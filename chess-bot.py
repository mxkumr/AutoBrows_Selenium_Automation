import time
import random
from pathlib import Path
import chess
import chess.engine
from selenium import webdriver
from selenium.webdriver.common.by import By

# --- PIPELINE INITIALIZATION CONFIG ---
STOCKFISH_PATH = str(
    Path(__file__).resolve().parent
    / "stockfish"
    / "stockfish-windows-x86-64-avx2.exe"
)
GAME_URL_HINTS = ("/play/online", "/play/computer", "/live", "/game/live", "/game/daily", "/game/")
HOME_URL_HINTS = ("/home", "/learn", "/lessons", "/puzzles", "/today")  # not a real game

HIGHLIGHT_ONLY = True       # True = only show best move, don't click
ENGINE_THINK_TIME = 0.30    # seconds; bump to 0.5+ for stronger play

# Force which side you play, regardless of board flip detection.
# Set to "white", "black", or None for auto-detect via the board's `flipped` class.
# Useful if the bot locks onto the wrong side because of a lobby/preview board.
FORCE_PLAY_AS = None

HIGHLIGHT_SOURCE_COLOR = "rgba(255, 196, 0, 0.55)"
HIGHLIGHT_TARGET_COLOR = "rgba(255, 60, 60, 0.65)"
HIGHLIGHT_ARROW_COLOR = "#ff8c00"

driver = webdriver.Chrome()
board = chess.Board()
engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)


DEBUG_CLICKS = True


def _visible_area(el):
    r = el.rect
    return r["width"] * r["height"] if el.is_displayed() else 0


def get_board_element(min_side=300):
    """Find the largest visible wc-chess-board / chess-board. Reject tiny preview boards."""
    for sel in ("wc-chess-board", "chess-board"):
        shown = [e for e in driver.find_elements(By.CSS_SELECTOR, sel) if _visible_area(e) > 0]
        if shown:
            el = max(shown, key=_visible_area)
            r = el.rect
            if min(r["width"], r["height"]) >= min_side:
                return el
    raise RuntimeError("No interactive chess board found yet")


def detect_play_as_white(board_el):
    """`wc-chess-board.flipped` means the user sits on the Black side.

    Honors FORCE_PLAY_AS override so a lobby/preview board can't lock the bot
    to the wrong side.
    """
    if isinstance(FORCE_PLAY_AS, str):
        forced = FORCE_PLAY_AS.strip().lower()
        if forced == "white":
            return True
        if forced == "black":
            return False
    flipped = driver.execute_script("return arguments[0].classList.contains('flipped');", board_el)
    return not bool(flipped)


def on_game_page():
    url = driver.current_url.lower()
    if any(h in url for h in HOME_URL_HINTS):
        return False
    return any(h in url for h in GAME_URL_HINTS)


def wait_for_active_game():
    """Block until: (a) we're on a game URL, and (b) a real-sized board is visible."""
    print("⏳ Open or start a real game in this Chrome window. Waiting...")
    last_url = ""
    while True:
        url = driver.current_url
        if url != last_url:
            print(f"   url={url}")
            last_url = url
        if on_game_page():
            try:
                el = get_board_element(min_side=300)
                r = el.rect
                play_white = detect_play_as_white(el)
                side_label = "White" if play_white else "Black"
                print(f"🏁 Game board ready ({r['width']:.0f}x{r['height']:.0f}, you play {side_label})")
                return el, play_white
            except Exception:
                pass
        time.sleep(1.0)


_SQUARE_CENTER_JS = """
const host = arguments[0];
const square = arguments[1];
const playAsWhite = arguments[2];
const file = square.charCodeAt(0) - 97;
const rank = parseInt(square[1], 10) - 1;
const r = host.getBoundingClientRect();
const side = Math.min(r.width, r.height);
const sq = side / 8;
const col = playAsWhite ? file : (7 - file);
const row = playAsWhite ? (7 - rank) : rank;
return {
  x: r.left + (col + 0.5) * sq,
  y: r.top + (row + 0.5) * sq,
  side: side,
  target: (document.elementFromPoint(r.left + (col + 0.5) * sq, r.top + (row + 0.5) * sq) || {tagName: '?'}).tagName
};
"""


def _cdp_mouse(event_type, x, y):
    driver.execute_cdp_cmd(
        "Input.dispatchMouseEvent",
        {
            "type": event_type,
            "x": float(x),
            "y": float(y),
            "button": "left",
            "buttons": 1 if event_type != "mouseReleased" else 0,
            "clickCount": 1,
            "pointerType": "mouse",
        },
    )


