"""
install_window.py — Full-screen install backdrop for Omega GUI Wizard.

Implements the same ``create / update / iscanceled / close`` interface as
``xbmcgui.DialogProgress`` so that ``downloader.py`` and ``extract.py`` need
zero code changes — just pass an ``InstallWindow`` instance where they
currently receive a ``DialogProgress``.

Visual layout (1280 × 720)
--------------------------
┌──────────────────────────────────┐
│  [full-screen fanart background] │
│                                  │
│   ┌──────────────────────────┐   │
│   │  [addon title / logo]    │   │
│   │  [step label     ………]  │   │
│   │  [progress bar   ██░░░░] │   │
│   │  [   pct %    speed/ETA] │   │
│   │  [detail line            │   │
│   └──────────────────────────┘   │
└──────────────────────────────────┘
"""

import os
import re
import json
import xbmc
import xbmcgui
import xbmcaddon
import uservar

from .. import config

ADDON = xbmcaddon.Addon(id=uservar.ADDON_ID)

# Gaengige Kodi-Skin-Farbnamen (Auszug aus Kodis GUIColorManager-Tabelle),
# damit in progressbar_color.json sowohl Namen ("lime") als auch Hex-Codes
# ("FF0827F5") verwendet werden koennen.
_KODI_COLOR_NAMES = {
    'white': 'FFFFFFFF', 'black': 'FF000000', 'red': 'FFFF0000',
    'green': 'FF008000', 'lime': 'FF00FF00', 'blue': 'FF0000FF',
    'yellow': 'FFFFFF00', 'orange': 'FFFFA500', 'cyan': 'FF00FFFF',
    'magenta': 'FFFF00FF', 'gray': 'FF808080', 'grey': 'FF808080',
    'silver': 'FFC0C0C0', 'gold': 'FFFFD700', 'springgreen': 'FF00FF7F',
    'dimgray': 'FF696969', 'dodgerblue': 'FF1E90FF',
}
_DEFAULT_PROGRESSBAR_COLOR = 'FFFFFFFF'  # Weiss = Basisfarbe von ProgressBar.png


def _resolve_progressbar_color(value):
    """Wandelt einen Kodi-Farbnamen ODER Hex-Code in einen gueltigen
    8-stelligen ARGB-Hex-String (ohne '0x'-Prefix) um. Faellt bei
    unbekanntem/ungueltigem Wert auf Weiss zurueck, statt abzustuerzen."""
    if not value or not isinstance(value, str):
        return _DEFAULT_PROGRESSBAR_COLOR
    value = value.strip()
    if re.fullmatch(r'[0-9A-Fa-f]{8}', value):
        return value.upper()
    if re.fullmatch(r'[0-9A-Fa-f]{6}', value):
        return ('FF' + value).upper()
    return _KODI_COLOR_NAMES.get(value.lower(), _DEFAULT_PROGRESSBAR_COLOR)


def _load_progressbar_colordiffuse():
    """Liest resources/art/progressbar_color.json (Format: {"color": "..."})
    und liefert den fertigen '0xARGB'-String fuer ControlImage(colorDiffuse=...).
    Bei fehlender/fehlerhafter Datei wird ohne Fehler auf Weiss zurueckgefallen,
    sodass die Progress-Bar in jedem Fall sichtbar bleibt."""
    path = os.path.join(config.ART, 'progressbar_color.json')
    raw = _DEFAULT_PROGRESSBAR_COLOR
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        color = data.get('color', _DEFAULT_PROGRESSBAR_COLOR)
        if isinstance(color, str):
            raw = color
    except Exception:
        pass
    return '0x%s' % _resolve_progressbar_color(raw)


# Screen constants
_W = 1280
_H = 720

# Overlay panel dimensions (centred horizontally, sits in the lower 60 %)
_PAN_W = 900
_PAN_H = 320
_PAN_X = (_W - _PAN_W) // 2      # 190
_PAN_Y = (_H - _PAN_H) // 2 + 60  # ~240

# Control IDs — must not clash with xbmcgui built-ins (0–99 are safe)
_ID_BG       = 100
_ID_PANEL    = 101
_ID_TITLE    = 102
_ID_STEP     = 103
_ID_PROGRESS = 104
_ID_DETAIL   = 106


