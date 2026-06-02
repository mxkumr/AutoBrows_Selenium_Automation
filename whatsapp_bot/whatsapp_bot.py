import time
import random
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# --- CONFIGURATION ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"                  # local Ollama model
USER_DATA_DIR = "./playwright_session"    # persistent WhatsApp login

# Reply ONLY inside these chats. Names must match WhatsApp Web's sidebar /
# header EXACTLY (case-sensitive, incl. spaces/emoji). Any chat NOT in this
# list is completely ignored, even if it has unread messages.
TARGET_GROUPS = [
    "Anuraag Saarland",
    # "Chai Waala",
    # "Agnes Uds",
]

# Legacy single-string config still works.
TARGET_GROUP = None  # e.g. "Anuraag Saarland"; overrides TARGET_GROUPS if set.

POLL_INTERVAL_SEC = 2.0
REPLY_MIN_DELAY = 2.0
REPLY_MAX_DELAY = 4.5
HEARTBEAT_EVERY_N_POLLS = 15  # ~30s with POLL_INTERVAL_SEC=2.0


def _resolve_targets():
    """List of chat names to watch, honoring legacy TARGET_GROUP."""
    if isinstance(TARGET_GROUP, str) and TARGET_GROUP.strip():
        return [TARGET_GROUP.strip()]
    return [t.strip() for t in TARGET_GROUPS if t and t.strip()]


# -------------------- LLM --------------------

def ask_local_llm(user_message):
    """Send the message to local Ollama and return its reply (empty on failure)."""
    prompt = (
        "You are a helpful, brief personal assistant. Reply to this casual chat "
        "message naturally. Keep it under 2 sentences:\n\n"
        f"Message: {user_message}\nReply:"
    )
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=60,
        )
    except requests.exceptions.ConnectionError:
        print("❌ Ollama not reachable at", OLLAMA_API_URL,
              "— is `ollama serve` running?")
        return ""
    except requests.exceptions.Timeout:
        print("❌ Ollama request timed out (60s). Model may be too large for your RAM.")
        return ""
    except Exception as e:
        print(f"❌ Error communicating with local LLM: {e}")
        return ""

    if response.status_code != 200:
        print(f"❌ Ollama HTTP {response.status_code}: {response.text[:300]}")
        return ""

    try:
        data = response.json()
    except ValueError:
        print(f"❌ Ollama returned non-JSON: {response.text[:300]}")
        return ""

    if "error" in data:
        err = data["error"]
        print(f"❌ Ollama error: {err}")
        if "memory" in err.lower():
            print("   → Try a smaller model: `ollama pull gemma3:1b` "
                  "or `ollama pull llama3.2:1b`, then set MODEL_NAME accordingly.")
            print("   → Or close other apps to free RAM (~4 GB needed for gemma3:4b).")
        return ""

    reply = (data.get("response") or "").strip()
    if not reply:
        print(f"⚠️ Ollama returned empty response. Full payload: {data}")
    return reply


# -------------------- typing & inputs --------------------

def human_type_focused(page, text):
    """Type into the currently focused element with human-ish keystroke timing."""
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.05, 0.15))


_FIND_INPUT_JS = r"""
(keywords) => {
    const wanted = keywords.map(k => k.toLowerCase());
    const nodes = Array.from(document.querySelectorAll(
        'input[role="textbox"], input[type="text"], input[type="search"], '
        + '[contenteditable="true"], [role="textbox"]'
    ));
    for (const el of nodes) {
        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
        const placeholder = (
            el.getAttribute('data-placeholder')
            || el.getAttribute('placeholder')
            || el.getAttribute('title')
            || ''
        ).toLowerCase();
        if (wanted.some(w => (aria + ' ' + placeholder).includes(w))) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                el.scrollIntoView({block: 'center'});
                return {found: true};
            }
        }
    }
    return {found: false};
}
"""

_FOCUS_INPUT_JS = r"""
(keywords) => {
    const wanted = keywords.map(k => k.toLowerCase());
    const nodes = Array.from(document.querySelectorAll(
        'input[role="textbox"], input[type="text"], input[type="search"], '
        + '[contenteditable="true"], [role="textbox"]'
    ));
    for (const el of nodes) {
        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
        const placeholder = (
            el.getAttribute('data-placeholder')
            || el.getAttribute('placeholder')
            || ''
        ).toLowerCase();
        if (wanted.some(w => (aria + ' ' + placeholder).includes(w))) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                el.focus();
                el.click();
                return true;
            }
        }
    }
    return false;
}
"""

