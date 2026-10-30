# -*- coding: utf-8 -*-
"""Binary handling (Wizard logic).

Implements the filesystem based wizard approach (no Titan/JSONRPC scan):

Build install (same session):
  - After extracting build zip into special://home/:
    * scan special://home/addons/*/addon.xml for 'kodi.binary'
    * collect addon ids
    * delete those addon folders (best-effort)
    * ALWAYS write binaries.json to:
        special://home/userdata/addon_data/plugin.program.TiTanX_LAB-GUIWizard/binaries.json
      format: {"binaries": ["addon.id", ...]}

Next start:
  - startup.py calls restore_binaries_startup(), which:
    * reads binaries.json
    * installs each addon via InstallAddon(id)
    * waits for System.HasAddon(id) with timeout
    * clicks yes/no dialog automatically
    * on success removes binaries.json, otherwise rewrites failed-only list.
"""

import json
import os
import shutil
import time
from xml.etree import ElementTree as ET

import xbmc
import xbmcvfs

from resources.libs import wizard as wiz


ADDONS_PATH = xbmcvfs.translatePath('special://home/addons')
BINARIES_JSON = xbmcvfs.translatePath(
    'special://home/userdata/addon_data/plugin.program.TiTanX_LAB-GUIWizard/binaries.json'
)


LOCK_PATH = xbmcvfs.translatePath(
    'special://home/userdata/addon_data/plugin.program.TiTanX_LAB-GUIWizard/restore.lock'
)

def _acquire_restore_lock(ttl_seconds=30):
    """Prevent running restore multiple times per Kodi start.
    Returns True if lock acquired, False if another instance ran recently.
    """
    try:
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        if os.path.exists(LOCK_PATH):
            age = time.time() - os.path.getmtime(LOCK_PATH)
            if age < ttl_seconds:
                _log('Restore lock present (age %.1fs) -> skipping duplicate run' % age)
                return False
        # touch/write lock
        with open(LOCK_PATH, 'w', encoding='utf-8') as f:
            f.write(str(time.time()))
        return True
    except Exception as e:
        _log('Restore lock error (continuing anyway): %s' % e, xbmc.LOGERROR)
        return True


def _log(msg, level=xbmc.LOGINFO):
    try:
        msg = wiz.redact_urls(str(msg))
    except Exception:
        pass
    xbmc.log('[TiTan Wizard][BINARIES] %s' % msg, level)


def _atomic_write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, path)  # atomic on Windows


def _read_binaries_json():
    if not os.path.exists(BINARIES_JSON):
        return []
    try:
        with open(BINARIES_JSON, 'r', encoding='utf-8', errors='ignore') as f:
            data = json.load(f)
        arr = data.get('binaries', [])
        if not isinstance(arr, list):
            return []
        return [x for x in arr if isinstance(x, str) and x.strip()]
    except Exception as e:
        _log('Failed to read binaries.json: %s' % e, xbmc.LOGERROR)
        return []


# -------------------------------------------------------------------------
# Compatibility hook: default.py currently calls binaries.scan_and_store_binaries()
# right after the Fresh-Install-YES.
# For Wizard-logic-only we DO NOT delete at that time; we simply log.
# -------------------------------------------------------------------------

def scan_and_store_binaries():
    """Compatibility wrapper.

    Keeps the build flow from crashing if default.py calls this. We do not
    want to perform the wizard scan/delete here (that happens post-extract).
    """
    _log('Fresh-Install YES confirmed -> binary scan deferred until post-extract')
    return []


def post_extract_scan_and_remove_binaries():
    """Scan for binary addons (addon.xml contains kodi.binary), delete folders,
    and ALWAYS write binaries.json.
    """
    _log('Binary scan started (post-extract filesystem kodi.binary)')

    binaries = []

    if not os.path.isdir(ADDONS_PATH):
        _log('Addons path not found: %s' % ADDONS_PATH, xbmc.LOGERROR)
        _atomic_write_json(BINARIES_JSON, {'binaries': []})
        return []

    for name in os.listdir(ADDONS_PATH):
        addon_dir = os.path.join(ADDONS_PATH, name)
        addon_xml = os.path.join(addon_dir, 'addon.xml')
        if not os.path.isdir(addon_dir) or not os.path.exists(addon_xml):
            continue

        try:
            with open(addon_xml, 'r', encoding='utf-8', errors='ignore') as f:
                xml_text = f.read()
        except Exception:
            continue

        if 'kodi.binary' not in xml_text:
            continue

        # derive addon id
        addon_id = name
        try:
            root = ET.fromstring(xml_text)
            addon_id = root.attrib.get('id', name)
        except Exception:
            addon_id = name

        binaries.append(addon_id)

        # best-effort delete folder to force repo reinstall after reboot
        try:
            shutil.rmtree(addon_dir)
            _log('Deleted binary addon folder: %s' % addon_id)
        except Exception as e:
            _log('Could not delete %s: %s' % (addon_id, e), xbmc.LOGERROR)

    # ALWAYS write valid JSON (even empty)
    _atomic_write_json(BINARIES_JSON, {'binaries': binaries})

    _log('Binary scan found %d binaries' % len(binaries))
    _log('binaries.json saved to %s' % BINARIES_JSON)
    return binaries


