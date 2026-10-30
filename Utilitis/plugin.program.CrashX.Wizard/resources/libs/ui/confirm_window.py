"""
confirm_window.py — Skin-independent Yes/No confirmation dialog.

Kodi's native ``xbmcgui.Dialog().yesno()`` inherits its background/panel
artwork from whichever skin is currently active. Some third-party build
skins ship an incomplete ``DialogConfirm.xml`` (no background panel
defined), which leaves the confirmation text floating with no backdrop —
readable, but visually broken and overlapping whatever was behind it.

``ConfirmWindow`` sidesteps that entirely: it is a self-contained
``xbmcgui.WindowDialog`` that draws its own background, panel, message and
Yes/No buttons using only assets bundled with this addon — so it looks the
same no matter which skin/build is installed.

Usage::

    yes = ConfirmWindow().show(heading, message, yeslabel='Yes', nolabel='No')

Returns True for Yes, False for No/Back/Esc.
"""

import os
import xbmc
import xbmcgui

from .. import config

# Screen constants
_W = 1280
_H = 720

# Overlay panel dimensions (centred)
_PAN_W = 900
_PAN_H = 320
_PAN_X = (_W - _PAN_W) // 2
_PAN_Y = (_H - _PAN_H) // 2

_BTN_W = 260
_BTN_H = 60


class ConfirmWindow(xbmcgui.WindowDialog):
    """Self-contained Yes/No confirmation window with a guaranteed dark
    background, independent of the currently active Kodi skin."""

    def __init__(self):
        super().__init__()
        self._result = False
        self._closing = False

    def show(self, heading: str = '', message: str = '',
             yeslabel: str = 'Yes', nolabel: str = 'No') -> bool:
        """Build, display and block until the user picks Yes or No.
        Returns True for Yes, False for No/Back/Esc."""
        self._result = False
        self._closing = False
        self._build_controls(heading, message, yeslabel, nolabel)
        super().show()
        self.setFocus(self._no_ctrl)
        while not self._closing:
            xbmc.sleep(100)
        super().close()
        return self._result

    # ------------------------------------------------------------------
    # Key / click handling
    # ------------------------------------------------------------------
    def onAction(self, action) -> None:
        action_id = action.getId()
        if action_id in (
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_STOP,
        ):
            self._result = False
            self._closing = True

    def onControl(self, control) -> None:
        cid = control.getId()
        if cid == self._yes_ctrl.getId():
            self._result = True
            self._closing = True
        elif cid == self._no_ctrl.getId():
            self._result = False
            self._closing = True

    # ------------------------------------------------------------------
    # Control construction
    # ------------------------------------------------------------------
    def _build_controls(self, heading, message, yeslabel, nolabel) -> None:
        # 1. Full-screen fanart background
        bg_img = config.FANART if os.path.exists(config.FANART) else ''
        bg = xbmcgui.ControlImage(0, 0, _W, _H, bg_img)
        self.addControl(bg)

        # 2. Dark panel
        panel_img = os.path.join(config.ART, 'LoadingPanel.png')
        if not os.path.exists(panel_img):
            panel_img = ''
        panel = xbmcgui.ControlImage(_PAN_X, _PAN_Y, _PAN_W, _PAN_H, panel_img)
        self.addControl(panel)

        # 3. Heading
        heading_lbl = xbmcgui.ControlLabel(
            _PAN_X + 20, _PAN_Y + 16, _PAN_W - 40, 40,
            heading or config.ADDONTITLE,
            font='Font13', textColor='0xFFFFFFFF',
            alignment=0x00000006,  # centre
        )
        self.addControl(heading_lbl)

        # 4. Message (multi-line, wraps within the panel)
        message_lbl = xbmcgui.ControlTextBox(
            _PAN_X + 30, _PAN_Y + 70, _PAN_W - 60, _PAN_H - 150,
            font='Font12', textColor='0xFFDDDDDD',
        )
        self.addControl(message_lbl)
        message_lbl.setText(message)

        # 5. Yes / No buttons
        focus_img   = os.path.join(config.ART, 'button_focus.png')
        nofocus_img = os.path.join(config.ART, 'button.png')
        if not os.path.exists(focus_img):
            focus_img = ''
        if not os.path.exists(nofocus_img):
            nofocus_img = ''

        btn_y = _PAN_Y + _PAN_H - _BTN_H - 24
        yes_x = _PAN_X + _PAN_W // 2 - _BTN_W - 15
        no_x  = _PAN_X + _PAN_W // 2 + 15

        self._yes_ctrl = xbmcgui.ControlButton(
            yes_x, btn_y, _BTN_W, _BTN_H,
            yeslabel, focusTexture=focus_img, noFocusTexture=nofocus_img,
            font='Font12', textColor='0xFF00FF00', alignment=0x00000006,
        )
        self.addControl(self._yes_ctrl)

        self._no_ctrl = xbmcgui.ControlButton(
            no_x, btn_y, _BTN_W, _BTN_H,
            nolabel, focusTexture=focus_img, noFocusTexture=nofocus_img,
            font='Font12', textColor='0xFFFF0000', alignment=0x00000006,
        )
        self.addControl(self._no_ctrl)

        self._yes_ctrl.controlRight(self._no_ctrl)
        self._no_ctrl.controlLeft(self._yes_ctrl)
