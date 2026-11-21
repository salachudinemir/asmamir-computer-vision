"""WeChat chat, voice call, and video call. WhatsApp is never used.

Phrases such as "kirim chat ke <name> <message>", "voice call <name>", and
"video call <name>" target WeChat only. A phrase that names WhatsApp is ignored.
Does not run for YouTube play. No Task Scheduler, no WhatsApp Web, no whatsapp://send.
"""

import ctypes
import importlib.util
import time
from ctypes import wintypes
from pathlib import Path

_LAST = 0.0
_COOLDOWN = 2.0
_VOICE_HINTS = ("voice call", "voice", "audio call", "语音", "語音")
_VIDEO_HINTS = ("video call", "video", "视频", "視頻")


def _clean(command):
    text = command.replace("-", " ").replace(".", " ").lower()
    return " ".join(text.split()).strip()


def _mentions_whatsapp(words):
    compact = "".join(words)
    if "whatsapp" in compact:
        return True
    return any(words[i] == "whats" and i + 1 < len(words) and words[i + 1] == "app" for i in range(len(words)))


def _split_chat(rest):
    rest = " ".join(rest.split())
    if not rest:
        return None
    if " pesan " in f" {rest} ":
        name, message = rest.split(" pesan ", 1)
    else:
        parts = rest.split()
        if parts and parts[0] == "ke":
            parts = parts[1:]
        if len(parts) < 2:
            return None
        name, message = parts[0], " ".join(parts[1:])
    name = name.strip()
    message = " ".join(message.split())
    if not name or not message:
        return None
    return {"action": "chat", "name": name[:40], "message": message[:160]}


def parse(command):
    """Return {action, name, message} for WeChat, or None.

    action is chat, voice, or video. WhatsApp phrases return None.
    """
    words = _clean(command).split()
    if not words or len(words) > 18:
        return None
    if _mentions_whatsapp(words):
        return None
    if words[0] in {"wechat", "weixin"}:
        words = words[1:]
    elif words[:2] == ["we", "chat"]:
        words = words[2:]
    if not words:
        return None
    joined = " ".join(words)
    for prefix, action in (
        ("voice call", "voice"),
        ("panggilan suara", "voice"),
        ("telepon suara", "voice"),
        ("panggil suara", "voice"),
        ("video call", "video"),
        ("panggilan video", "video"),
        ("telepon video", "video"),
    ):
        if joined.startswith(prefix + " "):
            name = joined[len(prefix):].strip()
            if not name or _mentions_whatsapp(name.split()):
                return None
            return {"action": action, "name": name[:40], "message": ""}
    for prefix in ("kirim chat ke", "kirim pesan ke", "send chat to", "send a chat to", "kirim chat"):
        if joined == prefix or joined.startswith(prefix + " "):
            return _split_chat(joined[len(prefix):])
    return None