SEARCH_KEYWORDS = [
    "search or start", "search input", "search chats", "search",
    "suchen", "neuen chat", "chat beginnen",
]
COMPOSE_KEYWORDS = [
    "type a message", "type message", "message",
    "nachricht", "schreiben",
]


def focus_search_box(page, timeout_ms=15000):
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        info = page.evaluate(_FIND_INPUT_JS, SEARCH_KEYWORDS)
        if info and info.get("found"):
            page.evaluate(_FOCUS_INPUT_JS, SEARCH_KEYWORDS)
            return True
        time.sleep(0.3)
    return False


def focus_compose_box(page, timeout_ms=10000, group_name=None):
    deadline = time.time() + timeout_ms / 1000.0
    keywords = list(COMPOSE_KEYWORDS)
    if group_name:
        keywords.append(group_name.lower())
    while time.time() < deadline:
        if page.evaluate(_FOCUS_INPUT_JS, keywords):
            return True
        focused = page.evaluate(
            """() => {
                const footer = document.querySelector('footer') || document;
                const nodes = Array.from(footer.querySelectorAll(
                    'input[role="textbox"], [contenteditable="true"], [role="textbox"]'
                ));
                for (const el of nodes) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        el.focus();
                        el.click();
                        return true;
                    }
                }
                return false;
            }"""
        )
        if focused:
            return True
        time.sleep(0.3)
    return False


def dump_editables(page):
    info = page.evaluate(
        """() => {
            const nodes = Array.from(document.querySelectorAll(
                'input[role="textbox"], input[type="text"], '
                + '[contenteditable="true"], [role="textbox"]'
            ));
            return nodes.map(el => {
                const rect = el.getBoundingClientRect();
                return {
                    tag: el.tagName,
                    aria: el.getAttribute('aria-label') || '',
                    placeholder: el.getAttribute('data-placeholder') || '',
                    role: el.getAttribute('role') || '',
                    visible: rect.width > 0 && rect.height > 0,
                };
            });
        }"""
    )
    print("🔍 Editable elements on page:")
    for i, e in enumerate(info or []):
        print(
            f"   [{i}] {e['tag']} role={e['role']!r} "
            f"aria={e['aria']!r} placeholder={e['placeholder']!r} visible={e['visible']}"
        )


# -------------------- chat detection & opening --------------------

def in_target_chat(page, name):
    """True iff the conversation header (#main) shows `name`."""
    selectors = [
        f'#main header span[title="{name}"]',
        f'header span[title="{name}"]',
        f'div[data-testid="conversation-info-header"] span[title="{name}"]',
    ]
    for sel in selectors:
        try:
            if page.locator(sel).first.count() > 0:
                return True
        except Exception:
            continue
    return False


def already_in_target_chat(page, name):
    if in_target_chat(page, name):
        return True
    name_l = name.lower()
    return bool(page.evaluate(
        """(groupName) => {
            const nodes = Array.from(document.querySelectorAll(
                'footer input[role="textbox"], footer [contenteditable="true"], footer [role="textbox"]'
            ));
            for (const el of nodes) {
                const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                if (aria.includes(groupName)) return true;
            }
            return false;
        }""",
        name_l,
    ))


# WhatsApp header contains both the contact name AND a status line ("online",
# "last seen…", "typing…"). querySelector returns the status first if we're
# not careful — this JS filters those out and prefers an allowlisted name.
_CURRENT_CHAT_JS = r"""
(targets) => {
    const allowed = new Set(targets || []);
    function isStatus(t) {
        const s = (t || '').toLowerCase().trim();
        if (!s) return true;
        if (s === 'online' || s === 'offline') return true;
        if (s.startsWith('last seen') || s.includes('zuletzt')) return true;
        if (s.includes('typing') || s.includes('schreibt')) return true;
        if (s.includes('recording') || s.includes('nimmt auf')) return true;
        if (/^\d{1,2}:\d{2}/.test(s)) return true;
        return false;
    }
    const header = document.querySelector('#main header')
        || document.querySelector('header');
    if (!header) return null;
    const titles = Array.from(header.querySelectorAll('span[title]'))
        .map(el => el.getAttribute('title'))
        .filter(t => t && !isStatus(t));
    for (const t of titles) {
        if (allowed.has(t)) return t;
    }
    return titles[0] || null;
}
"""


def current_chat_name(page, targets=None):
    try:
        return page.evaluate(_CURRENT_CHAT_JS, list(targets or []))
    except Exception:
        return None


