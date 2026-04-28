const setupPanel = document.getElementById('setup-panel');
const gamePanel = document.getElementById('game-panel');
const setupError = document.getElementById('setup-error');
const nameInput = document.getElementById('player-name');
const colorBlackBtn = document.getElementById('color-black');
const colorWhiteBtn = document.getElementById('color-white');
const opponentSelect = document.getElementById('opponent-select');
const startBtn = document.getElementById('start-game');

const boardEl = document.getElementById('board');
const moveNumberEl = document.getElementById('move-number');
const nextPlayerEl = document.getElementById('next-player');
const statusEl = document.getElementById('status-line');
const blackCountEl = document.getElementById('black-count');
const whiteCountEl = document.getElementById('white-count');
const userCountEl = document.getElementById('user-count');
const computerCountEl = document.getElementById('computer-count');
const messagesEl = document.getElementById('messages');
const winnerLineEl = document.getElementById('winner-line');
const opponentNameEl = document.getElementById('opponent-name');
const opponentDepthEl = document.getElementById('opponent-depth');
const opponentPortraitEl = document.getElementById('opponent-portrait');
const opponentCardEl = document.getElementById('opponent-card');
const opponentThinkingEl = document.getElementById('opponent-thinking');
const opponentOpeningPhraseEl = document.getElementById('opponent-opening-phrase');
const resignBtn = document.getElementById('resign-game');
const restartBtn = document.getElementById('restart-game');
const passAlertEl = document.getElementById('pass-alert');
const passAlertTextEl = document.getElementById('pass-alert-text');
const dismissPassAlertBtn = document.getElementById('dismiss-pass-alert');
const helpBtn = document.getElementById('help-btn');
const helpModal = document.getElementById('help-modal');
const closeHelpBtn = document.getElementById('close-help');
const helpModalBackdrop = document.getElementById('help-modal-backdrop');

let selectedColor = 'black';
let gameId = null;
let state = null;
let socket = null;
let computerMoveInFlight = false;
let autoActionInFlight = false;
let passAlertQueue = [];
let passAlertVisible = false;
let pendingPassDismissResolver = null;
let openingPhraseVisible = false;