def _apps():
    path = Path(__file__).resolve().parent / "open_apps.py"
    spec = importlib.util.spec_from_file_location("asmamir_open_apps_wx", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("web/open_apps.py missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _title(hwnd, user32):
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value or ""


def _is_wechat_title(title):
    if "whatsapp" in title.lower():
        return False
    folded = title.lower()
    return "wechat" in folded or "weixin" in folded or "微信" in title


def _find_wechat(user32):
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _title(hwnd, user32)
        if _is_wechat_title(title):
            found.append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    return found[0] if found else None


def _focus(user32, hwnd):
    user32.ShowWindow(hwnd, 9)
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.25)
    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return True
    return _is_wechat_title(_title(fg, user32))


def _key(user32, vk, up=False):
    flags = 0x0002 if up else 0
    user32.keybd_event(vk, 0, flags, 0)


def _chord(user32, modifier, vk):
    _key(user32, modifier, False)
    _key(user32, vk, False)
    _key(user32, vk, True)
    _key(user32, modifier, True)


def _type_text(user32, text):
    for char in text:
        if ord(char) < 32:
            continue
        scan = ord(char)
        user32.keybd_event(0, scan, 0x0004, 0)
        user32.keybd_event(0, scan, 0x0004 | 0x0002, 0)


def _invoke_call(hwnd, kind):
    """Press the WeChat voice or video button if UI Automation exposes it."""
    hints = _VOICE_HINTS if kind == "voice" else _VIDEO_HINTS
    try:
        import comtypes
        from comtypes.client import CreateObject, GetModule

        comtypes.CoInitialize()
        GetModule("UIAutomationCore.dll")
        try:
            import comtypes.gen.UIAutomationClient as uia_mod  # type: ignore[import]
        except ImportError:
            return

        uia = CreateObject(uia_mod.CUIAutomation)
        root = uia.ElementFromHandle(hwnd)
        walker = uia.RawViewWalker
        pending = []
        first = walker.GetFirstChildElement(root)
        if first:
            pending.append((first, 1))
        seen = 0
        while pending and seen < 240:
            element, depth = pending.pop(0)
            seen += 1
            try:
                name = (element.CurrentName or "").strip().lower()
            except Exception:
                name = ""
            if name and any(hint in name for hint in hints):
                try:
                    pattern = element.GetCurrentPattern(10000)
                    if pattern is not None:
                        pattern.Invoke()
                        return True
                except Exception as exc:
                    print(f"WeChat call button found but not invoked ({exc}).")
                    return False
            if depth < 6:
                try:
                    child = walker.GetFirstChildElement(element)
                except Exception:
                    child = None
                while child:
                    pending.append((child, depth + 1))
                    try:
                        child = walker.GetNextSiblingElement(child)
                    except Exception:
                        break
    except Exception as exc:
        print(f"WeChat call: UI automation unavailable ({exc}).")
        return False
    print(f"WeChat {kind} call button was not exposed. No guessed click.")
    return False


def perform(plan, *, apps=None, user32=None, typer=None, caller=None, launch=None, sleeper=None):
    """Run a parsed WeChat plan. False if WhatsApp, or if WeChat cannot take the action.

    Tests pass stand-ins. The live path types only after the foreground window is WeChat.
    """
    global _LAST
    if not plan or plan.get("action") not in {"chat", "voice", "video"}:
        return False
    name = (plan.get("name") or "").strip()
    message = plan.get("message") or ""
    if not name or "whatsapp" in name.lower():
        return False
    if plan["action"] == "chat" and not str(message).strip():
        return False
    now = time.monotonic()
    if now - _LAST < _COOLDOWN:
        print("WeChat action: cooldown, skipped.")
        return True
    if user32 is None:
        import ctypes

        user32 = ctypes.windll.user32
    if apps is None and launch is None:
        apps = _apps()
    hwnd = _find_wechat(user32)
    if hwnd is None:
        started = False
        if launch is not None:
            started = bool(launch())
        elif apps is not None:
            path = apps.wechat_path()
            if path is None:
                print("WeChat action: app not found.")
                return False
            apps._gui_popen([str(path)], cwd=str(path.parent))
            started = True
        if not started:
            return False
        wait = sleeper or time.sleep
        for _ in range(16):
            wait(0.25)
            hwnd = _find_wechat(user32)
            if hwnd:
                break
    if hwnd is None or not _focus(user32, hwnd):
        print("WeChat action: window did not focus. Nothing typed.")
        return False
    if not _is_wechat_title(_title(user32.GetForegroundWindow(), user32)):
        print("WeChat action: foreground is not WeChat. Nothing typed.")
        return False
    _chord(user32, 0x11, 0x46)  # Ctrl+F
    time.sleep(0.15)
    _chord(user32, 0x11, 0x41)  # Ctrl+A
    (_type_text if typer is None else typer)(user32, name)
    _key(user32, 0x0D, False)
    _key(user32, 0x0D, True)
    time.sleep(0.35)
    if not _is_wechat_title(_title(user32.GetForegroundWindow(), user32)):
        print("WeChat action: left WeChat before the message. Stopped.")
        return False
    if plan["action"] == "chat":
        (_type_text if typer is None else typer)(user32, str(message).replace("\r", " ").replace("\n", " "))
        _key(user32, 0x0D, False)
        _key(user32, 0x0D, True)
        _LAST = now
        print(f"WeChat chat sent to {name}.")
        return True
    invoke = _invoke_call if caller is None else caller
    ok = bool(invoke(hwnd, plan["action"]))
    if ok:
        _LAST = now
        print(f"WeChat {plan['action']} call: {name}.")
    return ok