def resolve_active_chat(page, targets):
    """Return the allowlisted chat that is currently open, or None."""
    name = current_chat_name(page, targets)
    if name and name in set(targets):
        return name
    for t in targets:
        try:
            if already_in_target_chat(page, t):
                return t
        except Exception:
            continue
    return None


def open_chat(page, name):
    """Search for `name` in the sidebar and open it."""
    if already_in_target_chat(page, name):
        print(f"✅ Already in chat: {name!r}")
        return
    if not focus_search_box(page):
        dump_editables(page)
        raise RuntimeError(
            "Could not find WhatsApp search box. Update keyword list "
            "in focus_search_box() if WhatsApp Web changed."
        )
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.keyboard.type(name, delay=40)
    page.wait_for_timeout(900)

    candidates = [
        f'#pane-side span[title="{name}"]',
        f'div[role="listitem"] span[title="{name}"]',
        f'span[title="{name}"]',
    ]
    result = None
    for sel in candidates:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=4000)
            result = loc
            break
        except PWTimeout:
            continue
    if result is None:
        raise RuntimeError(
            f"No chat titled exactly {name!r} found in sidebar. "
            "Check spelling/case in TARGET_GROUPS."
        )
    result.click()
    page.wait_for_timeout(800)
    try:
        page.locator(f'header span[title="{name}"]').wait_for(timeout=5000)
        print(f"✅ Opened chat: {name!r}")
    except PWTimeout:
        print(f"⚠️ Could not verify chat header for {name!r}; continuing anyway.")


# JS to find a sidebar chat that (a) is in our allowlist AND (b) has an unread
# badge. Non-allowlisted chats are NEVER returned, even if they are unread.
_FIND_UNREAD_TARGET_JS = r"""
(targets) => {
    const allowed = new Set(targets);
    const items = Array.from(document.querySelectorAll(
        '#pane-side div[role="listitem"], #pane-side [role="row"], '
        + '#pane-side [role="gridcell"]'
    ));
    for (const item of items) {
        const titleEl = item.querySelector('span[title]');
        if (!titleEl) continue;
        const name = titleEl.getAttribute('title');
        if (!allowed.has(name)) continue;
        const labeled = item.querySelectorAll('[aria-label]');
        for (const b of labeled) {
            const al = (b.getAttribute('aria-label') || '').toLowerCase();
            if (al.includes('unread') || al.includes('ungelesen')) {
                return name;
            }
        }
    }
    return null;
}
"""


def find_unread_allowlisted(page, targets):
    if not targets:
        return None
    try:
        return page.evaluate(_FIND_UNREAD_TARGET_JS, list(targets))
    except Exception:
        return None


# -------------------- message extraction --------------------

_MEDIA_NOISE_SUBSTRINGS = (
    "view once", "photo", "video", "sticker", "voice message", "audio",
    "gif", "document",
    "this message was deleted", "this message has been deleted",
    "you deleted this message", "missed voice call", "missed video call",
    "fotografie", "sprachnachricht", "videoanruf",
    "diese nachricht wurde gelöscht", "verpasster anruf",
)


def _clean_text(raw):
    lines = []
    for line in (raw or "").splitlines():
        s = line.strip().strip("\u200e\u202a\u202c").strip()
        if not s:
            continue
        if (len(s) <= 7
                and s.replace(":", "").replace(".", "").replace(" ", "").isdigit()):
            continue
        lines.append(s)
    return "\n".join(lines).strip()


# 2025–2026 WhatsApp Web: text lives in span[data-testid="selectable-text"]
# inside div._akbu. Quoted replies (`data-testid="quoted-message"`) must be skipped.
_EXTRACT_INBOUND_TEXT_JS = r"""
(el) => {
    const skipQuoted = (node) => !!node.closest('[data-testid="quoted-message"]');
    const isTime = (t) => /^\d{1,2}:\d{2}(\s*[AP]M)?$/i.test(t.trim());
    const isNoise = (t) => t === 'Du' || t === 'You';

    const pick = (nodes) => {
        const parts = [];
        for (const s of nodes) {
            if (skipQuoted(s)) continue;
            if (s.classList && s.classList.contains('quoted-mention')) continue;
            const t = (s.innerText || '').trim();
            if (!t || isTime(t) || isNoise(t)) continue;
            parts.push(t);
        }
        return parts.length ? parts[parts.length - 1] : '';
    };

    const body = el.querySelector('div._akbu');
    if (body) {
        const fromTestId = pick(body.querySelectorAll('span[data-testid="selectable-text"]'));
        if (fromTestId) return fromTestId;
        const lines = (body.innerText || '').split('\n')
            .map(l => l.trim()).filter(l => l && !isTime(l) && !isNoise(l));
        if (lines.length) return lines.join(' ');
    }

    const fromAll = pick(el.querySelectorAll('span[data-testid="selectable-text"]'));
    if (fromAll) return fromAll;

    for (const sel of ['span.selectable-text', 'div.selectable-text']) {
        const t = pick(el.querySelectorAll(sel));
        if (t) return t;
    }
    return '';
}
"""


