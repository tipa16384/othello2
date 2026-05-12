#!/usr/bin/env python3
"""Generate annotated Othello board diagrams from game logs and analysis JSON.

This script renders one SVG per analyzed move and an index HTML page.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from board_state import BoardState, Player
from game_utils import notation_to_position
from make_move import make_move


ARROW_COLORS = {
    "pressure_flow": "#0077b6",
    "future_consequence": "#e76f51",
    "inevitability": "#6a4c93",
    "forced_response": "#2a9d8f",
}

HIGHLIGHT_COLORS = [
    "rgba(255, 193, 7, 0.35)",
    "rgba(46, 204, 113, 0.30)",
    "rgba(52, 152, 219, 0.28)",
    "rgba(231, 111, 81, 0.28)",
    "rgba(155, 89, 182, 0.28)",
]


@dataclass
class MoveAnnotation:
    move_number: int
    importance: float
    phase: str
    primary_move: dict[str, Any]
    summary: str
    tags: list[str]
    arrows: list[dict[str, Any]]
    highlight_regions: list[dict[str, Any]]
    alternative_moves: list[dict[str, Any]]


@dataclass
class RenderGeometry:
    board_x: int = 80
    board_y: int = 110
    cell: int = 80

    @property
    def board_size(self) -> int:
        return self.cell * 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render analyzed Othello moments to SVG")
    parser.add_argument("--gamelog", required=True, help="Path to game log JSON file")
    parser.add_argument("--analysis", required=True, help="Path to analysis JSON file")
    parser.add_argument("--outdir", default="analysis_diagrams", help="Output directory")
    return parser.parse_args()


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_annotations(raw: Any) -> list[MoveAnnotation]:
    if not isinstance(raw, list):
        raise ValueError("Analysis JSON must be a list of move annotations")

    annotations: list[MoveAnnotation] = []
    for item in raw:
        annotations.append(
            MoveAnnotation(
                move_number=int(item["move_number"]),
                importance=float(item.get("importance", 0.0)),
                phase=str(item.get("phase", "")),
                primary_move=dict(item.get("primary_move", {})),
                summary=str(item.get("summary", "")),
                tags=list(item.get("tags", [])),
                arrows=list(item.get("arrows", [])),
                highlight_regions=list(item.get("highlight_regions", [])),
                alternative_moves=list(item.get("alternative_moves", [])),
            )
        )
    return annotations


def split_move_record(move_record: str) -> list[str]:
    cleaned = move_record.strip()
    if len(cleaned) % 2 != 0:
        raise ValueError("move_record length must be even")
    return [cleaned[i : i + 2] for i in range(0, len(cleaned), 2)]


def squares_to_bitmap(squares: list[str]) -> int:
    bitmap = 0
    for sq in squares:
        pos = notation_to_position(sq)
        bitmap |= 1 << pos
    return bitmap


def board_from_log_payload(board_payload: dict[str, Any]) -> BoardState:
    next_player_raw = str(board_payload.get("next_player", "black")).lower()
    next_player = Player.WHITE if next_player_raw == "white" else Player.BLACK
    black = squares_to_bitmap(list(board_payload.get("black_squares", [])))
    white = squares_to_bitmap(list(board_payload.get("white_squares", [])))
    return BoardState(
        user="analysis-render",
        black=black,
        white=white,
        next_player=next_player,
    )


def build_states_by_move_from_windows(gamelog: dict[str, Any]) -> dict[int, BoardState]:
    states: dict[int, BoardState] = {}
    for window in gamelog.get("windows", []):
        for move in window.get("moves", []):
            move_number = move.get("move_number")
            after = move.get("after", {})
            board_payload = after.get("board") if isinstance(after, dict) else None
            if isinstance(move_number, int) and isinstance(board_payload, dict):
                states[move_number] = board_from_log_payload(board_payload)
    return states


def build_states_by_move_from_record(move_record: str) -> dict[int, BoardState]:
    tokens = split_move_record(move_record)
    board = BoardState(user="analysis-render")
    states: dict[int, BoardState] = {}

    for idx, token in enumerate(tokens, start=1):
        pos = notation_to_position(token)
        try:
            board = make_move(pos, board)
        except ValueError:
            # Some compact logs omit pass turns; insert one implicit pass and retry.
            board = make_move(None, board)
            board = make_move(pos, board)
        states[idx] = board

    return states


def build_states_by_move(gamelog: dict[str, Any], required_moves: set[int]) -> dict[int, BoardState]:
    states = build_states_by_move_from_windows(gamelog)
    missing = required_moves - set(states.keys())
    if not missing:
        return states

    move_record = gamelog.get("move_record")
    if isinstance(move_record, str):
        replay_states = build_states_by_move_from_record(move_record)
        states.update(replay_states)

    return states


def notation_to_row_col(square: str) -> tuple[int, int]:
    s = square.strip().upper()
    if len(s) != 2:
        raise ValueError(f"Invalid square notation: {square}")
    col = ord(s[0]) - ord("A")
    row = int(s[1]) - 1
    if not (0 <= col < 8 and 0 <= row < 8):
        raise ValueError(f"Square out of range: {square}")
    return row, col


def square_center(square: str, geom: RenderGeometry) -> tuple[float, float]:
    row, col = notation_to_row_col(square)
    x = geom.board_x + col * geom.cell + geom.cell / 2.0
    y = geom.board_y + row * geom.cell + geom.cell / 2.0
    return x, y


def board_piece_at(board: BoardState, row: int, col: int) -> str | None:
    pos = row * 8 + col
    mask = 1 << pos
    if board.black & mask:
        return "black"
    if board.white & mask:
        return "white"
    return None


def render_text_block(lines: list[str], x: int, y: int, font_size: int = 18, line_gap: int = 24) -> str:
    out = []
    for i, line in enumerate(lines):
        esc = html.escape(line)
        out.append(
            f'<text x="{x}" y="{y + i * line_gap}" font-size="{font_size}" '
            f'font-family="Segoe UI, Arial, sans-serif" fill="#1f2937">{esc}</text>'
        )
    return "\n".join(out)


def wrap_lines(text: str, width: int = 58) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return [""]
    return textwrap.wrap(stripped, width=width)


def render_move_svg(annotation: MoveAnnotation, board: BoardState, out_path: Path) -> None:
    geom = RenderGeometry()
    width = 1650
    height = 970
    panel_x = geom.board_x + geom.board_size + 70

    svg_parts: list[str] = []
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    )

    svg_parts.append(
        """
        <defs>
          <marker id="arrow-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#0077b6"/>
          </marker>
          <marker id="arrow-orange" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#e76f51"/>
          </marker>
          <marker id="arrow-purple" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#6a4c93"/>
          </marker>
          <marker id="arrow-green" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#2a9d8f"/>
          </marker>
          <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.30"/>
          </filter>
        </defs>
        """
    )

    svg_parts.append('<rect width="100%" height="100%" fill="#f5f7fa"/>')
    svg_parts.append(
        '<text x="80" y="58" font-size="34" font-weight="700" font-family="Segoe UI, Arial, sans-serif" fill="#111827">'
        f"Move {annotation.move_number}: {html.escape(annotation.primary_move.get('move', '?'))}"
        "</text>"
    )
    svg_parts.append(
        '<text x="80" y="88" font-size="18" font-family="Segoe UI, Arial, sans-serif" fill="#334155">'
        f"Phase: {html.escape(annotation.phase)} | Importance: {annotation.importance:.2f}"
        "</text>"
    )

    # Board base
    svg_parts.append(
        f'<rect x="{geom.board_x}" y="{geom.board_y}" width="{geom.board_size}" height="{geom.board_size}" '
        'fill="#2d6a4f" stroke="#1b4332" stroke-width="3" filter="url(#softShadow)"/>'
    )

    for i in range(9):
        x = geom.board_x + i * geom.cell
        y = geom.board_y + i * geom.cell
        svg_parts.append(
            f'<line x1="{x}" y1="{geom.board_y}" x2="{x}" y2="{geom.board_y + geom.board_size}" stroke="#d8f3dc" stroke-width="1.8"/>'
        )
        svg_parts.append(
            f'<line x1="{geom.board_x}" y1="{y}" x2="{geom.board_x + geom.board_size}" y2="{y}" stroke="#d8f3dc" stroke-width="1.8"/>'
        )

    for col in range(8):
        label = chr(ord("A") + col)
        x = geom.board_x + col * geom.cell + geom.cell / 2
        svg_parts.append(
            f'<text x="{x}" y="{geom.board_y - 16}" text-anchor="middle" font-size="20" font-weight="600" '
            f'font-family="Segoe UI, Arial, sans-serif" fill="#0f172a">{label}</text>'
        )

    for row in range(8):
        y = geom.board_y + row * geom.cell + geom.cell / 2 + 7
        label = str(row + 1)
        svg_parts.append(
            f'<text x="{geom.board_x - 24}" y="{y}" text-anchor="middle" font-size="20" font-weight="600" '
            f'font-family="Segoe UI, Arial, sans-serif" fill="#0f172a">{label}</text>'
        )

    # Highlight regions
    for idx, region in enumerate(annotation.highlight_regions):
        squares = region.get("squares", [])
        color = HIGHLIGHT_COLORS[idx % len(HIGHLIGHT_COLORS)]
        centers: list[tuple[float, float]] = []

        for sq in squares:
            row, col = notation_to_row_col(sq)
            x = geom.board_x + col * geom.cell
            y = geom.board_y + row * geom.cell
            svg_parts.append(
                f'<rect x="{x + 2}" y="{y + 2}" width="{geom.cell - 4}" height="{geom.cell - 4}" fill="{color}"/>'
            )
            centers.append((x + geom.cell / 2.0, y + geom.cell / 2.0))

            # Ensure highlighted squares are explicitly labeled.
            sq_esc = html.escape(str(sq).upper())
            svg_parts.append(
                f'<text x="{x + 8}" y="{y + 22}" font-size="14" font-weight="700" '
                f'font-family="Segoe UI, Arial, sans-serif" fill="#111827">{sq_esc}</text>'
            )

        if centers:
            avg_x = sum(c[0] for c in centers) / len(centers)
            avg_y = sum(c[1] for c in centers) / len(centers)
            label = html.escape(str(region.get("label", "Region")))
            label_w = max(130, len(label) * 8)
            box_x = max(geom.board_x + 6, min(avg_x - label_w / 2.0, geom.board_x + geom.board_size - label_w - 6))
            box_y = max(geom.board_y + 6, min(avg_y - 18, geom.board_y + geom.board_size - 34))
            svg_parts.append(
                f'<rect x="{box_x}" y="{box_y}" width="{label_w}" height="28" rx="7" ry="7" '
                'fill="#111827" fill-opacity="0.80"/>'
            )
            svg_parts.append(
                f'<text x="{box_x + label_w / 2.0}" y="{box_y + 19}" text-anchor="middle" font-size="14" '
                f'font-family="Segoe UI, Arial, sans-serif" fill="#ffffff">{label}</text>'
            )

    # Pieces
    for row in range(8):
        for col in range(8):
            piece = board_piece_at(board, row, col)
            if piece is None:
                continue
            cx = geom.board_x + col * geom.cell + geom.cell / 2
            cy = geom.board_y + row * geom.cell + geom.cell / 2
            if piece == "black":
                svg_parts.append(
                    f'<circle cx="{cx}" cy="{cy}" r="30" fill="#111111" stroke="#f3f4f6" stroke-width="2"/>'
                )
            else:
                svg_parts.append(
                    f'<circle cx="{cx}" cy="{cy}" r="30" fill="#f8fafc" stroke="#1f2937" stroke-width="2"/>'
                )

    # Primary move marker
    primary_sq = str(annotation.primary_move.get("move", "")).upper().strip()
    if len(primary_sq) == 2:
        try:
            row, col = notation_to_row_col(primary_sq)
            x = geom.board_x + col * geom.cell
            y = geom.board_y + row * geom.cell
            svg_parts.append(
                f'<rect x="{x + 4}" y="{y + 4}" width="{geom.cell - 8}" height="{geom.cell - 8}" '
                'fill="none" stroke="#ef4444" stroke-width="4" stroke-dasharray="8 5"/>'
            )
            label = html.escape(str(annotation.primary_move.get("label", "Primary move")))
            svg_parts.append(
                f'<text x="{x + geom.cell / 2}" y="{y + geom.cell + 24}" text-anchor="middle" '
                f'font-size="14" font-family="Segoe UI, Arial, sans-serif" fill="#b91c1c">{label}</text>'
            )
        except Exception:
            pass

    marker_by_color = {
        "#0077b6": "arrow-blue",
        "#e76f51": "arrow-orange",
        "#6a4c93": "arrow-purple",
        "#2a9d8f": "arrow-green",
    }

    # Arrows and labels
    for arrow in annotation.arrows:
        src = str(arrow.get("from", "")).upper()
        dst = str(arrow.get("to", "")).upper()
        arrow_type = str(arrow.get("type", "pressure_flow"))
        color = ARROW_COLORS.get(arrow_type, "#111827")
        marker = marker_by_color.get(color, "arrow-blue")

        try:
            x1, y1 = square_center(src, geom)
            x2, y2 = square_center(dst, geom)
        except Exception:
            continue

        svg_parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="6" '
            f'stroke-linecap="round" marker-end="url(#{marker})" opacity="0.95"/>'
        )

        label = html.escape(str(arrow.get("label", arrow_type)))
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0
        svg_parts.append(
            f'<rect x="{mx - 88}" y="{my - 18}" width="176" height="26" rx="6" ry="6" fill="#ffffff" fill-opacity="0.88"/>'
        )
        svg_parts.append(
            f'<text x="{mx}" y="{my}" text-anchor="middle" font-size="13" '
            f'font-family="Segoe UI, Arial, sans-serif" fill="#0f172a">{label}</text>'
        )

    panel_lines = [
        f"Primary: {annotation.primary_move.get('move', '?')} - {annotation.primary_move.get('label', '')}",
        "",
        "Summary:",
        *wrap_lines(annotation.summary, 56),
        "",
        "Tags:",
        ", ".join(annotation.tags) if annotation.tags else "(none)",
        "",
        "Alternatives:",
    ]

    if annotation.alternative_moves:
        for alt in annotation.alternative_moves:
            panel_lines.append(f"- {alt.get('move', '?')}: {alt.get('label', '')}")
    else:
        panel_lines.append("- none")

    svg_parts.append(
        f'<rect x="{panel_x - 20}" y="{geom.board_y}" width="520" height="{geom.board_size}" '
        'rx="14" ry="14" fill="#ffffff" stroke="#cbd5e1" stroke-width="2"/>'
    )
    svg_parts.append(render_text_block(panel_lines, panel_x + 10, geom.board_y + 40, font_size=18, line_gap=26))

    svg_parts.append("</svg>")

    out_path.write_text("\n".join(svg_parts), encoding="utf-8")


def render_index(outdir: Path, generated_files: list[tuple[int, str, str]]) -> None:
    cards = []
    for move_number, filename, title in generated_files:
        cards.append(
            "\n".join(
                [
                    '<article class="card">',
                    f'<h2>Move {move_number}: {html.escape(title)}</h2>',
                    f'<img src="{html.escape(filename)}" alt="Move {move_number} diagram" />',
                    "</article>",
                ]
            )
        )

    html_doc = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Othello Postgame Analysis Diagrams</title>
  <style>
    body {{
      margin: 0;
      font-family: Segoe UI, Arial, sans-serif;
      background: #eef2f7;
      color: #111827;
    }}
    main {{
      max-width: 1600px;
      margin: 0 auto;
      padding: 22px;
    }}
    h1 {{
      margin: 4px 0 16px;
      font-size: 30px;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #dbe3ee;
      border-radius: 14px;
      box-shadow: 0 2px 9px rgba(17, 24, 39, 0.08);
      padding: 12px 12px 18px;
      margin-bottom: 20px;
    }}
    .card h2 {{
      margin: 6px 8px 12px;
      font-size: 20px;
      font-weight: 700;
    }}
    .card img {{
      width: 100%;
      height: auto;
      border-radius: 10px;
      display: block;
      border: 1px solid #d4dbe7;
      background: #f8fafc;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Othello Postgame Analysis Diagrams</h1>
    {''.join(cards)}
  </main>
</body>
</html>
"""
    (outdir / "index.html").write_text(html_doc, encoding="utf-8")


def main() -> None:
    args = parse_args()

    gamelog = load_json(args.gamelog)
    raw_analysis = load_json(args.analysis)
    annotations = parse_annotations(raw_analysis)

    required_moves = {ann.move_number for ann in annotations}
    states_by_move = build_states_by_move(gamelog, required_moves)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    generated: list[tuple[int, str, str]] = []
    for ann in sorted(annotations, key=lambda a: a.move_number):
        board = states_by_move.get(ann.move_number)
        if board is None:
            print(f"Skipping move {ann.move_number}: not present in move_record")
            continue

        safe_phase = "".join(c for c in ann.phase.lower() if c.isalnum() or c in ("-", "_")) or "phase"
        filename = f"move_{ann.move_number:02d}_{safe_phase}.svg"
        title = str(ann.primary_move.get("label", ""))
        render_move_svg(ann, board, outdir / filename)
        generated.append((ann.move_number, filename, title))

    render_index(outdir, generated)

    print(f"Generated {len(generated)} diagram(s) in: {outdir.resolve()}")
    print(f"Open: {(outdir / 'index.html').resolve()}")


if __name__ == "__main__":
    main()
