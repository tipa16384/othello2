from threading import RLock

from api.game_session import GameSession


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._lock = RLock()

    def create(self, session: GameSession) -> GameSession:
        with self._lock:
            self._sessions[session.game_id] = session
            return session

    def get(self, game_id: str) -> GameSession | None:
        with self._lock:
            return self._sessions.get(game_id)

    def delete(self, game_id: str) -> None:
        with self._lock:
            self._sessions.pop(game_id, None)


session_store = SessionStore()
