# -*- coding: utf-8 -*-
"""progress_dialog.py – Addon-eigener Progress-Dialog für TiTanX Lab GUI Wizard.

Ersetzt xbmcgui.DialogProgress() durch einen WindowXMLDialog mit eigenem
Hintergrund aus dem Addon-Skin. Dadurch ist der Dialog bei allen Skins
immer sichtbar – auch wenn der aktive Skin keine DialogProgress.xml liefert
oder diese keinen Hintergrund hat.

API-kompatibel mit xbmcgui.DialogProgressBG():
    create(heading, message='')
    update(percent, message='')
    close()
    iscanceled() → immer False (kein Abbrechen-Button)
"""

import os
import xbmc
import xbmcgui
import xbmcaddon
import uservar

ADDON       = xbmcaddon.Addon(uservar.ADDON_ID)
ADDON_PATH  = ADDON.getAddonInfo('path')
SKIN_PATH   = os.path.join(ADDON_PATH, 'resources', 'skins')
COLOR1      = uservar.COLOR1
COLOR2      = uservar.COLOR2

# Steuerelement-IDs (müssen mit ProgressDialog.xml übereinstimmen)
# _ID_TITLE entfernt – Titelzeile ist statisch in ProgressDialog.xml (4 separate Labels)
_ID_LINE1   = 102   # Nachricht Zeile 1
_ID_LINE2   = 103   # Nachricht Zeile 2
_ID_LINE3   = 104   # Nachricht Zeile 3
_ID_BAR     = 105   # Fortschrittsbalken (Breite = percent * 13)
_ID_PERCENT = 106   # Prozentzahl rechts

_BAR_MAX_WIDTH = 960  # Muss mit XML-Breite übereinstimmen


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log('[TiTanX Lab][ProgressDialog] %s' % msg, level)


def _strip_tags(text):
    """Entfernt Kodi-Farbtags für die Anzeige in Labels."""
    import re
    return re.sub(r'\[/?(?:COLOR|B|I|LIGHT|UPPERCASE|LOWERCASE|CAPITALIZE)[^\]]*\]', '', str(text))


def _split_message(message):
    """Teilt einen mehrzeiligen String in bis zu 3 Zeilen auf."""
    if not message:
        return '', '', ''
    lines = [l.strip() for l in str(message).split('\n') if l.strip()]
    lines += ['', '', '']
    return lines[0], lines[1], lines[2]


class _ProgressWindow(xbmcgui.WindowXMLDialog):
    """Internes WindowXMLDialog – nicht direkt verwenden, nur über WizardProgressDialog."""

    def __init__(self, *args, **kwargs):
        self._heading = kwargs.get('heading', uservar.ADDONTITLE_PLAIN)
        self._message = kwargs.get('message', '')
        self._percent = 0
        self._closed  = False

    def onInit(self):
        self._apply(self._heading, self._percent, self._message)

    def _apply(self, heading, percent, message):
        """Setzt alle Controls auf neue Werte."""
        try:
            # Titelzeile statisch in XML – kein setLabel nötig
            l1, l2, l3 = _split_message(message)
            self.getControl(_ID_LINE1).setLabel(_strip_tags(l1))
            self.getControl(_ID_LINE2).setLabel(_strip_tags(l2))
            self.getControl(_ID_LINE3).setLabel(_strip_tags(l3))
            bar_width = int(max(0, min(percent, 100)) * _BAR_MAX_WIDTH / 100)
            self.getControl(_ID_BAR).setWidth(bar_width)
            self.getControl(_ID_PERCENT).setLabel('%d%%' % int(percent))
        except Exception as e:
            _log('_apply Fehler: %s' % e, xbmc.LOGERROR)

    def set_values(self, heading, percent, message):
        self._heading = heading
        self._percent = percent
        self._message = message
        if not self._closed:
            self._apply(heading, percent, message)

    def safe_close(self):
        if not self._closed:
            self._closed = True
            self.close()

    def onAction(self, action):
        pass  # Dialog nicht schließbar per Tastatur/Fernbedienung


class WizardProgressDialog:
    """Öffentliche API – drop-in-Ersatz für xbmcgui.DialogProgressBG().

    Verwendung:
        dp = WizardProgressDialog()
        dp.create('TiTanX Lab GUI Wizard', 'Lade Build...')
        dp.update(50, 'Hälfte geschafft...')
        dp.close()
    """

    def __init__(self):
        self._window  = None
        self._heading = uservar.ADDONTITLE_PLAIN
        self._active  = False

    def create(self, heading='', message=''):
        self._heading = heading or uservar.ADDONTITLE_PLAIN
        try:
            self._window = _ProgressWindow(
                'ProgressDialog.xml', ADDON_PATH, 'DefaultSkin',
                heading=self._heading, message=message
            )
            self._active = True
            self._window.show()
            _log('Dialog geöffnet: %s' % _strip_tags(heading))
        except Exception as e:
            _log('create() Fehler: %s' % e, xbmc.LOGERROR)
            self._active = False

    def update(self, percent=0, message=''):
        if not self._active or not self._window:
            return
        try:
            self._window.set_values(self._heading, percent, message)
        except Exception as e:
            _log('update() Fehler: %s' % e, xbmc.LOGERROR)

    def close(self):
        if self._window:
            try:
                self._window.safe_close()
            except Exception as e:
                _log('close() Fehler: %s' % e, xbmc.LOGERROR)
            finally:
                self._window = None
                self._active = False

    def iscanceled(self):
        """Immer False – kein Abbrechen-Button im eigenen Dialog."""
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