function openHelpModal() {
  helpModal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeHelpModal() {
  helpModal.classList.add('hidden');
  document.body.style.overflow = '';
}

function setColor(color) {
  selectedColor = color;
  colorBlackBtn.classList.toggle('active', color === 'black');
  colorWhiteBtn.classList.toggle('active', color === 'white');
}

function toNotation(position) {
  const row = Math.floor(position / 8);
  const col = position % 8;
  return `${String.fromCharCode(97 + col)}${row + 1}`;
}

function clearBoard() {
  boardEl.innerHTML = '';
}

function createCell(position, cellState, isLegal) {
  const cell = document.createElement('button');
  cell.className = `cell ${isLegal ? 'playable legal' : ''}`;
  cell.type = 'button';
  cell.dataset.position = String(position);
  cell.dataset.testid = `cell-${position}`;
  cell.title = toNotation(position);

  if (state && state.last_move && state.last_move.move === position) {
    cell.classList.add('last-move');
  }
  if (state && state.last_player_move && state.last_player_move.move === position) {
    cell.classList.add('last-player-move');
  }
  if (state && state.last_computer_move && state.last_computer_move.move === position) {
    cell.classList.add('last-computer-move');
  }

  if (cellState === 'black' || cellState === 'white') {
    const disc = document.createElement('div');
    disc.className = `disc ${cellState}`;
    cell.appendChild(disc);
  } else if (isLegal && state && !state.game_over && state.next_player === state.player_color) {
    const hint = document.createElement('div');
    hint.className = 'hint';
    cell.appendChild(hint);
  }

  cell.addEventListener('click', () => onCellClick(position));
  return cell;
}

function renderBoard() {
  clearBoard();
  if (!state) {
    return;
  }

  const legalSet = new Set(state.legal_moves);
  for (let pos = 0; pos < 64; pos += 1) {
    const cell = createCell(pos, state.board[pos], legalSet.has(pos));
    boardEl.appendChild(cell);
  }
}

function renderMessages() {
  messagesEl.innerHTML = '';
  if (!state) {
    return;
  }

  for (const msg of state.messages) {
    const li = document.createElement('li');
    li.textContent = msg;
    messagesEl.appendChild(li);
  }
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function userColorDisplay(color) {
  return color === 'black' ? 'Black' : 'White';
}

function updateStatusLine() {
  if (!state) {
    statusEl.textContent = 'Waiting...';
    return;
  }

  if (state.game_over) {
    statusEl.textContent = 'Game over';
    return;
  }

  if (computerMoveInFlight) {
    statusEl.textContent = 'Computer thinking...';
    return;
  }

  if (state.next_player === state.player_color) {
    statusEl.textContent = `Your turn (${userColorDisplay(state.player_color)})`;
  } else {
    statusEl.textContent = `Computer turn (${userColorDisplay(state.computer_color)})`;
  }
}

function updateThinkingUi() {
  const isThinking = Boolean(
    state &&
    !state.game_over &&
    (computerMoveInFlight || (autoActionInFlight && state.next_player === state.computer_color))
  );
  opponentCardEl.classList.toggle('thinking', isThinking);
  opponentThinkingEl.classList.toggle('hidden', !isThinking);
}

function enqueuePassAlert(actor) {
  const actorLabel = actor === 'player' ? 'You' : state?.opponent_name || 'Computer';
  passAlertQueue.push(`${actorLabel} must pass because there are no legal moves.`);
  showNextPassAlert();
}

function showNextPassAlert() {
  if (passAlertVisible || passAlertQueue.length === 0) {
    return;
  }
  passAlertVisible = true;
  passAlertTextEl.textContent = passAlertQueue.shift();
  passAlertEl.classList.remove('hidden');
}

function waitForPassAlertDismiss() {
  return new Promise((resolve) => {
    pendingPassDismissResolver = resolve;
  });
}

function dismissPassAlert() {
  passAlertVisible = false;
  passAlertEl.classList.add('hidden');
  if (pendingPassDismissResolver) {
    const resolver = pendingPassDismissResolver;
    pendingPassDismissResolver = null;
    resolver();
  }
  showNextPassAlert();
}

function extractOpeningPhrase(currentState) {
  if (!currentState) {
    return '';
  }
  const prefix = `${currentState.opponent_name}:`;
  const line = currentState.messages.find((msg) => msg.startsWith(prefix));
  if (!line) {
    return '';
  }
  return line.slice(prefix.length).trim();
}

function showOpeningPhrase(phrase) {
  if (!phrase) {
    openingPhraseVisible = false;
    opponentOpeningPhraseEl.classList.add('hidden');
    opponentOpeningPhraseEl.textContent = '';
    return;
  }
  openingPhraseVisible = true;
  opponentOpeningPhraseEl.textContent = phrase;
  opponentOpeningPhraseEl.classList.remove('hidden');
}

function hideOpeningPhrase() {
  if (!openingPhraseVisible) {
    return;
  }
  openingPhraseVisible = false;
  opponentOpeningPhraseEl.classList.add('hidden');
}

function renderStats() {
  if (!state) {
    return;
  }
  moveNumberEl.textContent = String(state.move_number);
  nextPlayerEl.textContent = userColorDisplay(state.next_player);
  blackCountEl.textContent = String(state.black_count);
  whiteCountEl.textContent = String(state.white_count);
  userCountEl.textContent = String(state.user_count);
  computerCountEl.textContent = String(state.computer_count);
  opponentNameEl.textContent = state.opponent_name;
  opponentDepthEl.textContent = `Depth ${state.ai_depth}`;
  opponentPortraitEl.src = state.opponent_portrait;
  opponentPortraitEl.alt = `${state.opponent_name} portrait`;
  resignBtn.disabled = state.game_over;
  restartBtn.classList.toggle('hidden', !state.game_over);

  if (state.game_over) {
    if (state.winner === 'player') {
      winnerLineEl.textContent = `Congratulations, ${state.player_name}! You beat ${state.opponent_name}.`;
    } else if (state.winner === 'computer') {
      winnerLineEl.textContent = `Condolences, ${state.player_name}. ${state.opponent_name} wins this one.`;
    } else {
      winnerLineEl.textContent = `Draw game. Well played, ${state.player_name}.`;
    }
  } else {
    winnerLineEl.textContent = '';
  }

  updateStatusLine();
  updateThinkingUi();
}

function renderAll() {
  renderBoard();
  renderStats();
  renderMessages();
}

async function safeJson(response) {
  let payload = {};
  try {
    payload = await response.json();
  } catch (e) {
    payload = {};
  }
  return payload;
}

async function apiPost(path, body = undefined) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : null,
  });

  const payload = await safeJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return payload;
}

function closeSocket() {
  if (socket) {
    try {
      socket.close();
    } catch (e) {
      // ignore
    }
  }
  socket = null;
}

