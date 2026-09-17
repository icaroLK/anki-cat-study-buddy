"""
🐱︎ Cat Study Buddy ᗢᘏᓗ
A tiny virtual cat that changes its mood based on your Anki reviews in the day

Its mood ladder is driven by today's card count (thresholds are configurable via Tools -> 🐱︎ Cat Study Buddy ᗢᘏᓗ):
  - 0 cards                        -> Empty
  - 1 card .. mood_neutral_at      -> Sad
  - .. mood_happy_at               -> Neutral
  - .. mood_excited_at             -> Happy
  - beyond mood_excited_at         -> Excited

The "day" follows Anki's day cutoff (e.g. 4am rollover).
"""

import base64
import json
import os
import random
import time
from datetime import date

from aqt import mw, gui_hooks
from aqt.qt import (
    QAction,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

ADDON_DIR = os.path.dirname(__file__)
USER_FILES = os.path.join(ADDON_DIR, "user_files")
STATE_PATH = os.path.join(USER_FILES, "state.json")
ADDON_NAME = "🐱︎ Cat Study Buddy ᗢᘏᓗ"

# ---------------------------------------------------------------------------
# Tunables: change these and restart Anki to test different timing/feel.
# ---------------------------------------------------------------------------
FRAME_SECONDS = 0.13          # playback time per sprite frame (all animations)
SWAP_INTERVAL_MIN_MS = 5000   # shortest gap before the cat picks a new pose
SWAP_INTERVAL_MAX_MS = 10000  # longest gap before the cat picks a new pose
REACTION_HOLD_MS = 2000       # minimum time an in-review reaction stays up

# Deck-browser easter eggs (clicking/holding the cat directly).
EASTER_CLICK_COUNT = 5        # this many clicks...
EASTER_CLICK_WINDOW_MS = 1500  # ...within this many ms of each other
EASTER_EXCITED_HOLD_MS = 2000  # how long the forced "excited" pose stays up
EASTER_HOLD_MS = 3000          # press-and-hold duration that triggers "sleep"

# ---------------------------------------------------------------------------
# Mochi pixel-art
# All frames are 32x32; "loop" animations play continuously, others hold on their last frame.
# Each name maps to (basename, frame_count, loop) the actual file resolved per the selected pet_color (img/<basename>.png for "classical", else img/<basename>_<color>.png).
# ---------------------------------------------------------------------------
SPRITE_FILES = {
    # neutral
    "idle": ("MochiIdle", 10, True),
    "idle2": ("MochiIdle2", 10, True),
    "waiting": ("MochiWaiting", 6, True),
    "laydown": ("MochiLayDown", 12, True),
    "sleep": ("MochiSleep", 4, True),
    # sad
    "cry": ("MochiCry", 4, True),
    "sad": ("MochiSad", 9, True),
    # happy
    "excited": ("MochiExcited", 12, True),
    "dance": ("MochiDance", 4, True),
    "surprised": ("MochiSurprised", 12, True),
    # actions
    "sleepy": ("MochiSleepy", 8, True),
    "bathtub": ("MochiBathtub", 7, True),
    "eating": ("MochiEating", 15, True),
    "box1": ("MochiBox1", 4, True),
    "box2": ("MochiBox2", 12, True),
    "box3": ("MochiBox3", 4, True),
    # exaggerated
    "sick1": ("MochiSick1", 5, True),
    "sick2": ("MochiSick2", 4, True),
    "dead": ("MochiDead", 1, False),
}


ANIMATION_CATEGORIES = {
    "neutral": ["idle", "idle2", "waiting", "laydown", "sleep"],
    "sad": ["cry", "sad"],
    "happy": ["excited", "dance", "surprised"],
    "actions": ["sleepy", "bathtub", "eating", "box1", "box2", "box3"],
    "exaggerated": ["sick1", "sick2", "dead"],
}


def _animations(*categories: str) -> list:
    """Flatten one or more ANIMATION_CATEGORIES into a single pool."""
    names = []
    for cat in categories:
        names.extend(ANIMATION_CATEGORIES[cat])
    return names


# In-review reactions: base state is always one of MINI_IDLE_POOL, independent of the day's overall mood. 
# Every single answer plays a one-shot reaction (good pool if not "Again", bad pool if "Again"), held for REACTION_HOLD_MS, then returns to a fresh idle pick.
MINI_IDLE_POOL = _animations("neutral")
REACTION_POOL_GOOD = _animations("happy")
REACTION_POOL_BAD = _animations("exaggerated", "sad")

PET_COLORS = ["classical", "orange", "grey", "white"]
COLOR_LABELS = {
    "classical": "Classical (cream)",
    "orange": "Orange",
    "grey": "Grey",
    "white": "White",
}

_sprite_data_uri_cache = {}


def _sprite_data_uri(path: str) -> str:
    if path not in _sprite_data_uri_cache:
        with open(path, "rb") as f:
            _sprite_data_uri_cache[path] = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    return _sprite_data_uri_cache[path]


def _sprite_path(basename: str, color: str) -> str:
    suffix = "" if color == "classical" else f"_{color}"
    path = os.path.join(ADDON_DIR, "img", f"{basename}{suffix}.png")
    if not os.path.exists(path):
        path = os.path.join(ADDON_DIR, "img", f"{basename}.png")  # fall back to classical
    return path


def sprite_html(name: str, width: int = 220, color: str = "classical") -> str:
    """Render one of the named Mochi sprite animations in the given color."""
    basename, frames, loop = SPRITE_FILES[name]
    path = _sprite_path(basename, color)
    scale = width / 32
    height = 32 * scale
    base_style = (
        f"width:{width}px; height:{height}px; margin:0 auto; "
        f"background-image:url({_sprite_data_uri(path)}); "
        f"background-repeat:no-repeat; image-rendering:pixelated;"
    )
    if frames <= 1:
        return f'<div style="{base_style} background-size:{width}px {height}px; background-position:0 0;"></div>'

    sheet_width = 32 * frames * scale
    duration = round(frames * FRAME_SECONDS, 2)
    anim_mode = "infinite" if loop else "1 forwards"
    keyframe_name = f"studybuddySprite_{name}"
    return f"""
<div style="{base_style} background-size:{sheet_width}px {height}px;
            animation:{keyframe_name} {duration}s steps({frames}) {anim_mode};"></div>
<style>
@keyframes {keyframe_name} {{
  from {{ background-position: 0 0; }}
  to {{ background-position: -{sheet_width}px 0; }}
}}
</style>"""


# ---------------------------------------------------------------------------
# Mood ladder (today's-cards -> label/color/animations). Thresholds come from config so they're user-adjustable.
# ---------------------------------------------------------------------------
def _all_mood_tiers(cfg: dict) -> list:
    neutral_at = max(1, int(cfg.get("mood_neutral_at", DEFAULT_CONFIG["mood_neutral_at"])))
    happy_at = max(neutral_at + 1, int(cfg.get("mood_happy_at", DEFAULT_CONFIG["mood_happy_at"])))
    excited_at = max(happy_at + 1, int(cfg.get("mood_excited_at", DEFAULT_CONFIG["mood_excited_at"])))
    return [
        {"min": 0, "max": 1, "key": "dead", "label": "Empty", "emoji": "💤", "color": "#7F8C8D", "pct": (0, 0), "pool": _animations("exaggerated")},
        {"min": 1, "max": neutral_at + 1, "key": "sad", "label": "Sad", "emoji": "😿", "color": "#E74C3C", "pct": (5, 30), "pool": _animations("sad")},
        {"min": neutral_at + 1, "max": happy_at + 1, "key": "neutral", "label": "Neutral", "emoji": "😐", "color": "#3498DB", "pct": (30, 60), "pool": _animations("neutral")},
        {"min": happy_at + 1, "max": excited_at + 1, "key": "happy", "label": "Happy", "emoji": "😻", "color": "#2ECC71", "pct": (60, 90), "pool": _animations("neutral", "actions")},
        {"min": excited_at + 1, "max": None, "key": "excited", "label": "Excited", "emoji": "🤩", "color": "#F1C40F", "pct": (100, 100), "pool": _animations("happy")},
    ]


def _current_mood_tier(cfg: dict, reviews: int) -> dict:
    tiers = _all_mood_tiers(cfg)
    for t in tiers:
        if (t["max"] is None or reviews < t["max"]) and reviews >= t["min"]:
            return t
    return tiers[-1]


def _mood_bar_percent(tier: dict, reviews: int) -> int:
    lo, hi = tier["pct"]
    if tier["max"] is None or lo == hi:
        return hi
    span = tier["max"] - tier["min"]
    frac = max(0.0, min(1.0, (reviews - tier["min"]) / span)) if span else 0.0
    return int(lo + (hi - lo) * frac)


DEFAULT_CONFIG = {
    "pet_name": "Mochi",
    "pet_color": "classical",
    "pet_color_random": False,
    "mood_neutral_at": 50,
    "mood_happy_at": 100,
    "mood_excited_at": 200,
    "sprite_size": 100,
    "show_during_review": True,
    "show_mood_bar": True,
}


# ---------------------------------------------------------------------------
# Config + daily state
# ---------------------------------------------------------------------------
def get_config() -> dict:
    cfg = mw.addonManager.getConfig(__name__) or {}
    merged = dict(DEFAULT_CONFIG)
    merged.update(cfg)
    return merged


def save_config(cfg: dict) -> None:
    mw.addonManager.writeConfig(__name__, cfg)


def _today() -> dict:
    """Current day as {'scheme': ..., 'num': ...}. Uses Anki's scheduling day
    (respects the day cutoff, e.g. 4am) when the collection is open."""
    try:
        if mw.col is not None:
            return {"scheme": "anki", "num": int(mw.col.sched.today)}
    except Exception:
        pass
    return {"scheme": "cal", "num": date.today().toordinal()}


def _count_todays_reviews_from_history() -> dict:
    """Reconstruct today's review count/streak from Anki's actual revlog
    (respecting the day-cutoff), so a fresh state doesn't lose reviews you
    already did before this addon started counting them (first install,
    profile switch, cards synced in from mobile/AnkiWeb, etc.)."""
    empty = {"reviews": 0, "correct": 0, "streak": 0, "best_streak": 0}
    try:
        if mw.col is None:
            return empty
        cutoff = int(mw.col.sched.day_cutoff)
        start_ms = (cutoff - 86400) * 1000
        end_ms = cutoff * 1000
        eases = mw.col.db.list(
            "select ease from revlog where id >= ? and id < ? and ease > 0 order by id asc",
            start_ms, end_ms,
        )
    except Exception:
        return empty

    correct = streak = best_streak = 0
    for ease in eases:
        if ease == 1:
            streak = 0
        else:
            correct += 1
            streak += 1
            best_streak = max(best_streak, streak)
    return {"reviews": len(eases), "correct": correct, "streak": streak, "best_streak": best_streak}


def _reconcile_today_after_sync() -> None:
    """Reviews done on phone/AnkiWeb only land in the local revlog once a
    sync completes. If the deck browser already rendered (and backfilled
    today's count) before that sync finished, today's count would stay
    stuck too low for the rest of the day with nothing to re-check it.
    Re-run the same revlog backfill now and adopt it if it shows more than
    what's already stored."""
    try:
        if mw.col is None:
            return
        state = load_state()
        if state.get("day") != _today():
            return  # a day boundary already turned over; load_state() handled it
        backfill = _count_todays_reviews_from_history()
        if backfill["reviews"] <= int(state.get("reviews", 0)):
            return
        state["reviews"] = backfill["reviews"]
        state["correct"] = backfill["correct"]
        state["streak"] = backfill["streak"]
        state["best_streak"] = max(int(state.get("best_streak", 0)), backfill["best_streak"])
        save_state(state)
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()
    except Exception:
        pass


def _fresh_state() -> dict:
    today = _today()
    backfill = _count_todays_reviews_from_history()
    return {
        "day": today,
        "reviews": backfill["reviews"],
        "correct": backfill["correct"],
        "streak": backfill["streak"],
        "best_streak": backfill["best_streak"],
    }


_STATE_DEFAULTS = {
    "reviews": 0,
    "correct": 0,
    "streak": 0,
    "best_streak": 0,
}


def load_state() -> dict:
    state = {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}

    today = _today()
    old_day = state.get("day")

    if not isinstance(old_day, dict) or old_day != today:
        # first run, legacy state, or a new day -> today starts completely fresh
        state = _fresh_state()
        save_state(state)
        return state

    for k, v in _STATE_DEFAULTS.items():
        state.setdefault(k, v)
    state.setdefault("day", today)
    return state


def save_state(state: dict) -> None:
    os.makedirs(USER_FILES, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


# ---------------------------------------------------------------------------
# Deck browser rendering
# ---------------------------------------------------------------------------
def render_pet_html() -> str:
    cfg = get_config()
    state = load_state()
    name = cfg["pet_name"]
    r = int(state["reviews"])
    color = cfg.get("pet_color", "classical")
    size = int(cfg.get("sprite_size", DEFAULT_CONFIG["sprite_size"]))

    tier = _current_mood_tier(cfg, r)
    label, emoji, bar_color = tier["label"], tier["emoji"], tier["color"]
    pct = _mood_bar_percent(tier, r)
    candidates = tier["pool"]

    mood = f"{emoji} {name}'s mood: {label}"
    initial = random.choice(candidates)
    box_id = f"studybuddy-pet-{random.randint(0, 10**9)}"

    # Easter eggs (5-fast-clicks -> excited, hold 3s -> sleep) need "excited"
    # and "sleep" available to reveal even when the current mood pool doesn't
    # include them.
    extra_names = [n for n in ("excited", "sleep") if n not in candidates]
    all_names = candidates + extra_names
    variants = "".join(
        f'<div class="studybuddy-variant" data-name="{nm}" style="display:{"block" if nm == initial else "none"}">'
        f'{sprite_html(nm, width=size, color=color)}</div>'
        for nm in all_names
    )

    mood_names_json = json.dumps(candidates)
    cycle_script = f"""
<script>
(function(){{
  var box = document.getElementById('{box_id}');
  if (!box) return;
  var variants = {{}};
  box.querySelectorAll('.studybuddy-variant').forEach(function(v){{ variants[v.dataset.name] = v; }});
  var moodNames = {mood_names_json};
  var current = '{initial}';
  var token = 0;

  function show(name){{
    Object.keys(variants).forEach(function(k){{ variants[k].style.display = (k === name) ? 'block' : 'none'; }});
    current = name;
  }}

  function scheduleTick(){{
    var myToken = ++token;
    setTimeout(function(){{
      if (myToken !== token) return;
      var pool = moodNames.filter(function(n){{ return n !== current; }});
      var next = pool.length ? pool[Math.floor(Math.random() * pool.length)] : moodNames[0];
      show(next);
      scheduleTick();
    }}, {SWAP_INTERVAL_MIN_MS} + Math.random() * {SWAP_INTERVAL_MAX_MS - SWAP_INTERVAL_MIN_MS});
  }}
  if (moodNames.length > 1) scheduleTick();

  function resumeMood(){{
    ++token;
    var pick = moodNames[Math.floor(Math.random() * moodNames.length)];
    show(pick);
    scheduleTick();
  }}

  var clickTimes = [];
  box.addEventListener('click', function(){{
    var now = Date.now();
    clickTimes.push(now);
    clickTimes = clickTimes.filter(function(t){{ return now - t <= {EASTER_CLICK_WINDOW_MS}; }});
    if (clickTimes.length >= {EASTER_CLICK_COUNT}) {{
      clickTimes = [];
      ++token;
      show('excited');
      var myToken = token;
      setTimeout(function(){{ if (myToken === token) resumeMood(); }}, {EASTER_EXCITED_HOLD_MS});
    }}
  }});

  var holding = false;
  var pressTimer = null;
  box.addEventListener('mousedown', function(){{
    holding = false;
    pressTimer = setTimeout(function(){{
      holding = true;
      ++token;
      show('sleep');
    }}, {EASTER_HOLD_MS});
  }});
  function endPress(){{
    clearTimeout(pressTimer);
    if (holding) {{ holding = false; resumeMood(); }}
  }}
  box.addEventListener('mouseup', endPress);
  box.addEventListener('mouseleave', endPress);
}})();
</script>"""

    mood_block = ""
    if cfg.get("show_mood_bar", True):
        mood_block = f"""
  <div style="font-size:12px; margin:2px 0 6px;">{mood}</div>
  <div style="background:rgba(127,127,127,0.25); border-radius:6px; height:9px; overflow:hidden;">
    <div style="width:{pct}%; height:100%; background:{bar_color}; transition:width 0.4s ease;"></div>
  </div>
  <div style="font-size:10px; margin-top:4px; opacity:0.8;">{r} cards today</div>"""

    box_width = max(size, 160) + 40
    return f"""
<div style="text-align:center; margin:12px auto 6px; max-width:{box_width}px; padding:10px 12px;
            border-radius:12px; background:transparent;">
  <div id="{box_id}">{variants}</div>
  {cycle_script}
  {mood_block}
</div>"""


def on_deck_browser_render(deck_browser, content) -> None:
    content.stats += render_pet_html()


# ---------------------------------------------------------------------------
# Mini cat shown during reviews
# ---------------------------------------------------------------------------
# While actively reviewing, the cat's base pose is always one of MINI_IDLE_POOL (independent of the day's overall mood). 
# A reaction animation can briefly override it (see on_answer/animate_reaction), and _mini_reaction_until tells on_show_question not to stomp on a reaction that's still playing out.
_mini_reaction_until = 0.0


def _mini_html(force_name: str = None) -> str:
    cfg = get_config()
    color = cfg.get("pet_color", "classical")
    name = force_name or random.choice(MINI_IDLE_POOL)
    svg = sprite_html(name, width=100, color=color)
    return f"<div>{svg}</div>"


_ENSURE_MINI_EL_JS = (
    "var el = document.getElementById('studybuddy-mini');"
    "if(!el){"
    "el = document.createElement('div');"
    "el.id = 'studybuddy-mini';"
    "el.style.cssText = 'position:fixed;bottom:6px;right:10px;z-index:999;"
    "text-align:center;opacity:0.9;pointer-events:none;font-size:11px;line-height:1.2;';"
    "document.body.appendChild(el);"
    "}"
)


def _eval_in_reviewer(js: str) -> None:
    try:
        mw.reviewer.web.eval(js)
    except Exception:
        pass


def _mini_pet_active() -> bool:
    if not get_config().get("show_during_review", True):
        return False
    return mw.state == "review" and bool(getattr(mw, "reviewer", None))


def show_idle_pet() -> None:
    """Refresh the mini cat to a fresh idle pose, right now."""
    if not _mini_pet_active():
        return
    global _mini_reaction_until
    _mini_reaction_until = 0.0
    js = """
(function(){
  %s
  window.studybuddyToken = (window.studybuddyToken || 0) + 1;
  el.innerHTML = %s;
})();
""" % (_ENSURE_MINI_EL_JS, json.dumps(_mini_html()))
    _eval_in_reviewer(js)


def animate_reaction(name: str, min_duration_ms: int) -> None:
    # Show the `name` sprite on the mini cat for at least min_duration_ms, then revert to a fresh idle pose. 
    # This is the browser-side equivalent of "play animation for N seconds
    if not _mini_pet_active():
        return

    global _mini_reaction_until
    frames = SPRITE_FILES[name][1]
    natural_ms = int(round(frames * FRAME_SECONDS * 1000)) + 50
    duration_ms = max(natural_ms, min_duration_ms)
    _mini_reaction_until = time.time() + duration_ms / 1000.0

    html_now = _mini_html(force_name=name)
    html_after = _mini_html()
    js = """
(function(){
  %s
  window.studybuddyToken = (window.studybuddyToken || 0) + 1;
  var myToken = window.studybuddyToken;
  el.innerHTML = %s;
  setTimeout(function(){
    if (window.studybuddyToken === myToken) { el.innerHTML = %s; }
  }, %d);
})();
""" % (_ENSURE_MINI_EL_JS, json.dumps(html_now), json.dumps(html_after), duration_ms)
    _eval_in_reviewer(js)


def on_show_question(card) -> None:
    if time.time() < _mini_reaction_until:
        return  # a reaction animation is still playing itself out; let it finish
    show_idle_pet()


# ---------------------------------------------------------------------------
# Review hook: streak tracking, in-review reactions
# ---------------------------------------------------------------------------
def on_answer(reviewer, card, ease: int) -> None:
    cfg = get_config()
    state = load_state()
    show_review_cat = cfg.get("show_during_review", True)

    state["reviews"] += 1
    if ease == 1:
        state["streak"] = 0
    else:
        state["correct"] = int(state.get("correct", 0)) + 1
        state["streak"] = int(state.get("streak", 0)) + 1
        state["best_streak"] = max(state["best_streak"], state["streak"])

    # Reactions are entirely skipped when the mini cat is turned off
    if show_review_cat:
        if ease == 1:
            animate_reaction(random.choice(REACTION_POOL_BAD), REACTION_HOLD_MS)
        else:
            animate_reaction(random.choice(REACTION_POOL_GOOD), REACTION_HOLD_MS)

    save_state(state)


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(ADDON_NAME)
        cfg = get_config()

        def with_reset(widget, default_label, reset_fn):
            btn = QPushButton(f"Reset ({default_label})")
            btn.clicked.connect(reset_fn)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(widget)
            row.addWidget(btn)
            container = QWidget()
            container.setLayout(row)
            return container

        def spin_row(lo, hi, val, default):
            box = QSpinBox()
            box.setRange(lo, hi)
            box.setValue(int(val))
            row = with_reset(box, str(default), lambda: box.setValue(default))
            return box, row

        self.name_edit = QLineEdit(cfg["pet_name"])

        self.color_combo = QComboBox()
        self._color_keys = PET_COLORS
        for key in self._color_keys:
            self.color_combo.addItem(COLOR_LABELS[key])
        if cfg.get("pet_color") in self._color_keys:
            self.color_combo.setCurrentIndex(self._color_keys.index(cfg["pet_color"]))

        self.color_random_check = QCheckBox("Random on startup")
        self.color_random_check.setChecked(bool(cfg.get("pet_color_random", False)))
        self.color_combo.setEnabled(not self.color_random_check.isChecked())
        self.color_random_check.toggled.connect(lambda checked: self.color_combo.setEnabled(not checked))

        color_row_layout = QHBoxLayout()
        color_row_layout.setContentsMargins(0, 0, 0, 0)
        color_row_layout.addWidget(self.color_combo)
        color_row_layout.addWidget(self.color_random_check)
        color_row = QWidget()
        color_row.setLayout(color_row_layout)

        self.neutral_spin, neutral_row = spin_row(2, 100000, cfg["mood_neutral_at"], DEFAULT_CONFIG["mood_neutral_at"])
        self.happy_spin, happy_row = spin_row(3, 200000, cfg["mood_happy_at"], DEFAULT_CONFIG["mood_happy_at"])
        self.excited_spin, excited_row = spin_row(4, 300000, cfg["mood_excited_at"], DEFAULT_CONFIG["mood_excited_at"])
        self.size_spin, size_row = spin_row(60, 300, cfg["sprite_size"], DEFAULT_CONFIG["sprite_size"])

        self.mini_check = QCheckBox("Show mini cat during reviews")
        self.mini_check.setChecked(bool(cfg["show_during_review"]))

        self.mood_bar_check = QCheckBox("Show mood label, bar, and card count")
        self.mood_bar_check.setChecked(bool(cfg["show_mood_bar"]))

        form = QFormLayout()
        form.addRow("Cat's name:", self.name_edit)
        form.addRow("Cat color:", color_row)
        form.addRow("Cards for Sad → Neutral:", neutral_row)
        form.addRow("Cards for Neutral → Happy:", happy_row)
        form.addRow("Cards for Happy → Excited:", excited_row)
        form.addRow("Cat size (px):", size_row)
        form.addRow(self.mini_check)
        form.addRow(self.mood_bar_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def accept(self):
        cfg = get_config()
        cfg["pet_name"] = self.name_edit.text().strip() or DEFAULT_CONFIG["pet_name"]
        cfg["pet_color_random"] = self.color_random_check.isChecked()
        if cfg["pet_color_random"]:
            cfg["pet_color"] = random.choice(PET_COLORS)  # reroll immediately, not just on next startup
        else:
            cfg["pet_color"] = self._color_keys[self.color_combo.currentIndex()]
        cfg["mood_neutral_at"] = self.neutral_spin.value()
        cfg["mood_happy_at"] = self.happy_spin.value()
        cfg["mood_excited_at"] = self.excited_spin.value()
        cfg["sprite_size"] = self.size_spin.value()
        cfg["show_during_review"] = self.mini_check.isChecked()
        cfg["show_mood_bar"] = self.mood_bar_check.isChecked()
        save_config(cfg)
        super().accept()
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()


def open_settings() -> None:
    SettingsDialog(mw).exec()


# ---------------------------------------------------------------------------
# Wire everything up
# ---------------------------------------------------------------------------
def setup() -> None:
    cfg = get_config()
    if cfg.get("pet_color_random", False):
        cfg["pet_color"] = random.choice(PET_COLORS)
        save_config(cfg)

    gui_hooks.deck_browser_will_render_content.append(on_deck_browser_render)
    gui_hooks.reviewer_did_answer_card.append(on_answer)
    gui_hooks.reviewer_did_show_question.append(on_show_question)
    gui_hooks.sync_did_finish.append(_reconcile_today_after_sync)

    action = QAction(f"{ADDON_NAME} Settings…", mw)
    action.triggered.connect(open_settings)
    mw.form.menuTools.addAction(action)


setup()