def _install_addon(addon_id: str, timeout_sec: int = 20) -> bool:
    """Installiert ein Addon via InstallAddon(), wartet auf System.HasAddon()
    und klickt Bestätigungs-Dialoge automatisch weg (wie TiTan Simpel).

    Args:
        addon_id:    Kodi-Addon-ID
        timeout_sec: Max. Wartezeit pro Addon in Sekunden (Standard: 20)
    """
    if xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id):
        _log('%s bereits installiert, überspringe' % addon_id)
        return True

    xbmc.executebuiltin('InstallAddon(%s)' % addon_id)

    clicked = False
    start   = time.time()
    while not xbmc.getCondVisibility('System.HasAddon(%s)' % addon_id):
        if time.time() - start >= timeout_sec:
            return False
        xbmc.sleep(500)
        # Bestätigungs-Dialog automatisch wegklicken (Ja-Button = 11)
        if xbmc.getCondVisibility('Window.IsTopMost(yesnodialog)') and not clicked:
            xbmc.executebuiltin('SendClick(yesnodialog, 11)')
            clicked = True

    return True


def restore_binaries_startup():
    """Install binaries listed in binaries.json on Kodi startup.

    Wizard-logic restore with extra robustness:
      - logs whether binaries.json exists and how many IDs are loaded
      - waits for Kodi startup + repos/network
      - forces repository update
      - installs each addon via InstallAddon() and waits for System.HasAddon()
      - auto-clicks yes/no dialogs
      - does not abort on failures; rewrites binaries.json with failed-only IDs
    """
    _log('Binary restore started')

    # Lock is only meant to prevent duplicate runs within the *same* Kodi start.
    # We release it at the end so we can retry installs in the same session if
    # the add-on manager / repositories weren't ready yet.
    if not _acquire_restore_lock():
        return

    try:
        _restore_binaries_body()
    finally:
        try:
            if os.path.exists(LOCK_PATH):
                os.remove(LOCK_PATH)
        except Exception:
            pass


def _restore_binaries_body():
    """Implementation body for restore_binaries_startup (kept separate to allow lock-release in finally)."""

    if not os.path.exists(BINARIES_JSON):
        _log('binaries.json not found at %s' % BINARIES_JSON)
        return

    binaries = _read_binaries_json()
    _log('Restoring %d binaries' % len(binaries))
    if not binaries:
        _log('Binary restore finished (nothing to do)')
        return

    # Allow Kodi GUI / addon system to settle
    try:
        mon = xbmc.Monitor()
        mon.waitForAbort(5)
    except Exception:
        xbmc.sleep(5000)

    # Kick repo update (helps right after fresh install)
    try:
        xbmc.executebuiltin('UpdateAddonRepos')
        xbmc.executebuiltin('UpdateLocalAddons')
        _log('Triggered UpdateAddonRepos/UpdateLocalAddons')
    except Exception as e:
        _log('Repo update trigger failed: %s' % e, xbmc.LOGERROR)

    # Give the repo update a moment
    xbmc.sleep(3000)

    failed = []
    for addon_id in binaries:
        addon_id = addon_id.strip()
        if not addon_id:
            continue

        try:
            _log('Installing binary: %s' % addon_id)
            ok = _install_addon(addon_id, timeout_sec=20)
        except Exception as e:
            _log('Install exception for %s: %s' % (addon_id, e), xbmc.LOGERROR)
            ok = False

        if ok:
            _log('Install OK: %s' % addon_id)
        else:
            _log('Install FAILED/TIMEOUT: %s' % addon_id, xbmc.LOGERROR)
            failed.append(addon_id)

    if failed:
        _log('Binary restore finished with failures: %d (will retry next start)' % len(failed), xbmc.LOGERROR)
        _atomic_write_json(BINARIES_JSON, {'binaries': failed})
    else:
        _log('Binary restore finished (all OK)')
        try:
            os.remove(BINARIES_JSON)
        except Exception as e:
            _log('Could not delete binaries.json: %s' % e, xbmc.LOGERROR)