class InstallWindow(xbmcgui.WindowDialog):
    """Full-screen install backdrop with a centred progress overlay.

    Usage::

        win = InstallWindow()
        win.create('Installing My Build', 'Downloading…')
        # …pass win to downloader / extract as the progress callback…
        win.close()

    The ``update(percent, line1, line2='')`` / ``iscanceled()`` / ``close()``
    interface is intentionally identical to ``xbmcgui.DialogProgress``.
    """

    def __init__(self):
        super().__init__()
        self._cancelled = False
        self._cancel_locked = False
        self._built = False

    # ------------------------------------------------------------------
    # DialogProgress-compatible API
    # ------------------------------------------------------------------
    def create(self, heading: str, message: str = '') -> None:
        """Build controls, show the window, and set the initial heading."""
        if not self._built:
            self._build_controls()
            self._built = True
        self._set_label(_ID_STEP, heading)
        self._set_label(_ID_DETAIL, message)
        self._set_progress(0)
        self._cancelled = False
        self.show()

    def update(self, percent: int, line1: str = '', line2: str = '') -> None:
        """Update progress.  percent=0-100; line1 = step (above bar);
        line2 = detail (below bar). Both are shown exactly as passed —
        callers are responsible for embedding the percentage in line1
        themselves (see downloader.py / extract.py)."""
        pct = max(0, min(100, percent))
        if line1:
            self._set_label(_ID_STEP, line1)
        if line2:
            self._set_label(_ID_DETAIL, line2)
        self._set_progress(pct)

    def iscanceled(self) -> bool:
        """Return True if the user pressed Back/Cancel."""
        return self._cancelled and not self._cancel_locked

    def close(self) -> None:
        """Hide and destroy the window."""
        super().close()

    # ------------------------------------------------------------------
    # Extra methods beyond the DialogProgress interface
    # ------------------------------------------------------------------
    def lock_cancel(self) -> None:
        """Prevent user cancellation (use during ZIP extraction)."""
        self._cancel_locked = True
        self._set_label(_ID_DETAIL, ADDON.getLocalizedString(32808))

    def unlock_cancel(self) -> None:
        """Re-allow user cancellation."""
        self._cancel_locked = False

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------
    def onAction(self, action) -> None:
        action_id = action.getId()
        if action_id in (
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_STOP,
        ):
            if not self._cancel_locked:
                self._cancelled = True

    # ------------------------------------------------------------------
    # Control construction
    # ------------------------------------------------------------------
    def _build_controls(self) -> None:
        # 1. Full-screen fanart background
        bg_img = config.FANART if os.path.exists(config.FANART) else ''
        bg = xbmcgui.ControlImage(0, 0, _W, _H, bg_img)
        self.addControl(bg)

        # 2. Dark semi-transparent overlay panel
        panel_img = os.path.join(config.ART, 'LoadingPanel.png')
        if not os.path.exists(panel_img):
            panel_img = ''
        panel = xbmcgui.ControlImage(_PAN_X, _PAN_Y, _PAN_W, _PAN_H, panel_img)
        self.addControl(panel)

        # 3. Addon title (top of panel)
        title_lbl = xbmcgui.ControlLabel(
            _PAN_X + 20, _PAN_Y + 16, _PAN_W - 40, 40,
            config.ADDONTITLE,
            font='Font13', textColor='0xFFFFFFFF',
            alignment=0x00000006,  # centre
        )
        self.addControl(title_lbl)

        # 4. Step label (2 Zeilen: "Build Downloading/Installing: Name - pct%"
        #    + "Size:..." bzw. "File:.../Size:..." — siehe downloader.py/extract.py)
        step_lbl = xbmcgui.ControlLabel(
            _PAN_X + 20, _PAN_Y + 62, _PAN_W - 40, 56,
            '',
            font='Font12', textColor='0xFFDDDDDD',
        )
        self.addControl(step_lbl)
        self._step_ctrl = step_lbl

        # 5. Progress bar track + fill
        bar_x = _PAN_X + 20
        bar_y = _PAN_Y + 128
        bar_w = _PAN_W - 40
        bar_h = 24

        # Track (grey background)
        track_img = os.path.join(config.ART, 'ProgressBarTrack.png')
        if not os.path.exists(track_img):
            track_img = ''
        track = xbmcgui.ControlImage(bar_x, bar_y, bar_w, bar_h, track_img)
        self.addControl(track)

        # Fill (progress indicator)
        fill_img = os.path.join(config.ART, 'ProgressBar.png')
        if not os.path.exists(fill_img):
            fill_img = ''
        self._fill = xbmcgui.ControlImage(bar_x, bar_y, 0, bar_h, fill_img, colorDiffuse=_load_progressbar_colordiffuse())
        self.addControl(self._fill)
        self._bar_x = bar_x
        self._bar_max_w = bar_w

        # 6. Detail label — eine Zeile unterhalb des Balkens
        #    (Download: "Speed:... ETA:..." | Install: "Errors:...")
        detail_lbl = xbmcgui.ControlLabel(
            bar_x, bar_y + bar_h + 6, bar_w, 36,
            '',
            font='Font12', textColor='0xFFAAAAAA',
        )
        self.addControl(detail_lbl)
        self._detail_ctrl = detail_lbl

    # ------------------------------------------------------------------
    # Control helpers
    # ------------------------------------------------------------------
    def _set_label(self, ctrl_id_or_ctrl, text: str) -> None:
        if isinstance(ctrl_id_or_ctrl, xbmcgui.ControlLabel):
            ctrl = ctrl_id_or_ctrl
        else:
            ctrl = self.getControl(ctrl_id_or_ctrl) if False else None
            # Use stored references — avoids getControl() overhead
            ctrl = {
                _ID_STEP:   getattr(self, '_step_ctrl',   None),
                _ID_DETAIL: getattr(self, '_detail_ctrl', None),
            }.get(ctrl_id_or_ctrl)

        if ctrl is not None:
            ctrl.setLabel(str(text))

    def _set_progress(self, pct: int) -> None:
        if hasattr(self, '_fill'):
            w = int(self._bar_max_w * pct / 100)
            self._fill.setWidth(w)