_HIGHLIGHT_JS = r"""
const host = arguments[0];
const fromSq = arguments[1];
const toSq = arguments[2];
const playAsWhite = arguments[3];
const srcColor = arguments[4];
const dstColor = arguments[5];
const arrowColor = arguments[6];

const OVERLAY_ID = '__bestmove_overlay__';
document.getElementById(OVERLAY_ID)?.remove();

const r = host.getBoundingClientRect();
const side = Math.min(r.width, r.height);
const sq = side / 8;

function center(square) {
  const file = square.charCodeAt(0) - 97;
  const rank = parseInt(square[1], 10) - 1;
  const col = playAsWhite ? file : (7 - file);
  const row = playAsWhite ? (7 - rank) : rank;
  return {
    x: r.left + (col + 0.5) * sq + window.scrollX,
    y: r.top + (row + 0.5) * sq + window.scrollY,
    col, row,
  };
}

const a = center(fromSq);
const b = center(toSq);

const overlay = document.createElement('div');
overlay.id = OVERLAY_ID;
Object.assign(overlay.style, {
  position: 'absolute', left: '0', top: '0', width: '100%', height: '100%',
  pointerEvents: 'none', zIndex: 999999,
});

function squareBox(c, color) {
  const box = document.createElement('div');
  Object.assign(box.style, {
    position: 'absolute',
    left: (c.x - sq / 2) + 'px',
    top: (c.y - sq / 2) + 'px',
    width: sq + 'px',
    height: sq + 'px',
    background: color,
    boxSizing: 'border-box',
    border: '3px solid ' + color.replace(/[\d\.]+\)$/, '0.95)'),
    borderRadius: '6px',
  });
  return box;
}

overlay.appendChild(squareBox(a, srcColor));
overlay.appendChild(squareBox(b, dstColor));

const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
Object.assign(svg.style, {
  position: 'absolute',
  left: '0', top: '0',
  width: document.documentElement.scrollWidth + 'px',
  height: document.documentElement.scrollHeight + 'px',
  pointerEvents: 'none',
});
svg.setAttribute('width', document.documentElement.scrollWidth);
svg.setAttribute('height', document.documentElement.scrollHeight);

const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
defs.innerHTML = `
  <marker id="bm-arrow-head" viewBox="0 0 10 10" refX="6" refY="5"
          markerWidth="6" markerHeight="6" orient="auto">
    <path d="M0,0 L10,5 L0,10 Z" fill="${arrowColor}" />
  </marker>`;
svg.appendChild(defs);

const dx = b.x - a.x, dy = b.y - a.y;
const len = Math.hypot(dx, dy);
const trim = sq * 0.35;
const ux = dx / len, uy = dy / len;
const x1 = a.x + ux * trim;
const y1 = a.y + uy * trim;
const x2 = b.x - ux * trim;
const y2 = b.y - uy * trim;

const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
line.setAttribute('x1', x1); line.setAttribute('y1', y1);
line.setAttribute('x2', x2); line.setAttribute('y2', y2);
line.setAttribute('stroke', arrowColor);
line.setAttribute('stroke-width', Math.max(6, sq * 0.18));
line.setAttribute('stroke-linecap', 'round');
line.setAttribute('marker-end', 'url(#bm-arrow-head)');
line.setAttribute('opacity', '0.9');
svg.appendChild(line);
overlay.appendChild(svg);

document.body.appendChild(overlay);
return {from: fromSq, to: toSq};
"""


def highlight_move(source_square, target_square):
    board_el = get_board_element()
    play_white = detect_play_as_white(board_el)
    driver.execute_script(
        _HIGHLIGHT_JS,
        board_el,
        source_square,
        target_square,
        play_white,
        HIGHLIGHT_SOURCE_COLOR,
        HIGHLIGHT_TARGET_COLOR,
        HIGHLIGHT_ARROW_COLOR,
    )


def clear_highlight():
    driver.execute_script("document.getElementById('__bestmove_overlay__')?.remove();")