def extract_message_text(message_loc):
    """Best-effort plain text from an inbound message bubble. Empty on media."""
    try:
        raw = message_loc.evaluate(_EXTRACT_INBOUND_TEXT_JS)
        text = _clean_text(raw)
        if text:
            lower = text.lower()
            if any(noise in lower for noise in _MEDIA_NOISE_SUBSTRINGS):
                return ""
            return text
    except Exception:
        pass
    # Fallbacks (Playwright-only path)
    try:
        body = message_loc.locator("div._akbu").first
        if body.count() > 0:
            loc = body.locator('span[data-testid="selectable-text"]').first
            if loc.count() > 0:
                text = _clean_text(loc.inner_text(timeout=1500))
                if text:
                    return text
    except Exception:
        pass
    try:
        locs = message_loc.locator(
            'span[data-testid="selectable-text"]:not(.quoted-mention)'
        )
        for i in range(locs.count() - 1, -1, -1):
            text = _clean_text(locs.nth(i).inner_text(timeout=1500))
            if text:
                return text
    except Exception:
        pass
    return ""


def debug_dump_bubble(message_loc, label="bubble"):
    try:
        raw = message_loc.inner_text(timeout=2000)
        print(f"🔬 {label} inner_text:\n{raw!r}")
    except Exception as exc:
        print(f"🔬 {label} inner_text: <failed: {exc}>")
    try:
        html = message_loc.evaluate("el => el.outerHTML")
        print(f"🔬 {label} outerHTML (first 800 chars):\n{html[:800]}")
    except Exception as exc:
        print(f"🔬 {label} outerHTML: <failed: {exc}>")


def count_inbound(page):
    """Approximate count of inbound bubbles currently rendered."""
    try:
        n = page.locator("div.message-in").count()
        if n > 0:
            return n
    except Exception:
        pass
    try:
        return page.locator('#main div[role="row"]:has(div.message-in)').count()
    except Exception:
        return 0


def latest_inbound(page):
    """Return (Locator, count) for the most recent inbound bubble in the DOM."""
    for sel in ["div.message-in", '#main div[role="row"] div.message-in']:
        try:
            loc = page.locator(sel)
            count = loc.count()
            if count > 0:
                return loc.nth(count - 1), count
        except Exception:
            continue
    return None, 0


# Returns a stable identifier for the most recent inbound message.
# WhatsApp Web virtualizes the DOM (old bubbles unmount as you scroll), so
# counting bubbles is unreliable. Instead we identify the latest inbound
# bubble by `data-pre-plain-text` (e.g. "[17:35, 1.6.2026] Agnes Uds: ")
# plus a hash of its text. When this signature changes, a new message arrived.
_LATEST_INBOUND_SIG_JS = r"""
() => {
    const bubbles = document.querySelectorAll('div.message-in');
    if (!bubbles.length) return null;
    const last = bubbles[bubbles.length - 1];

    // 1) data-pre-plain-text holds "[time, date] sender: "
    const pre = last.querySelector('[data-pre-plain-text]');
    const meta = pre ? pre.getAttribute('data-pre-plain-text') || '' : '';

    // 2) text fingerprint (first 120 chars, normalized)
    let txt = '';
    const sel = last.querySelector('span[data-testid="selectable-text"]')
        || last.querySelector('span.selectable-text')
        || last;
    if (sel) txt = (sel.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120);

    // 3) DOM-row data-id, if present (sometimes WhatsApp adds one)
    const row = last.closest('[data-id]');
    const rowId = row ? row.getAttribute('data-id') || '' : '';

    if (!meta && !txt && !rowId) return null;
    return rowId + '|' + meta + '|' + txt;
}
"""


def latest_inbound_signature(page):
    """Stable signature of the most recent inbound bubble, or None."""
    try:
        return page.evaluate(_LATEST_INBOUND_SIG_JS)
    except Exception:
        return None


# -------------------- main loop --------------------

