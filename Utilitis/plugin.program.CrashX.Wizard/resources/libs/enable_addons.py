# -*- coding: utf-8 -*-
"""enable_addons.py – Nach Build-Installation alle Addons in der Kodi-DB aktivieren.

Übernommen und angepasst von TiTan Simpel (plugin.program.titansimpel).
Scannt alle addon.xml im Addons-Verzeichnis, erkennt deaktivierte Addons
und trägt sie direkt in die Addons-Datenbank ein.
"""

import glob
import os
import sqlite3
from datetime import datetime

import xbmc
import xbmcaddon
import xbmcvfs

_ADDONS_PATH  = xbmcvfs.translatePath('special://home/addons')
_ADDONS_DB    = xbmcvfs.translatePath('special://userdata/Database/Addons33.db')
_INSTALL_DATE = str(datetime.now())[:-7]


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log('[TiTanX Lab][enable_addons] %s' % msg, level)


def _enable_in_db(addon_id):
    """Fügt ein Addon in die Kodi-DB ein oder setzt es auf enabled=1."""
    conn = None
    try:
        conn = sqlite3.connect(_ADDONS_DB)
        c = conn.cursor()
        c.execute('SELECT id, addonID, enabled FROM installed WHERE addonID = ?', (addon_id,))
        found = c.fetchone()
        if found is None:
            c.execute(
                'INSERT INTO installed (addonID, enabled, installDate) VALUES (?,?,?)',
                (addon_id, 1, _INSTALL_DATE)
            )
        else:
            c.execute('UPDATE installed SET enabled = ? WHERE addonID = ?', (1, addon_id))
        conn.commit()
    except Exception as e:
        _log('DB-Fehler für %s: %s' % (addon_id, e), xbmc.LOGERROR)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def enable_addons():
    """Scannt alle Addons im Addons-Ordner und aktiviert deaktivierte in der DB."""
    _log('Addon-Aktivierung gestartet')

    xmls = sorted(glob.glob(os.path.join(_ADDONS_PATH, '*/addon.xml')))
    addon_ids = []

    for xml in xmls:
        try:
            import xml.dom.minidom as minidom
            root = minidom.parse(xml).documentElement
            addon_id = root.getAttribute('id')
            if addon_id:
                addon_ids.append(addon_id)
        except Exception as e:
            _log('addon.xml Lesefehler %s: %s' % (xml, e), xbmc.LOGWARNING)

    enabled  = []
    disabled = []

    for addon_id in addon_ids:
        try:
            xbmcaddon.Addon(id=addon_id)
            enabled.append(addon_id)
        except Exception:
            disabled.append(addon_id)

    _log('%d Addons gefunden – %d aktiv, %d deaktiviert' % (
        len(addon_ids), len(enabled), len(disabled)))

    for addon_id in disabled:
        try:
            _enable_in_db(addon_id)
        except Exception as e:
            _log('Aktivierung fehlgeschlagen %s: %s' % (addon_id, e), xbmc.LOGERROR)

    # Kodi über neue Addons informieren
    xbmc.executebuiltin('UpdateLocalAddons')
    xbmc.executebuiltin('UpdateAddonRepos')

    _log('Addon-Aktivierung abgeschlossen (%d aktiviert)' % len(disabled))
