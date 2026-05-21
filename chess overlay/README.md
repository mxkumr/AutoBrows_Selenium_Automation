# Chess Overlay

Real-time best-move suggester for [chess.com](https://www.chess.com). Drives a real Chrome browser via Selenium, reads the live board out of the page, asks Stockfish what to play, and either **highlights** the move on the board or **clicks it for you** (CDP synthetic mouse input).

> Educational/curiosity project. Using engine assistance in rated games against other people is cheating and will get you banned. Default mode is **highlight-only** on **unrated** games against a friend.

---

## Requirements

### Software

| Dependency | Why |
|------------|-----|
| Python 3.10+ | Runtime |
| Google Chrome (installed) | The bot drives it via Selenium |
| `selenium` (Python) | Browser automation |
| `python-chess` | Board state + UCI engine wrapper |
| **Stockfish** Windows binary | The engine |

### Python packages

```bash
pip install selenium chess
```

`selenium` 4.6+ ships with Selenium Manager — it auto-fetches a matching ChromeDriver, so no manual driver setup is needed.

### Stockfish binary

The binary is **not** in this repo (GitHub 100 MB limit). You need to place it here:

```text
chess overlay/stockfish/stockfish-windows-x86-64-avx2.exe
```

Get it from [stockfishchess.org/download](https://stockfishchess.org/download/) → pick the Windows AVX2 build. If your CPU does not support AVX2, download the appropriate Windows variant and update `STOCKFISH_PATH` in `chess-bot.py`.

---

## How to use

From the repo root:

```bash
python "chess overlay/chess-bot.py"
```

What happens:

1. Chrome opens to `chess.com/login` — **you log in manually** (avoids bot detection).
2. The script waits until a real game board is visible (≥300 px).
3. Console prints something like:
   ```text
   Game board ready (504x504, you play Black)
   Engaged. Mode: HIGHLIGHT_ONLY | Thinking time: 0.3s
   ```
4. On every position change it reads the board, and when it's **your turn** it computes the best move and overlays a yellow/red highlight + arrow on the board.
5. You make the move (any move — the next suggestion auto-loads on the next ply).

Stop with `Ctrl+C` in the terminal.

### Configuration (top of `chess-bot.py`)

| Option | Default | Meaning |
|--------|---------|---------|
| `HIGHLIGHT_ONLY` | `True` | `True` = draw suggestion only. `False` = auto-click the move via Chrome DevTools Protocol |
| `ENGINE_THINK_TIME` | `0.30` | Seconds Stockfish thinks per move. Bump to `0.5–2.0` for stronger play |
| `FORCE_PLAY_AS` | `None` | Override side detection. Set to `"white"` or `"black"` if the bot guesses wrong |
| `STOCKFISH_PATH` | `chess overlay/stockfish/stockfish-windows-x86-64-avx2.exe` | Path to the engine binary |
| `HIGHLIGHT_SOURCE_COLOR` / `TARGET_COLOR` / `ARROW_COLOR` | yellow / red / orange | Overlay colors |
| `DEBUG_CLICKS` | `True` | Print click coordinates when auto-clicking |

### Tips

- The bot re-detects which side you play every loop — if it locks onto the wrong color from a lobby preview board, it self-corrects once the live game loads. You can also hard-pin it with `FORCE_PLAY_AS`.
- Play **unrated** games (against a friend, or set up casual games). The bot only knows what's on the page; it does not modify any chess.com state.
- If you change `HIGHLIGHT_ONLY = False`, the click path randomizes timing and jitters cursor positions to avoid mechanical-looking clicks, but `chess.com` may still detect automation. Use at your own risk.

---

## Architecture (at a glance)

Three subsystems talking in a tight loop:

```text
       Chrome (Selenium)                Python                       Stockfish
   +-----------------------+      +------------------+         +-------------------+
   |  chess.com DOM        |      |  chess.Board     |         |  UCI subprocess   |
   |  wc-chess-board       |<---->|  (canonical FEN) |<------->|  engine.play()    |
   |  injected overlay JS  |      |  main loop       |         |                   |
   |  CDP mouse events     |      |                  |         |                   |
   +-----------------------+      +------------------+         +-------------------+
```

### What each layer does

- **Selenium + Chrome.** Real, non-headless browser. You log in manually so chess.com sees a normal session.
- **DOM scraping (JS injected via `execute_script`).** Two read paths:
  1. Try `wc-chess-board.game.getFEN()` (the widget's own API, when exposed).
  2. Fall back to parsing `.piece` element classes (`wn`, `square-71`, …) into an 8×8 grid → FEN piece-placement.
- **Turn parity.** Counts visible move-list nodes; even = White to move, odd = Black to move. Combined with the piece-placement it builds a full FEN.
- **`chess.Board`.** Single source of truth for legality, SAN naming, game-over detection.
- **Stockfish.** Launched once at startup via `chess.engine.SimpleEngine.popen_uci`. Asked for a best move with a time limit on every ply where it's your turn.
- **Output:**
  - **Highlight mode** — injects an absolute-positioned `<div>` overlay with two square markers and an SVG arrow, mirrored if you play Black.
  - **Auto-click mode** — converts the algebraic square to viewport coordinates, then sends real mouse events via Chrome DevTools Protocol (`Input.dispatchMouseEvent`). Promotion pieces are picked with a separate Selenium click on the chess.com promotion popup.

### Control loop

```text
loop every ~0.4s:
    read board → build FEN → load into chess.Board
    re-detect player color (handles lobby misdetection)
    if position changed:
        clear previous overlay
    if board.is_game_over():
        break
    if it's our turn AND we haven't already suggested for this ply:
        engine.play(board, time=ENGINE_THINK_TIME)
        if HIGHLIGHT_ONLY: draw overlay
        else:              CDP-click source → target → handle promotion
```

### Failure handling

- Unreadable board → retry next tick.
- Invalid FEN → skip cycle (don't poison `chess.Board`).
- Engine error → log + retry.
- Promotion popup not yet rendered → poll for up to ~3 seconds before clicking.

---

## Files in this folder

| Path | Purpose |
|------|---------|
| `chess-bot.py` | The bot |
| `stockfish/` | Stockfish source + binary location (binary is **gitignored**) |
| `stockfish/stockfish-windows-x86-64-avx2.exe` | The engine (you supply this) |

---

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `FileNotFoundError` on `Stockfish` | Binary missing at `chess overlay/stockfish/stockfish-windows-x86-64-avx2.exe` |
| Bot says `you play White` but you're Black (or vice versa) | Started while a lobby/preview board was visible — wait, it self-corrects, or set `FORCE_PLAY_AS` |
| No suggestion ever appears | Console shows `turn=<other color>` on every tick → the bot thinks you are the other color |
| Suggestion shows on wrong squares | Board flip detected wrong — set `FORCE_PLAY_AS` |
| `DEPRECATED_ENDPOINT` / `socket_manager` errors in console | Chrome internal noise, harmless |
| Auto-click moves the wrong piece | chess.com markup changed or page zoom is non-100% — keep zoom at 100% |