def run_bot():
    targets = _resolve_targets()
    if not targets:
        raise SystemExit(
            "No chats configured. Add at least one name to TARGET_GROUPS "
            "(or set TARGET_GROUP) at the top of whatsapp_bot.py."
        )

    with sync_playwright() as p:
        print("🚀 Starting browser...")
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            args=["--start-maximized"],
        )

        page = context.pages[0]
        page.goto("https://web.whatsapp.com")

        print("⏳ Waiting for WhatsApp Web to load. (Scan QR code if prompted)...")
        page.wait_for_selector(
            "#side, div[data-testid='chat-list']", timeout=120000
        )
        print("✅ Logged in successfully!")

        print(f"🎯 Watching {len(targets)} chat(s): {targets}")
        first = targets[0]
        print(f"🎯 Opening initial chat: {first!r}")
        open_chat(page, first)

        # Track the *identity* of the latest inbound msg per chat, not a count.
        # Counts are unreliable because WhatsApp Web virtualizes the DOM —
        # old bubbles unmount as you scroll, so the count goes up AND down.
        last_sig = {first: latest_inbound_signature(page)}
        print(
            f"🤖 Bot is active. Allowlist only: {targets}. "
            f"Ignoring everything up to current state in {first!r}."
        )
        poll_tick = 0
        active = first

        while True:
            try:
                # 1) Prefer any allowlisted chat with an unread badge.
                unread = find_unread_allowlisted(page, targets)
                if unread and unread != active:
                    print(f"📬 Unread in {unread!r}; switching.")
                    open_chat(page, unread)
                    active = unread
                    if active not in last_sig:
                        last_sig[active] = latest_inbound_signature(page)
                        print(
                            f"📚 First visit to {active!r}; "
                            "ignoring prior messages."
                        )
                        time.sleep(POLL_INTERVAL_SEC)
                        continue

                # 2) Make sure the visible chat is allowlisted.
                resolved = resolve_active_chat(page, targets)
                if not resolved:
                    stray = current_chat_name(page, targets)
                    if stray and stray not in set(targets):
                        print(
                            f"🙈 Stray chat {stray!r} is NOT allowlisted — parking."
                        )
                    open_chat(page, first)
                    active = first
                    if active not in last_sig:
                        last_sig[active] = latest_inbound_signature(page)
                    time.sleep(POLL_INTERVAL_SEC)
                    continue
                active = resolved

                # 3) Watch for a new latest-inbound signature in the active chat.
                sig = latest_inbound_signature(page)
                if sig is None or sig == last_sig.get(active):
                    poll_tick += 1
                    if poll_tick % HEARTBEAT_EVERY_N_POLLS == 0:
                        print(
                            f"💓 watching {active!r} — no new message yet"
                            f" ({count_inbound(page)} rendered)…"
                        )
                    time.sleep(POLL_INTERVAL_SEC)
                    continue

                new_msg, _ = latest_inbound(page)
                if new_msg is None:
                    print(
                        "⚠️ Signature changed but no inbound element found "
                        "(selector mismatch?). Skipping."
                    )
                    last_sig[active] = sig
                    continue
                text = extract_message_text(new_msg)
                last_sig[active] = sig

                if not text:
                    print(f"📩 New message in {active!r} — text extraction failed.")
                    debug_dump_bubble(new_msg, label=f"{active} bubble")
                    continue

                print(f"📩 New message in {active!r}: {text!r}")
                print("🧠 Thinking (Local LLM)...")
                reply = ask_local_llm(text)
                if not reply:
                    print("⚠️ Empty LLM reply; skipping.")
                    continue

                print(f"🤖 AI Response: {reply!r}")
                time.sleep(random.uniform(REPLY_MIN_DELAY, REPLY_MAX_DELAY))

                # Re-verify before sending.
                resolved_now = resolve_active_chat(page, targets)
                if not resolved_now:
                    print("↩️ Left allowlisted chat before send; aborting.")
                    continue
                if resolved_now != active:
                    print(f"↪️ Chat switched to {resolved_now!r}; sending there.")
                    active = resolved_now

                if not focus_compose_box(page, group_name=active):
                    dump_editables(page)
                    print("⚠️ Could not focus compose box; skipping reply.")
                    continue
                human_type_focused(page, reply)
                page.keyboard.press("Enter")
                print(f"📤 Reply sent to {active!r}.")

                last_sig[active] = latest_inbound_signature(page)
                time.sleep(POLL_INTERVAL_SEC)

            except Exception as loop_error:
                print(f"⚠️ Loop Warning: {loop_error}")
                time.sleep(5)


if __name__ == "__main__":
    run_bot()
