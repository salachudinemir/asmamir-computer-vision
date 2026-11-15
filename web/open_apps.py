"""Voice-launched local apps. Open only.

YouTube and the default browser use webbrowser. Excel, WeChat, and WhatsApp use
subprocess. No typing, no send, no WhatsApp/WeChat message body, no Task Scheduler.
"""

import os
import subprocess
import time
import webbrowser
from pathlib import Path

YOUTUBE = "youtube"
EXCEL = "excel"
BROWSER = "browser"
WECHAT = "wechat"
WHATSAPP = "whatsapp"

YOUTUBE_URL = "https://www.youtube.com/"
BROWSER_BLANK = "about:blank"
WHATSAPP_AUMID = os.environ.get(
    "ASMAMIR_WHATSAPP_AUMID",
    "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
)

_EXCEL_GUESSES = (
    Path(os.environ["ProgramFiles"]) / "Microsoft Office" / "root" / "Office16" / "EXCEL.EXE",
    Path(os.environ["ProgramFiles"]) / "Microsoft Office" / "Office16" / "EXCEL.EXE",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    / "Microsoft Office"
    / "root"
    / "Office16"
    / "EXCEL.EXE",
)
_WECHAT_GUESSES = (
    Path(os.environ["ProgramFiles"]) / "Tencent" / "Weixin" / "Weixin.exe",
    Path(os.environ["ProgramFiles"]) / "Tencent" / "WeChat" / "WeChat.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Tencent" / "WeChat" / "WeChat.exe",
)
_BROWSER_GUESSES = (
    Path(os.environ["ProgramFiles"]) / "Google" / "Chrome" / "Application" / "chrome.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    / "Microsoft"
    / "Edge"
    / "Application"
    / "msedge.exe",
)
_WHATSAPP_GUESSES = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "WhatsApp" / "WhatsApp.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "WhatsApp" / "WhatsApp.exe",
)

_SEND_WORDS = {
    "send",
    "sent",
    "type",
    "typing",
    "typed",
    "message",
    "messages",
    "kirim",
    "ketik",
    "pesan",
}
_LAST_LAUNCH = 0.0
_COOLDOWN = 1.6

DISPLAY = {
    YOUTUBE: "YouTube",
    EXCEL: "Excel",
    BROWSER: "the browser",
    WECHAT: "WeChat",
    WHATSAPP: "WhatsApp",
}


def _clean(command):
    text = command.replace("-", " ").replace(".", " ").lower()
    return " ".join(text.split()).strip()


def _has_pair(words, first, second):
    return any(words[i] == first and words[i + 1] == second for i in range(len(words) - 1))


_EXACT = {
    "youtube",
    "you tube",
    "excel",
    "browser",
    "chrome",
    "wechat",
    "we chat",
    "weixin",
    "wei xin",
    "whatsapp",
    "whats app",
}


def wants(command):
    """Return youtube|excel|browser|wechat|whatsapp, or None.

    Open only. A phrase that asks to type or send is ignored.
    Needs “open” / “buka” or the app name by itself.
    """
    text = _clean(command)
    if not text:
        return None
    words = text.split()
    if len(words) > 6:
        return None
    if words[0] in {"opening", "opened", "launching"}:
        return None
    if any(word in _SEND_WORDS for word in words):
        return None
    joined = " ".join(words)
    if joined.replace(" ", "") in {
        "youtubeison",
        "excelison",
        "browserison",
        "wechatison",
        "whatsappison",
    }:
        return None
    opener = words[0] in {"open", "buka"}
    if not opener and joined not in _EXACT:
        return None
    rest = words[1:] if opener else words
    if not rest:
        return None
    rest_join = " ".join(rest)
    compact = rest_join.replace(" ", "")
    if "youtube" in compact or _has_pair(rest, "you", "tube"):
        return YOUTUBE
    if "excel" in rest:
        return EXCEL
    if (
        "weixin" in compact
        or "wechat" in compact
        or _has_pair(rest, "we", "chat")
        or _has_pair(rest, "wei", "xin")
    ):
        return WECHAT
    if "whatsapp" in compact or _has_pair(rest, "whats", "app"):
        return WHATSAPP
    if "browser" in rest or "chrome" in rest or rest[:1] == ["edge"] or rest[:2] == ["microsoft", "edge"]:
        return BROWSER
    return None


def _env_path(name):
    raw = os.environ.get(name, "").strip().strip('"')
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def _first_file(paths):
    for path in paths:
        if path and path.is_file():
            return path
    return None


def excel_path():
    return _env_path("ASMAMIR_EXCEL") or _first_file(_EXCEL_GUESSES)


def wechat_path():
    return _env_path("ASMAMIR_WECHAT") or _first_file(_WECHAT_GUESSES)


def browser_path():
    return _env_path("ASMAMIR_BROWSER") or _first_file(_BROWSER_GUESSES)


def whatsapp_path():
    return _env_path("ASMAMIR_WHATSAPP") or _first_file(_WHATSAPP_GUESSES)


def _gui_popen(argv, cwd=None):
    """Start a visible GUI process. Never schtasks. Never extra args for typing."""
    if not argv:
        raise ValueError("empty launch argv")
    banned = {"schtasks", "send", "type", "pyautogui"}
    lowered = [str(part).lower() for part in argv]
    if any(token in banned for token in lowered):
        raise ValueError(f"refusing launch argv {argv!r}")
    return subprocess.Popen(
        argv,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )


def _open_youtube():
    return bool(webbrowser.open(YOUTUBE_URL, new=2))


def _open_browser():
    path = browser_path()
    if path is not None:
        _gui_popen([str(path)], cwd=str(path.parent))
        return True
    return bool(webbrowser.open(BROWSER_BLANK, new=2))


def _open_excel():
    path = excel_path()
    if path is None:
        return False
    _gui_popen([str(path)], cwd=str(path.parent))
    return True


def _open_wechat():
    path = wechat_path()
    if path is None:
        return False
    _gui_popen([str(path)], cwd=str(path.parent))
    return True


def _open_whatsapp():
    """Desktop WhatsApp only. No web.whatsapp.com, no whatsapp://send."""
    path = whatsapp_path()
    if path is not None:
        _gui_popen([str(path)], cwd=str(path.parent))
        return True
    aumid = (os.environ.get("ASMAMIR_WHATSAPP_AUMID") or WHATSAPP_AUMID).strip()
    if not aumid or "send" in aumid.lower():
        return False
    _gui_popen(["explorer.exe", f"shell:AppsFolder\\{aumid}"])
    return True


_LAUNCHERS = {
    YOUTUBE: _open_youtube,
    BROWSER: _open_browser,
    EXCEL: _open_excel,
    WECHAT: _open_wechat,
    WHATSAPP: _open_whatsapp,
}


def launch(app):
    """Open the named app. True if a launch was started. Respects a short cooldown."""
    global _LAST_LAUNCH
    if app not in _LAUNCHERS:
        return False
    now = time.monotonic()
    if now - _LAST_LAUNCH < _COOLDOWN:
        print(f"Open {app}: cooldown, skipped.")
        return True
    ok = bool(_LAUNCHERS[app]())
    if ok:
        _LAST_LAUNCH = now
        print(f"Open {app}: launched (open only).")
    else:
        print(f"Open {app}: not found on this computer.")
    return ok


def launch_from_command(command):
    app = wants(command)
    if not app:
        return None, False
    return app, launch(app)