function connectSocket() {
  closeSocket();
  if (!gameId) {
    return;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  socket = new WebSocket(`${protocol}//${window.location.host}/ws/game/${gameId}`);

  socket.addEventListener('message', (event) => {
    try {
      const envelope = JSON.parse(event.data);
      if (envelope.type === 'state_update') {
        state = envelope.data;
        renderAll();
        driveGameLoop();
      }
    } catch (e) {
      // ignore malformed events
    }
  });
}

async function driveGameLoop() {
  if (autoActionInFlight) {
    return;
  }
  autoActionInFlight = true;

  try {
    while (state && gameId && !state.game_over) {
      if (state.legal_moves.length === 0) {
        const actor = state.next_player === state.player_color ? 'player' : 'computer';
        const newState = await apiPost(`/api/game/${gameId}/pass`, { actor });
        state = newState;
        renderAll();
        if (!state.game_over && state.legal_moves.length > 0) {
          enqueuePassAlert(actor);
          await waitForPassAlertDismiss();
        }
        continue;
      }

      if (state.next_player === state.computer_color) {
        computerMoveInFlight = true;
        updateStatusLine();
        try {
          const newState = await apiPost(`/api/game/${gameId}/computer-move`);
          state = newState;
          renderAll();
          continue;
        } finally {
          computerMoveInFlight = false;
          updateStatusLine();
          updateThinkingUi();
        }
      }

      break;
    }
  } catch (e) {
    setupError.textContent = e.message;
  } finally {
    autoActionInFlight = false;
    updateStatusLine();
    updateThinkingUi();
  }
}

async function onCellClick(position) {
  if (!state || !gameId) {
    return;
  }
  if (state.game_over || state.next_player !== state.player_color || computerMoveInFlight) {
    return;
  }
  if (!state.legal_moves.includes(position)) {
    return;
  }

  setupError.textContent = '';
  try {
    const newState = await apiPost(`/api/game/${gameId}/move`, { move: position });
    state = newState;
    renderAll();
    await driveGameLoop();
  } catch (e) {
    setupError.textContent = e.message;
  }
}

async function startGame() {
  setupError.textContent = '';
  const playerName = nameInput.value.trim();
  if (!playerName) {
    setupError.textContent = 'Please enter a player name.';
    return;
  }

  startBtn.disabled = true;
  try {
    const aiDepth = Number(opponentSelect.value);
    const payload = await apiPost('/api/game', {
      player_name: playerName,
      player_color: selectedColor,
      ai_depth: aiDepth,
    });

    gameId = payload.game_id;
    state = payload.state;

    setupPanel.classList.add('hidden');
    gamePanel.classList.remove('hidden');
    restartBtn.classList.add('hidden');

    connectSocket();
    renderAll();
    showOpeningPhrase(extractOpeningPhrase(state));
    await driveGameLoop();
  } catch (e) {
    setupError.textContent = e.message;
  } finally {
    startBtn.disabled = false;
  }
}

function resetToSetup() {
  closeSocket();
  gameId = null;
  state = null;
  computerMoveInFlight = false;
  autoActionInFlight = false;
  passAlertQueue = [];
  passAlertVisible = false;
  pendingPassDismissResolver = null;
  openingPhraseVisible = false;
  passAlertEl.classList.add('hidden');
  opponentOpeningPhraseEl.classList.add('hidden');
  opponentOpeningPhraseEl.textContent = '';
  clearBoard();
  winnerLineEl.textContent = '';
  setupError.textContent = '';
  gamePanel.classList.add('hidden');
  setupPanel.classList.remove('hidden');
}

async function resignGame() {
  if (!gameId || !state || state.game_over) {
    return;
  }
  resignBtn.disabled = true;
  setupError.textContent = '';
  try {
    const newState = await apiPost(`/api/game/${gameId}/resign`, { actor: 'player' });
    state = newState;
    renderAll();
  } catch (e) {
    setupError.textContent = e.message;
    resignBtn.disabled = false;
  }
}

colorBlackBtn.addEventListener('click', () => setColor('black'));
colorWhiteBtn.addEventListener('click', () => setColor('white'));
startBtn.addEventListener('click', startGame);
resignBtn.addEventListener('click', resignGame);
restartBtn.addEventListener('click', resetToSetup);
dismissPassAlertBtn.addEventListener('click', dismissPassAlert);
gamePanel.addEventListener('click', hideOpeningPhrase);

helpBtn.addEventListener('click', openHelpModal);
closeHelpBtn.addEventListener('click', closeHelpModal);
helpModal.addEventListener('click', (event) => {
  // Close modal if clicking on the backdrop (not on the content)
  if (event.target === helpModal) {
    closeHelpModal();
  }
});
window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !helpModal.classList.contains('hidden')) {
    closeHelpModal();
  }
});

window.addEventListener('beforeunload', () => {
  closeSocket();
});

setColor('black');