def click_square(square_name):
    """Real OS-level mouse click via Chrome DevTools Protocol. Produces isTrusted events."""
    time.sleep(random.uniform(0.4, 0.9))
    board_el = get_board_element()
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", board_el)
    time.sleep(0.15)

    play_white = detect_play_as_white(board_el)
    info = driver.execute_script(_SQUARE_CENTER_JS, board_el, square_name, play_white)

    jitter = (info["side"] / 8.0) * 0.12
    x = info["x"] + random.uniform(-jitter, jitter)
    y = info["y"] + random.uniform(-jitter, jitter)

    _cdp_mouse("mouseMoved", x, y)
    time.sleep(random.uniform(0.04, 0.10))
    _cdp_mouse("mousePressed", x, y)
    time.sleep(random.uniform(0.04, 0.09))
    _cdp_mouse("mouseReleased", x, y)

    if DEBUG_CLICKS:
        print(f"   click {square_name}: ({x:.0f},{y:.0f}) over=<{info['target']}> [CDP]")


def handle_promotion(promotion_piece):
    """Chess.com pops a 4-piece picker after a pawn reaches the last rank."""
    if promotion_piece is None:
        return
    letter = chess.piece_symbol(promotion_piece).lower()  # q/r/b/n
    color = "w" if board.turn == chess.WHITE else "b"
    selector = f"div.promotion-piece.{color}{letter}, .promotion-piece-{color}{letter}"
    for _ in range(20):
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            elements[0].click()
            return
        time.sleep(0.15)

_READ_POSITION_JS = r"""
const host = arguments[0];

// Approach 1: wc-chess-board's own API, if exposed
try {
  if (host.game) {
    if (typeof host.game.getFEN === 'function') return {fen: host.game.getFEN(), src: 'game.getFEN'};
    if (typeof host.game.fen === 'function')    return {fen: host.game.fen(),    src: 'game.fen'};
  }
} catch (e) {}

// Approach 2: read .piece elements (classes like "piece wn square-71")
const pieces = host.querySelectorAll('.piece');
if (!pieces.length) return {fen: null, src: 'no-pieces'};

const grid = Array.from({length: 8}, () => Array(8).fill(null));
for (const p of pieces) {
  let color = null, type = null, sq = null;
  for (const cls of p.classList) {
    const m1 = cls.match(/^([wb])([kqrbnp])$/i);
    if (m1) { color = m1[1].toLowerCase(); type = m1[2].toLowerCase(); continue; }
    const m2 = cls.match(/^square-(\d)(\d)$/);
    if (m2) { sq = [parseInt(m2[1], 10), parseInt(m2[2], 10)]; }
  }
  if (color && type && sq) {
    const file = sq[0] - 1;       // 1..8 → 0..7  (a..h)
    const rank = sq[1] - 1;       // 1..8 → 0..7  (1..8)
    const sym = color === 'w' ? type.toUpperCase() : type.toLowerCase();
    // FEN row 0 = rank 8 (top), row 7 = rank 1 (bottom)
    grid[7 - rank][file] = sym;
  }
}

const rows = grid.map(row => {
  let s = '', empty = 0;
  for (const c of row) {
    if (c === null) { empty++; } else { if (empty) { s += empty; empty = 0; } s += c; }
  }
  if (empty) s += empty;
  return s;
});
return {fen: rows.join('/'), src: 'piece-classes'};
"""


def read_position_from_board():
    """Returns (piece_placement_fen, source_tag). Piece placement only, no metadata."""
    board_el = get_board_element()
    info = driver.execute_script(_READ_POSITION_JS, board_el)
    if not info or not info.get("fen"):
        return None, info.get("src") if info else "error"
    fen = info["fen"]
    # Some Chess.com builds return a full FEN here. Keep just the placement field.
    placement = fen.split()[0]
    return placement, info["src"]


def count_moves_on_page():
    """Best-effort count of moves played, used only to derive side-to-move parity."""
    selectors = (
        "wc-vertical-move-list .node",
        "wc-move-list .node",
        "vertical-move-list .node",
        ".main-line .node",
        ".move-list-row .node",
    )
    for sel in selectors:
        try:
            nodes = driver.find_elements(By.CSS_SELECTOR, sel)
        except Exception:
            continue
        visible = []
        for n in nodes:
            try:
                if not n.is_displayed():
                    continue
                txt = (n.text or "").strip()
                if not txt:
                    continue
                if txt.replace(".", "").isdigit():
                    continue  # move-number label
                visible.append(n)
            except Exception:
                continue
        if visible:
            return len(visible), sel
    return 0, None


def sync_board_from_page(debug=False):
    """Read FEN directly from the live board element. Returns ply count."""
    placement, src = read_position_from_board()
    if not placement:
        if debug:
            print(f"   ⚠️ couldn't read board ({src})")
        return -1

    moves_played, sel = count_moves_on_page()
    turn = "w" if moves_played % 2 == 0 else "b"
    full_move = 1 + moves_played // 2
    fen = f"{placement} {turn} KQkq - 0 {full_move}"

    try:
        new_board = chess.Board(fen=fen)
    except ValueError as exc:
        if debug:
            print(f"   ⚠️ invalid FEN: {exc}  ({fen})")
        return -1

    board.set_fen(new_board.fen())
    if debug:
        print(f"   📜 board-read via {src!r}, move_list_sel={sel!r}, moves={moves_played}")
        print(f"      FEN: {board.fen()}")
    return moves_played

# --- RUNTIME OPERATIONS ---
def main():
    # Direct access bypasses headless signature detection blocks
    driver.get("https://www.chess.com/login")
    print("⏳ ACTION REQUIRED: Complete authentication, invite your friend to an UNRATED match.")
    
    _board_el, play_white = wait_for_active_game()
    our_color = chess.WHITE if play_white else chess.BLACK
    last_color_label = "White" if play_white else "Black"

    last_ply = -1
    highlighted_for_ply = -1
    forced_msg = f" | FORCED as {FORCE_PLAY_AS}" if isinstance(FORCE_PLAY_AS, str) else ""
    print(f"🎯 Engaged. Mode: {'HIGHLIGHT_ONLY' if HIGHLIGHT_ONLY else 'AUTO-CLICK'} | Thinking time: {ENGINE_THINK_TIME}s{forced_msg}")

    while True:
        try:
            current_ply = sync_board_from_page(debug=False)
        except Exception as exc:
            print(f"⚠️ Sync failed: {exc}")
            time.sleep(0.5)
            continue

        # Re-detect color each iteration. Lobby/preview boards can mis-report
        # orientation; the live game board is the source of truth.
        try:
            live_board_el = get_board_element()
            play_white_now = detect_play_as_white(live_board_el)
            new_color = chess.WHITE if play_white_now else chess.BLACK
            if new_color != our_color:
                our_color = new_color
                last_color_label = "White" if play_white_now else "Black"
                highlighted_for_ply = -1  # force re-suggestion under the new color
                clear_highlight()
                print(f"🔄 Side updated: you play {last_color_label}")
        except Exception:
            pass  # transient: between games, page reload, etc.

        if current_ply != last_ply:
            sync_board_from_page(debug=True)  # dump what we parsed
            print(f"   ⏱ ply={current_ply} turn={'White' if board.turn == chess.WHITE else 'Black'} | you={last_color_label}")
            last_ply = current_ply
            clear_highlight()
            if highlighted_for_ply != current_ply:
                highlighted_for_ply = -1

        if board.is_game_over():
            break

        if board.turn == our_color and highlighted_for_ply != current_ply:
            print("🧠 Computing best move...")
            try:
                computation = engine.play(board, chess.engine.Limit(time=ENGINE_THINK_TIME))
            except Exception as exc:
                print(f"⚠️ Engine error: {exc}")
                time.sleep(0.5)
                continue
            engine_move = computation.move
            if engine_move is None:
                time.sleep(0.4)
                continue

            source_square = chess.square_name(engine_move.from_square)
            target_square = chess.square_name(engine_move.to_square)
            move_san = board.san(engine_move)
            print(f"💡 Best move: {move_san}  ({source_square} -> {target_square})")

            if HIGHLIGHT_ONLY:
                try:
                    highlight_move(source_square, target_square)
                    highlighted_for_ply = current_ply
                except Exception as exc:
                    print(f"⚠️ Highlight failed: {exc}")
                print("👉 Play the suggested move (or any move); next suggestion auto-loads.")
            else:
                time.sleep(random.uniform(0.6, 1.4))
                try:
                    click_square(source_square)
                    click_square(target_square)
                    handle_promotion(engine_move.promotion)
                except Exception as exc:
                    print(f"⚠️ Click failure ({exc})")
                highlighted_for_ply = current_ply
                time.sleep(0.8)

        time.sleep(0.4)

    print(f"🏳️ Game concluded. Resulting state: {board.outcome()}")
    clear_highlight()
    engine.quit()
    driver.quit()

if __name__ == "__main__":
    main()