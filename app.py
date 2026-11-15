import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import faulthandler
import json
import os
import queue
import sys
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import speech_recognition as sr
import threading
import time
from vosk import KaldiRecognizer, Model

def load_env_file():
    """Read .env beside app.py. Existing environment variables stay as they are."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value

load_env_file()
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

_fault_path = Path(os.environ.get("LOCALAPPDATA", ".")) / "asmamir" / "fault.log"
_fault_path.parent.mkdir(parents=True, exist_ok=True)
faulthandler.enable(file=open(_fault_path, "w", buffering=1), all_threads=True)

# =====================================================================
# 1. SUARA
# pyttsx3 di Windows harus dibuat di thread yang sama dengan runAndWait.
# Kalau dibuat di thread utama, antrean terisi tetapi tidak ada suara.
# =====================================================================
speech_queue = queue.Queue()
speaking = False
quiet_after = 0.0
cut_requested = False

recent_speech = []
speech_language = "en"
_indonesian_listener = None
_indonesian_voice = None
_indonesian_load = threading.Event()
_indonesian_done = threading.Event()

def line(key, **kwargs):
    """Fixed sentence for the current session language."""
    text = {
        "intro": {
            "en": "I can count fingers, look at the camera, read a page, or you can ask who I am and who you are.",
            "id": "Aku Asmamir. Aku bisa hitung jari, lihat kamera, baca halaman, atau kamu tanya siapa aku dan siapa kamu.",
        },
        "language_en": {
            "en": "English is on.",
            "id": "English is on.",
        },
        "language_id": {
            "en": "Baik, aku pakai bahasa Indonesia.",
            "id": "Baik, aku pakai bahasa Indonesia.",
        },
        "language_same": {
            "en": "English is already on.",
            "id": "Aku memang sudah pakai bahasa Indonesia.",
        },
        "no_indonesian_ear": {
            "en": "I cannot listen in Indonesian on this computer yet.",
            "id": "I cannot listen in Indonesian on this computer yet.",
        },
        "page_missing": {
            "en": "I could not see a page just now.",
            "id": "Halaman tadi tidak kelihatan.",
        },
        "page_blank": {
            "en": "I cannot read any text in this picture. Hold the page flat and closer.",
            "id": "Tulisannya tidak terbaca. Dekatkan halamannya, lalu tahan yang rata.",
        },
        "no_model": {
            "en": "I cannot see with the language model right now.",
            "id": "Aku belum bisa melihat lewat model bahasa.",
        },
        "no_picture": {
            "en": "I could not see a picture just now.",
            "id": "Gambar tadi tidak kelihatan.",
        },
        "fruit_on": {
            "en": "Fruit detection is on, {name}. Show the fruit to the camera.",
            "id": "Aku cari buah, {name}. Tunjukkan ke kamera.",
        },
        "count_on": {
            "en": "Detection is on, {name}. Show your fingers to the camera.",
            "id": "Aku hitung jari, {name}. Tunjukkan tanganmu.",
        },
        "shutdown": {
            "en": "Shutting down. Goodbye.",
            "id": "Aku matikan dulu. Sampai jumpa.",
        },
        "wake": {
            "en": "I'm here.",
            "id": "Saya di sini.",
        },
        "count_off": {
            "en": "ok, back to standby mode",
            "id": "ok, back to standby mode",
        },
        "deagle_on": {
            "en": "Desert Eagle overlay is on. Show a pistol grip.",
            "id": "Mode Desert Eagle nyala. Tunjukkan genggaman pistol.",
        },
        "dragon_on": {
            "en": "Dragon is on. Point with your index. Fist to breathe fire.",
            "id": "Naga nyala. Tunjuk dengan telunjuk. Kepal untuk napas api.",
        },
        "canvas_on": {
            "en": "Canvas is on. Draw with your index. Fist erases.",
            "id": "Kanvas nyala. Gambar dengan telunjuk. Kepal untuk hapus.",
        },
        "tab_closed": {
            "en": "Closed the {name} tab.",
            "id": "Tab {name} ditutup.",
        },
        "tab_missing": {
            "en": "I could not find a {name} tab in Chrome.",
            "id": "Tab {name} tidak ada di Chrome.",
        },
        "airbus_on": {
            "en": "Airbus is on. Pinch hold plus the other index orbits the jet 360. Pinch to pull a part, drag it onto the tray. Peace reassembles. Point for the part name. Two pinches measure. Fist then open pauses. One fist throttle. Two fists explode.",
            "id": "Airbus nyala. Cubit ditahan plus telunjuk lain orbit pesawat 360. Cubit cabut bagian, geser ke nampan. Peace merakit ulang. Telunjuk nama suku cadang. Dua cubit ukur. Kepal lalu buka jeda. Satu kepal gas. Dua kepal meledak.",
        },
        "filter_on": {
            "en": "Camera filters are on. Pinch or peace to cycle. Two hands open a portal.",
            "id": "Filter kamera nyala. Cubit atau peace untuk ganti filter. Dua tangan membuka portal.",
        },
        "anime_on": {
            "en": "Anime is on. Drag a rectangle around the picture.",
            "id": "Anime nyala. Seret kotak di sekeliling gambar.",
        },
        "anime_camera_on": {
            "en": "Anime is on. The camera still is stippled on black. Peace or one fist recapture the screen.",
            "id": "Anime nyala. Gambar kamera diarsir di atas hitam. Peace atau satu kepal tangkap layar lagi.",
        },
        "app_youtube": {
            "en": "YouTube is on.",
            "id": "YouTube nyala.",
        },
        "app_excel": {
            "en": "Excel is on.",
            "id": "Excel nyala.",
        },
        "app_browser": {
            "en": "Browser is on.",
            "id": "Browser nyala.",
        },
        "app_wechat": {
            "en": "WeChat is on.",
            "id": "WeChat nyala.",
        },
        "app_whatsapp": {
            "en": "WhatsApp is on.",
            "id": "WhatsApp nyala.",
        },
        "app_missing": {
            "en": "I could not find {name} on this computer.",
            "id": "{name} tidak ketemu di komputer ini.",
        },
        "yt_play": {
            "en": "Playing that on YouTube.",
            "id": "Memutar itu di YouTube.",
        },
        "yt_fail": {
            "en": "I could not open YouTube.",
            "id": "YouTube tidak bisa dibuka.",
        },
        "wx_chat": {
            "en": "Sent on WeChat.",
            "id": "Terkirim di WeChat.",
        },
        "wx_voice": {
            "en": "WeChat voice call.",
            "id": "Panggilan suara WeChat.",
        },
        "wx_video": {
            "en": "WeChat video call.",
            "id": "Panggilan video WeChat.",
        },
        "wx_fail": {
            "en": "I could not do that on WeChat.",
            "id": "Itu tidak bisa di WeChat.",
        },
        "fog_on": {
            "en": "Fog mirror is clear. An open mouth close to the camera fogs the whole glass quickly. One index finger wipes a small path. An open hand wipes a wider patch.",
            "id": "Cermin kabut bersih. Mulut terbuka dekat kamera mengabutkan seluruh kaca dengan cepat. Satu telunjuk menghapus sedikit. Telapak terbuka menghapus lebih lebar.",
        },
        "pointer_on": {
            "en": "The Windows cursor follows your index. Pinch clicks. Two fingers scroll.",
            "id": "Kursor Windows ikut telunjuk. Cubit klik. Dua jari menggulung.",
        },
        "pointer_off": {
            "en": "The hand mouse is off.",
            "id": "Mouse tangan mati.",
        },
        "deagle_off": {
            "en": "ok, back to standby mode",
            "id": "ok, back to standby mode",
        },
        "who_she": {
            "en": "I am {assistant}, {product}.",
            "id": "Aku {assistant}. {product}.",
        },
        "full_name": {
            "en": "Your full name is {full}. I call you {nick}.",
            "id": "Nama lengkapmu {full}. Aku panggil kamu {nick}.",
        },
        "nickname": {
            "en": "I call you {nick}.",
            "id": "Aku panggil kamu {nick}.",
        },
        "who_he": {
            "en": "You are {full}. I call you {nick}.",
            "id": "Kamu {full}. Aku panggil kamu {nick}.",
        },
        "fruit": {
            "en": "This is {article} {name}.",
            "id": "Ini {name}.",
        },
    }[key][speech_language]
    return text.format(**kwargs) if kwargs else text

ASSISTANT_NAME = "Asmamir"
PRODUCT_NAME = "Asmamir Computer Vision AI Assistant"


def _env_text(key):
    return os.environ.get(key, "").strip()


USER_FULL_NAME = _env_text("ASMAMIR_USER_FULL_NAME") or "User"
USER_NICKNAME = _env_text("ASMAMIR_USER_NICKNAME") or "friend"


def pronounce_names(text):
    """Swap written names for SAPI phonemes when .env provides them."""
    parts = USER_FULL_NAME.split()
    given = parts[0] if parts else ""
    family = parts[-1] if len(parts) > 1 else ""
    steps = (
        (USER_FULL_NAME, _env_text("ASMAMIR_SAID_FULL"), False),
        (given, _env_text("ASMAMIR_SAID_GIVEN"), False),
        (family, _env_text("ASMAMIR_SAID_FAMILY"), True),
        (USER_NICKNAME, _env_text("ASMAMIR_SAID_NICK"), True),
    )
    for written, said, bounded in steps:
        if not written or not said or written.lower() in {"user", "friend"}:
            continue
        pattern = rf"\b{re.escape(written)}\b" if bounded else re.escape(written)
        flags = 0 if bounded else re.IGNORECASE
        text = re.sub(pattern, said, text, flags=flags)
    return text

def speak(text):
    if text and not cut_requested:
        lang = speech_language
        spoken = pronounce_names(text) if lang == "en" else text
        recent_speech.append(re.sub(r"<[^>]+>", "", spoken).lower())
        del recent_speech[:-6]
        speech_queue.put((lang, spoken))

def cut_speech():
    """Stop the current sentence and drop anything still queued. Listening resumes."""
    global cut_requested, quiet_after
    cut_requested = True
    while True:
        try:
            speech_queue.get_nowait()
            speech_queue.task_done()
        except queue.Empty:
            break
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass
    quiet_after = time.time() + 0.15
    if not speaking:
        cut_requested = False
    print("Standing by.")

def _play_until_cut(audio, sample_rate):
    import sounddevice as sd
    sd.play(audio, sample_rate)
    while True:
        if cut_requested:
            sd.stop()
            return
        try:
            active = sd.get_stream().active
        except Exception:
            return
        if not active:
            return
        time.sleep(0.05)

def _speak_until_cut(voice, text, flags=0):
    """Speak one piece, polling so Space or 'diam' can stop it."""
    voice.Speak(text, flags | 1)  # SVSFlagsAsync
    while not voice.WaitUntilDone(80):
        if cut_requested:
            voice.Skip("Sentence", 1000)
            return

def speech_pieces(text, limit=220):
    """Split a long page into pieces Piper and Zira can finish."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return [text] if text else []
    sentences = re.split(r"(?<=[.!?;:])\s+", text)
    pieces = []
    buffer = ""
    for sentence in sentences:
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit)
            if cut < 40:
                cut = limit
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if buffer and len(buffer) + 1 + len(sentence) > limit:
            pieces.append(buffer)
            buffer = sentence
        else:
            buffer = f"{buffer} {sentence}".strip()
    if buffer:
        pieces.append(buffer)
    return [piece for piece in pieces if piece]


def heard_herself(text):
    compact = " ".join(text.split())
    if len(compact.split()) <= 2:
        return compact in recent_speech
    return any(compact in said or said in compact for said in recent_speech)

def _speaker():
    global speaking, quiet_after, cut_requested
    import comtypes.client
    import sounddevice as sd
    from piper import PiperVoice
    voice = comtypes.client.CreateObject("SAPI.SpVoice")
    voice.Volume = 100
    voice.Rate = 0
    chosen = "default"
    tokens = voice.GetVoices()
    for index in range(tokens.Count):
        token = tokens.Item(index)
        desc = str(token.GetDescription()).lower()
        if "zira" in desc or "hazel" in desc or "susan" in desc:
            voice.Voice = token
            chosen = str(token.GetDescription())
            break
    print(f"Voice engine ready: {chosen}")
    piper = None
    piper_path = Path(__file__).resolve().parent / "models" / "piper" / "id_ID-news_tts-medium.onnx"
    while True:
        lang, text = speech_queue.get()
        if cut_requested:
            speech_queue.task_done()
            cut_requested = False
            continue
        speaking = True
        try:
            plain = re.sub(r"<[^>]+>", "", text)
            if lang == "id":
                if piper is None:
                    piper = PiperVoice.load(str(piper_path))
                    print("Indonesian voice ready: Piper news.")
                pieces = speech_pieces(plain, limit=80)
                sample_rate = None
                gap = None
                for piece in pieces:
                    if cut_requested:
                        break
                    try:
                        chunks = list(piper.synthesize(piece))
                    except Exception as exc:
                        print(f"Piper skipped a piece: {exc}")
                        continue
                    if not chunks:
                        continue
                    sample_rate = chunks[0].sample_rate
                    if gap is None:
                        gap = np.zeros(int(sample_rate * 0.12), dtype=np.float32)
                    audio = np.concatenate([chunk.audio_float_array for chunk in chunks])
                    _play_until_cut(np.concatenate([audio, gap]), sample_rate)
                if sample_rate is None and not cut_requested:
                    raise RuntimeError("Piper returned no audio")
            elif "<phoneme" in text:
                xml = f'<speak version="1.0" xml:lang="en-US">{text}</speak>'
                _speak_until_cut(voice, xml, 8)  # SVSFIsXML
            else:
                for piece in speech_pieces(plain):
                    if cut_requested:
                        break
                    _speak_until_cut(voice, piece)
            if not cut_requested:
                print(f"Spoke: {plain}")
        except Exception as exc:
            print(f"Voice error: {exc}")
        finally:
            speaking = False
            if cut_requested:
                quiet_after = time.time() + 0.15
                cut_requested = False
            else:
                quiet_after = time.time() + 0.5
            speech_queue.task_done()

threading.Thread(target=_speaker, daemon=True).start()
speak(line("intro"))

# =====================================================================
# 2. INISIALISASI SPEECH-TO-TEXT (MENDENGAR SUARA)
# =====================================================================
def _mic_kind(name):
    """Why a PortAudio name is vague, and Hands-Free vs USB."""
    n = (name or "").lower()
    if "hands-free" in n or "handsfree" in n:
        return (
            "Bluetooth Hands-Free (HFP/HSP telephony, ~8 kHz). "
            "That is a phone-call mic, not USB capture. Poor for Vosk."
        )
    if "bluetooth" in n or "headset" in n or "a2dp" in n:
        return "Bluetooth / headset capture"
    if "usbaudio" in n or "usb audio" in n:
        return (
            "USB Audio Class 1.0 generic driver name, not a product brand. "
            "Windows labels many wired USB mics this way. This is USB, not Hands-Free."
        )
    if "emeet" in n:
        return "webcam microphone"
    if "array" in n or "intel smart sound" in n:
        return "laptop built-in array"
    if "nvidia broadcast" in n:
        return "virtual (NVIDIA Broadcast)"
    if "voice changer" in n or "virtual" in n:
        return "virtual audio"
    if "mapper" in n or "primary sound capture" in n:
        return "Windows mapper / primary capture"
    return ""


def _default_input_device():
    """Windows / PyAudio default capture index and name, or (None, '')."""
    try:
        pa = sr.Microphone.get_pyaudio().PyAudio()
        try:
            info = pa.get_default_input_device_info()
            return int(info["index"]), str(info.get("name") or "")
        finally:
            pa.terminate()
    except Exception:
        return None, ""


def _mic_preferences(choice):
    """Ordered ASMAMIR_MIC tokens. Comma-separated: first match wins. USB stays listed as fallback."""
    tokens = [part.strip() for part in (choice or "").split(",") if part.strip()]
    if not tokens:
        return []
    if len(tokens) == 1 and tokens[0].isdigit():
        return tokens
    if not any("usbaudio" in token.lower() for token in tokens):
        tokens.append("USBAudio1.0")
    return tokens


def _match_microphone(names, fragment):
    """First PortAudio input matching a name fragment, or (None, None, [])."""
    lowered = fragment.lower()
    matches = [(i, name) for i, name in enumerate(names) if lowered in name.lower()]
    inputs = [
        (i, name)
        for i, name in matches
        if "microphone" in name.lower() or "mic" in name.lower() or "usbaudio" in name.lower()
    ]
    if inputs:
        matches = inputs
    if not matches:
        return None, None, []
    index, name = matches[0]
    return index, name, matches


def _print_microphone_list(names, default_index=None, preferred="", fallbacks=None):
    preferred = (preferred or "").lower()
    fallback_needles = [item.lower() for item in (fallbacks or []) if item]
    print("Microphones (speech_recognition / PortAudio):")
    for i, name in enumerate(names):
        mark = "  [Windows default]" if default_index is not None and i == default_index else ""
        n = (name or "").lower()
        is_capture = "microphone" in n or "mic" in n or "usbaudio" in n
        if is_capture and preferred and preferred in n:
            mark += "  [preferred]"
        elif is_capture and any(needle in n for needle in fallback_needles):
            mark += "  [fallback]"
        kind = _mic_kind(name)
        extra = f"  — {kind}" if kind else ""
        print(f"  {i}: {name}{mark}{extra}")
    print(
        "Prefer NVIDIA Broadcast when that virtual mic is present. "
        "USBAudio1.0 stays listed as the wired USB fallback (USB Audio Class 1.0, not a brand). "
        "Hands-Free is Bluetooth telephony (calls, ~8 kHz) and must not feed Vosk."
    )


def _open_default_microphone(names, reason):
    default_index, default_name = _default_input_device()
    if default_index is not None and 0 <= default_index < len(names):
        default_name = names[default_index] or default_name
    label = default_name or "Windows default (name unavailable)"
    kind = _mic_kind(label)
    print(f"Vosk microphone: {label}  (Windows default{', ' + reason if reason else ''})")
    if kind:
        print(f"  why the name is vague: {kind}")
    if not os.environ.get("ASMAMIR_MIC", "").strip():
        print("  optional: set ASMAMIR_MIC=NVIDIA Broadcast,USBAudio1.0 in .env to prefer Broadcast then USB.")
    return sr.Microphone(), label


def _open_named_microphone(index, name, token, extra=""):
    global microphone_label
    microphone_label = name
    kind = _mic_kind(name)
    note = f", {extra}" if extra else ""
    print(f"Vosk microphone: {name}  (ASMAMIR_MIC={token!r}, index {index}{note})")
    if kind:
        print(f"  why the name is vague: {kind}")
    return sr.Microphone(device_index=index)


def open_microphone():
    """Prefer NVIDIA Broadcast, then USBAudio1.0, or the ASMAMIR_MIC list (fragments or index)."""
    global microphone_label
    choice = os.environ.get("ASMAMIR_MIC", "").strip()
    try:
        names = sr.Microphone.list_microphone_names()
    except OSError as exc:
        print(f"Could not list microphones ({exc}). Using the default.")
        microphone_label = "Windows default"
        return sr.Microphone()
    default_index, default_name = _default_input_device()
    preferences = _mic_preferences(choice)
    _print_microphone_list(
        names,
        default_index,
        preferred=preferences[0] if preferences else "",
        fallbacks=preferences[1:],
    )
    if default_name:
        print(f"Windows default input: {default_name}")
        kind = _mic_kind(default_name)
        if kind:
            print(f"  why the name is vague: {kind}")
    if not preferences:
        mic, microphone_label = _open_default_microphone(names, "")
        return mic
    for i, token in enumerate(preferences):
        if token.isdigit():
            index = int(token)
            if index < 0 or index >= len(names):
                print(f"ASMAMIR_MIC index {index} is not in the list.")
                continue
            extra = "fallback" if i else "preferred"
            return _open_named_microphone(index, names[index], token, extra)
        index, name, matches = _match_microphone(names, token)
        if index is None:
            nxt = preferences[i + 1] if i + 1 < len(preferences) else None
            if nxt:
                print(f"ASMAMIR_MIC {token!r} was not found. Trying {nxt!r}.")
            else:
                print(f"ASMAMIR_MIC {token!r} was not found.")
            continue
        if len(matches) > 1:
            print("Several microphones match ASMAMIR_MIC. Using the first:")
            for match_index, matched in matches:
                print(f"  {match_index}: {matched}")
        extra = f"fallback after {preferences[0]!r} missing" if i else "preferred"
        return _open_named_microphone(index, name, token, extra)
    print("ASMAMIR_MIC preferences were not found. Using the default microphone.")
    mic, microphone_label = _open_default_microphone(names, "ASMAMIR_MIC not found")
    return mic

microphone_label = "unresolved"
recognizer = sr.Recognizer()
microphone = open_microphone()
system_active = False  # Standby at startup. "count" / "hitung" turns finger tracking on.
deagle_active = False  # Overlay stays off until "desert eagle".
dragon_active = False  # Overlay stays off until "dragon".
canvas_active = False  # Overlay stays off until "draw" / "gambar" / "canvas".
airbus_active = False  # Overlay stays off until "airbus".
filter_active = False  # Overlay stays off until "filter" / "filter kamera".
fog_active = False  # Overlay stays off until "fog mirror".
anime_active = False  # Screen stipple stays off until "anime" / "stipple". No camera window.
_anime_mod = None
_fog_mod = None
anime_pending = None  # "screen" grabs the front Chrome window. Never "camera".
_anime_source = None  # "screen" places a finger box on the desktop.
_anime_ready = None  # Screen rect that has held still, waiting for peace.
_anime_parked = False  # Standby window moved aside so it does not cover the desktop.
_box_place = None
_monitor_bounds = None
shutdown_requested = False


def _reset_anime_place():
    """Drop the finger box. The camera thread closes its windows."""
    global _anime_source, _anime_ready, _monitor_bounds
    _anime_source = None
    _anime_ready = None
    _monitor_bounds = None
    if _box_place is not None:
        _box_place.reset()


def anime_reset():
    if _anime_mod is not None:
        _anime_mod.reset()


def set_session_mode(mode):
    """Exclusive count / fruit / overlay. None = standby."""
    global system_active, fruit_active, deagle_active, dragon_active
    global canvas_active, airbus_active, filter_active, fog_active, anime_active, anime_pending
    system_active = mode == "count"
    fruit_active = mode == "fruit"
    deagle_active = mode == "deagle"
    dragon_active = mode == "dragon"
    canvas_active = mode == "canvas"
    airbus_active = mode == "airbus"
    filter_active = mode == "filter"
    fog_active = mode == "fog"
    anime_active = mode == "anime"
    if mode != "anime":
        anime_pending = None
        anime_reset()
        _reset_anime_place()
    if mode is not None:
        from web import hologram_dance
        hologram_dance.leave()
    if mode == "fog":
        _load_fog().reset()
    elif _fog_mod is not None:
        _fog_mod.reset()


last_total_count = -1
stable_total = -1
stable_hits = 0

def profile_reply(command):
    """Answers about Asmamir Computer Vision AI Assistant and the user. None if this is not a profile question."""
    words = set(command.split())
    if speech_language == "id":
        if "lengkap" in words and "nama" in words:
            return line("full_name", full=USER_FULL_NAME, nick=USER_NICKNAME)
        if "panggilan" in words:
            return line("nickname", nick=USER_NICKNAME)
        if "siapa" in words and "kamu" in words:
            return line("who_she", assistant=ASSISTANT_NAME, product=PRODUCT_NAME)
        if ("siapa" in words and "saya" in words) or ("nama" in words and "saya" in words):
            return line("who_he", full=USER_FULL_NAME, nick=USER_NICKNAME)
        return None
    if "full" in words and "name" in words:
        return line("full_name", full=USER_FULL_NAME, nick=USER_NICKNAME)
    if "nickname" in words or "nick" in words or "call me" in command:
        return line("nickname", nick=USER_NICKNAME)
    if "who" in words and "you" in words or command in {"what are you", "what you"}:
        return line("who_she", assistant=ASSISTANT_NAME, product=PRODUCT_NAME)
    if "your" in words and "name" in words:
        return line("who_she", assistant=ASSISTANT_NAME, product=PRODUCT_NAME)
    if ("who" in words and "i" in words) or ("my" in words and "name" in words):
        return line("who_he", full=USER_FULL_NAME, nick=USER_NICKNAME)
    return None

VOSK_MODEL_DIR = Path(__file__).resolve().parent / "models" / "vosk-model-small-en-us-0.15"
print(f"Loading Vosk model from {VOSK_MODEL_DIR} ...")
vosk_model = Model(str(VOSK_MODEL_DIR))
print("Vosk model ready. Speech stays on this computer.")
OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_FALLBACK_MODELS = (
    "gemma4:12b",
    "llama3.2:latest",
    "qwen2.5-coder:14b",
    "llama3.1:8b",
    "deepseek-r1:14b",
)
OLLAMA_VISION_MODEL = None
OLLAMA_TEXT_MODEL = None
OLLAMA_MODEL = "gemma4:12b"
HERMES_HOST = (os.environ.get("ASMAMIR_HERMES_URL") or "").strip() or "http://127.0.0.1:8642"
HERMES_MODEL = "hermes-agent"
HERMES_ENV_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / ".env"


def _looks_like_openai_model(name):
    lowered = (name or "").strip().lower()
    if not lowered:
        return False
    return (
        lowered.startswith("gpt-")
        or lowered.startswith("chatgpt")
        or lowered.startswith("o1-")
        or lowered.startswith("o3-")
        or lowered.startswith("o4-")
        or "openai" in lowered
    )


def _ollama_name_matches(preferred, listed):
    left = (preferred or "").strip().lower()
    right = (listed or "").strip().lower()
    if not left or not right:
        return False
    if left == right:
        return True
    if right.startswith(left) or left.startswith(right):
        return True
    return left.split(":")[0] == right.split(":")[0]


def configured_ollama_model():
    """Primary local model from .env. gpt-4o-mini and other OpenAI names are rejected."""
    raw = os.environ.get("ASMAMIR_LLM_MODEL", "").strip() or "gemma4:12b"
    if _looks_like_openai_model(raw):
        return "gemma4:12b"
    for allowed in OLLAMA_FALLBACK_MODELS:
        if _ollama_name_matches(raw, allowed):
            return allowed
    return "gemma4:12b"


def warn_ignored_openai_env():
    """OpenAI keys, OpenAI URLs, and gpt-* model names never leave this PC."""
    key = os.environ.get("ASMAMIR_LLM_API_KEY", "").strip()
    if key:
        print("ASMAMIR_LLM_API_KEY is ignored. Never OpenAI cloud. Hermes then Ollama.")
    base = os.environ.get("ASMAMIR_LLM_BASE_URL", "").strip()
    if base:
        print("ASMAMIR_LLM_BASE_URL is ignored. Chat/look uses Hermes then Ollama.")
    raw = os.environ.get("ASMAMIR_LLM_MODEL", "").strip()
    if _looks_like_openai_model(raw):
        print(f"ASMAMIR_LLM_MODEL={raw} is OpenAI and wrong. Using gemma4:12b.")
    elif raw and not any(_ollama_name_matches(raw, allowed) for allowed in OLLAMA_FALLBACK_MODELS):
        print(f"ASMAMIR_LLM_MODEL={raw} is not in the Ollama chain. Using gemma4:12b.")


def _model_has_vision(name, caps_by_name):
    caps = [str(cap).lower() for cap in (caps_by_name.get(name) or [])]
    if "vision" in caps:
        return True
    return name.lower().startswith("gemma4")

def hermes_api_key():
    """Bearer for local Hermes /v1. .env first, then %LOCALAPPDATA%/hermes/.env."""
    key = (os.environ.get("ASMAMIR_HERMES_API_KEY") or "").strip()
    if key:
        return key
    if not HERMES_ENV_PATH.exists():
        return ""
    for line in HERMES_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("API_SERVER_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def hermes_is_up():
    try:
        urllib.request.urlopen(f"{HERMES_HOST}/health", timeout=1)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def ollama_is_up():
    try:
        urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=1)
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False

def list_ollama_models():
    """Installed Ollama models as (name, capabilities). Empty if Ollama is down."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []
    listed = []
    for item in body.get("models") or []:
        name = str(item.get("name") or item.get("model") or "").strip()
        if not name:
            continue
        caps = [str(cap).lower() for cap in (item.get("capabilities") or [])]
        listed.append((name, caps))
    return listed

def ollama_fallback_chain():
    """Installed models in .env order, then the rest of the five. Never OpenAI names."""
    primary = configured_ollama_model()
    preferred = (primary,) + tuple(model for model in OLLAMA_FALLBACK_MODELS if model != primary)
    catalog = list_ollama_models()
    names = [name for name, _caps in catalog]
    if not names:
        return list(preferred)
    chain = []
    for item in preferred:
        match = next((name for name in names if _ollama_name_matches(item, name)), None)
        if match and match not in chain:
            chain.append(match)
    return chain


def choose_ollama_models():
    """First vision model in the chain (gemma4:12b), then first text model."""
    catalog = list_ollama_models()
    caps_by_name = {name: caps for name, caps in catalog}
    chain = ollama_fallback_chain()
    vision = next((name for name in chain if _model_has_vision(name, caps_by_name)), None)
    text = chain[0] if chain else None
    return vision, text

def refresh_ollama_models():
    """Pick models from a live Ollama. Safe to call when Ollama is down."""
    global OLLAMA_VISION_MODEL, OLLAMA_TEXT_MODEL, OLLAMA_MODEL
    vision, text = choose_ollama_models()
    chain = ollama_fallback_chain()
    OLLAMA_VISION_MODEL = vision
    OLLAMA_TEXT_MODEL = text
    OLLAMA_MODEL = vision or text or configured_ollama_model()
    print(
        "Ollama fallback: "
        + " → ".join(chain or list(OLLAMA_FALLBACK_MODELS))
        + " at http://127.0.0.1:11434."
    )
    if vision:
        print(f"Ollama vision model: {vision}. Look/describe sends the camera JPEG.")
    elif text:
        print(
            f"Ollama has no vision model in the chain. Look/describe uses {text} "
            "as text only. No image is sent."
        )
    else:
        print("Ollama is up but lists none of the fallback models. Look/describe will fail softly.")
    if text and text != vision:
        print(f"Ollama text model: {text}.")
    return bool(vision or text)

def ensure_hermes():
    """Local Hermes OpenAI-compat API at 127.0.0.1:8642. Do not start the gateway from here."""
    if hermes_is_up():
        print(f"Hermes API is up at {HERMES_HOST}/health.")
        if not hermes_api_key():
            print("Hermes API_SERVER_KEY is missing. Chat/look will fall through to Ollama.")
        return True
    print(f"Hermes API is down at {HERMES_HOST}/health. Chat/look will try Ollama.")
    return False


def ensure_ollama():
    """Start ollama serve when the app starts, unless it is already listening."""
    if ollama_is_up():
        print("Ollama is already running at http://127.0.0.1:11434.")
        refresh_ollama_models()
        return True
    print("Starting ollama serve...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError:
        print("ollama was not found on PATH. Look/describe fails softly. Profile answers still work.")
        return False
    for _ in range(20):
        time.sleep(0.5)
        if ollama_is_up():
            print("Ollama is ready at http://127.0.0.1:11434.")
            refresh_ollama_models()
            return True
    print("Ollama did not answer in time. Look/describe fails softly. Profile answers still work.")
    return False

warn_ignored_openai_env()
ensure_hermes()
ensure_ollama()
print("Chat/look fallback: Hermes http://127.0.0.1:8642 → Ollama http://127.0.0.1:11434.")

VOSK_PHRASES = json.dumps([
    "asmamir",
    "hey asmamir",
    "as mamir",
    "who are you",
    "what are you",
    "what is your name",
    "who am i",
    "what is my name",
    "what is my full name",
    "what is my nickname",
    "count",
    "counting",
    "start count",
    "start counting",
    "hitung",
    "mulai hitung",
    "mulai menghitung",
    "stop counting",
    "stop hitung",
    "desert eagle",
    "deagle",
    "elang gurun",
    "senjata deagle",
    "pistol deagle",
    "dragon",
    "naga",
    "airbus",
    "air bus",
    "draw",
    "drawing",
    "start drawing",
    "gambar",
    "canvas",
    "kanvas",
    "open canvas",
    "air canvas",
    "filter",
    "filters",
    "filter kamera",
    "kamera filter",
    "camera filter",
    "anime",
    "stipple",
    "stipple anime",
    "stipple art",
    "anime stipple",
    "anime mode",
    "anime kamera",
    "anime camera",
    "kamera anime",
    "open youtube",
    "open you tube",
    "open excel",
    "open browser",
    "open chrome",
    "open wechat",
    "open we chat",
    "open weixin",
    "open whatsapp",
    "open whats app",
    "buka youtube",
    "buka excel",
    "buka browser",
    "buka wechat",
    "buka whatsapp",
    "youtube",
    "you tube",
    "excel",
    "browser",
    "wechat",
    "we chat",
    "weixin",
    "whatsapp",
    "whats app",
    "lihat",
    "standby",
    "posisi standby",
    "clear",
    "hapus",
    "red",
    "blue",
    "green",
    "yellow",
    "cyan",
    "merah",
    "biru",
    "hijau",
    "kuning",
    "stop deagle",
    "stop dragon",
    "stop airbus",
    "stop draw",
    "stop filter",
    "stop anime",
    "stop stipple",
    "stop stipple art",
    "berhenti deagle",
    "berhenti naga",
    "berhenti airbus",
    "berhenti gambar",
    "berhenti filter",
    "berhenti anime",
    "ignore my fingers",
    "ignore fingers",
    "shutdown",
    "shutdown and quit",
    "shut down and quit",
    "show fruit",
    "what do you see",
    "what is this",
    "look at this",
    "describe this",
    "read this",
    "read the book",
    "read the page",
    "read the text",
    "what does it say",
    "solve this",
    "solve this question",
    "calculate this",
    "answer this",
    "switch to bahasa",
    "switch to indonesian",
    "switch to english",
    "gunakan bahasa indonesia",
    "gunakan bahasa inggris",
    "mouse",
    "kursor",
    "stop mouse",
    "lepas kursor",
    "[unk]",
])
# Own grammar, checked before every other phrase. Exact words only.
CANVAS_PHRASES = json.dumps(["canvas", "draw", "drawing", "[unk]"])
# "stipple anime" is heard as "stipple" plus [unk]. "anime" is heard as "anime" plus [unk].
# "anime camera" stays out of this list so a trailing noise does not hide the word anime.
ANIME_PHRASES = json.dumps([
    "anime",
    "a me",
    "enemy",
    "stipple",
    "stipple anime",
    "stipple art",
    "stippled",
    "stippled anime",
    "anime stipple",
    "anime mode",
    "stop anime",
    "stop stipple",
    "stop stipple art",
    "restart anime",
    "[unk]",
])
# "close youtube" is heard as "close you tube".
CLOSE_PHRASES = json.dumps([
    "close youtube",
    "close you tube",
    "close airbus",
    "close desert eagle",
    "[unk]",
])
# Own grammar, checked before color and YouTube. Exact phrase only.
FOG_PHRASES = json.dumps(["fog mirror", "[unk]"])
WAKE_PHRASES = json.dumps(["asmamir", "hey asmamir", "as mamir", "asma mir", "[unk]"])
DANCE_PHRASES = json.dumps(["stop dance", "dance", "twerk", "rumba", "salsa", "[unk]"])
# Tiny grammar: full phrases only. One-word draw/airbus is too easy for noise.
MODE_PHRASES = json.dumps([
    "open canvas",
    "start drawing",
    "air canvas",
    "filter",
    "filters",
    "filter kamera",
    "kamera filter",
    "camera filter",
    "anime",
    "stipple",
    "stipple anime",
    "stipple art",
    "anime stipple",
    "anime mode",
    "anime kamera",
    "anime camera",
    "kamera anime",
    "open youtube",
    "open you tube",
    "open excel",
    "open browser",
    "open chrome",
    "open wechat",
    "open we chat",
    "open weixin",
    "open whatsapp",
    "open whats app",
    "buka youtube",
    "buka excel",
    "buka browser",
    "buka wechat",
    "buka whatsapp",
    "count",
    "counting",
    "start count",
    "start counting",
    "hitung",
    "mulai hitung",
    "mulai menghitung",
    "what do you see",
    "look at this",
    "describe this",
    "lihat",
    "standby",
    "shutdown",
    "mouse",
    "kursor",
    "stop mouse",
    "lepas kursor",
    "[unk]",
])
# Whole utterance only. A sentence that merely contains one of these words does not quit.
QUIT_PHRASES = json.dumps([
    "shutdown",
    "shut down",
    "shutdown and quit",
    "shut down and quit",
    "quit",
    "exit",
    "good bye",
    "goodbye",
    "[unk]",
])
RECORD_SNAP_PHRASES = json.dumps(["record snap", "records snap", "[unk]"])
STIPPLE_ARM_PHRASES = json.dumps(["start", "capture", "start capture", "take screenshot", "[unk]"])

def _register_phrase_grammar(label, grammar):
    """Build one small grammar at startup so a missing word is printed."""
    KaldiRecognizer(vosk_model, 16000, grammar)
    listed = [phrase for phrase in json.loads(grammar) if phrase != "[unk]"]
    print(f"{label} grammar registered: " + ", ".join(listed))


_register_phrase_grammar("Canvas", CANVAS_PHRASES)
_register_phrase_grammar("Anime", ANIME_PHRASES)
_register_phrase_grammar("Close tab", CLOSE_PHRASES)
_register_phrase_grammar("Quit", QUIT_PHRASES)
_register_phrase_grammar("Record snap", RECORD_SNAP_PHRASES)
_register_phrase_grammar("Stipple arm", STIPPLE_ARM_PHRASES)
_register_phrase_grammar("Dance", DANCE_PHRASES)
STANDBY_PHRASES = json.dumps(["standby", "stand by", "[unk]"])
_register_phrase_grammar("Standby", STANDBY_PHRASES)

def _vosk_text(audio, grammar):
    recognizer_vosk = KaldiRecognizer(vosk_model, 16000, grammar) if grammar else KaldiRecognizer(vosk_model, 16000)
    raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
    recognizer_vosk.AcceptWaveform(raw)
    text = json.loads(recognizer_vosk.FinalResult()).get("text", "").strip().lower()
    if not text:
        return ""
    tokens = text.split()
    if any(token == "[unk]" for token in tokens):
        return ""
    return text


def _vosk_phrase(audio, grammar):
    """Like _vosk_text, but a trailing [unk] does not erase a real phrase.

    The anime grammar returns 'anime [unk]' for the spoken word anime.
    """
    recognizer_vosk = KaldiRecognizer(vosk_model, 16000, grammar) if grammar else KaldiRecognizer(vosk_model, 16000)
    raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
    recognizer_vosk.AcceptWaveform(raw)
    text = json.loads(recognizer_vosk.FinalResult()).get("text", "").strip().lower()
    tokens = [token for token in text.split() if token != "[unk]"]
    return " ".join(tokens)


def _audio_too_short(audio, seconds=0.35):
    raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
    return len(raw) < int(16000 * 2 * seconds)


_SNAP_MATCH = 0.82
_snap_templates = None


def _burst_envelope(samples):
    """30 ms around the peak, in 1 ms energy bins. Sample rate is 16 kHz."""
    if samples.size < 160:
        return None
    center = int(np.argmax(np.abs(samples)))
    half = 240
    window = samples[max(0, center - half):center + half].astype(np.float32)
    window = window - float(window.mean())
    hop = 16
    usable = (window.size // hop) * hop
    if usable < hop:
        return None
    energy = np.abs(window[:usable]).reshape(-1, hop).mean(axis=1)
    norm = float(np.linalg.norm(energy))
    if norm < 1:
        return None
    return energy / norm


def _snap_envelopes():
    """snap-1.wav through snap-5.wav, converted to the same 16 kHz envelope."""
    global _snap_templates
    if _snap_templates is not None:
        return _snap_templates
    folder = Path(__file__).resolve().parent / "models" / "snaps"
    found = []
    if folder.is_dir():
        import wave
        for path in sorted(folder.glob("snap-*.wav")):
            try:
                with wave.open(str(path), "rb") as handle:
                    raw = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32)
                    rate = int(handle.getframerate())
            except Exception:
                continue
            if rate != 16000 and raw.size > 1:
                count = int(raw.size * 16000 / rate)
                raw = np.interp(
                    np.linspace(0, 1, count),
                    np.linspace(0, 1, raw.size),
                    raw,
                ).astype(np.float32)
            shape = _burst_envelope(raw)
            if shape is not None:
                found.append(shape)
    _snap_templates = found
    return found


def _matches_saved_snap(audio):
    """A short burst that matches a saved snap. Speech and a click stay below 0.82."""
    raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
    heard = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if heard.size < 160:
        return False
    peak = float(np.max(np.abs(heard)))
    if peak < 3500:
        return False
    loud = np.abs(heard) >= max(3000.0, peak / 3.0)
    if float(np.count_nonzero(loud)) / 16000.0 > 0.25:
        return False
    shape = _burst_envelope(heard)
    templates = _snap_envelopes()
    if shape is None or not templates:
        return False
    best = 0.0
    for template in templates:
        width = min(shape.size, template.size)
        score = abs(float(np.dot(shape[:width], template[:width])))
        best = max(best, score)
    if best >= _SNAP_MATCH:
        print(f"Anime snap sound match {best:.2f}. Threshold {_SNAP_MATCH:.2f}.", flush=True)
        return True
    print(f"Anime snap sound rejected {best:.2f}. Needs >= {_SNAP_MATCH:.2f}.", flush=True)
    return False


def _audio_snap(audio):
    """A finger snap on the listener mic: one short loud peak, not a sentence."""
    raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
    samples = np.frombuffer(raw, dtype=np.int16)
    if samples.size < 160:
        return False
    peak = int(np.max(np.abs(samples)))
    if peak < 8000:
        return False
    loud = np.abs(samples) >= max(4000, peak // 3)
    loud_seconds = float(np.count_nonzero(loud)) / 16000.0
    span = samples.size / 16000.0
    return span <= 1.2 and loud_seconds <= 0.4


_clap_watch = None


def _heard_double_clap(audio):
    """True when this clip holds two claps. Uses the listener mic. No second stream."""
    global _clap_watch
    if _clap_watch is None:
        from web.clap_wake import ClapWatch
        _clap_watch = ClapWatch()
    raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
    if len(raw) < 4:
        return False
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return _clap_watch.feed(samples, 16000)


def _confirmed_keep(predicate, label, mode_hit, hinted, open_text, need_open=False):
    """Tiny MODE grammar may invent a word from noise. Need hinted or open agreement.

    Canvas/airbus set need_open so a forced one-word grammar hit cannot switch the overlay.
    """
    if need_open:
        if open_text and predicate(open_text):
            print(f"{label} phrase kept: {open_text}")
            return [open_text]
        if mode_hit and predicate(mode_hit):
            print(f"Ignored forced phrase '{mode_hit}'. Open hearing: '{open_text or 'unclear'}'")
        elif hinted and predicate(hinted):
            print(f"Ignored forced phrase '{hinted}'. Open hearing: '{open_text or 'unclear'}'")
        return []
    for text in (hinted, open_text):
        if text and predicate(text):
            print(f"{label} phrase kept: {text}")
            return [text]
    if mode_hit and predicate(mode_hit):
        print(f"Ignored forced phrase '{mode_hit}'. Open hearing: '{open_text or 'unclear'}'")
    return []

def ensure_indonesian_listener():
    """Ask the camera thread to load the Indonesian listener. False if that fails."""
    if _indonesian_listener is not None:
        return True
    print("Loading the Indonesian listener on the camera thread...")
    _indonesian_done.clear()
    _indonesian_load.set()
    if not _indonesian_done.wait(timeout=180):
        print("Indonesian listener timed out.")
        return False
    return _indonesian_listener is not None

def load_indonesian_listener():
    """Create Whisper on the camera thread. Loading it from the microphone thread exits the process."""
    global _indonesian_listener
    if not _indonesian_load.is_set() or _indonesian_listener is not None:
        return
    try:
        from faster_whisper import WhisperModel
        _indonesian_listener = WhisperModel(
            "tiny",
            device="cpu",
            compute_type="int8",
            download_root=str(Path(__file__).resolve().parent / "models" / "whisper"),
        )
        print("Indonesian listener ready. Speech stays on this computer.")
    except Exception as exc:
        print(f"Indonesian listener unavailable: {exc}")
    finally:
        _indonesian_load.clear()
        _indonesian_done.set()

def switch_target(command):
    """en, id, or None. English is tested first so 'gunakan bahasa inggris' stays English."""
    words = set(command.split())
    if "english" in words or "inggris" in words:
        return "en"
    if "indonesian" in words or "indonesia" in words or "bahasa" in words:
        return "id"
    return None

def _whisper_text(samples, language):
    if _indonesian_listener is None:
        return ""
    segments, _info = _indonesian_listener.transcribe(samples, language=language)
    return " ".join(segment.text for segment in segments).strip().lower()

def _whole_phrase(command):
    return " ".join((command or "").replace("-", " ").lower().split())


_RECORD_EXACT = {"record snap", "records snap"}
_DANCE_EXACT = {"twerk", "rumba", "salsa"}
_STIPPLE_ARM = {"start", "capture", "start capture", "take screenshot"}


_QUIT_EXACT = {
    "shutdown",
    "shut down",
    "shutdown and quit",
    "shut down and quit",
    "quit",
    "exit",
    "good bye",
    "goodbye",
    "matikan",
}


def _kept_command(open_text, quit_hit="", record_hit="", dance_hit="", stipple_hit=""):
    """Whole utterance only. A later grammar must not replace these phrases."""
    whole = _whole_phrase(open_text)
    record = _whole_phrase(record_hit)
    # The record-snap grammar wins even when open text rewrites the same clip.
    if record in _RECORD_EXACT or whole in _RECORD_EXACT:
        print("Record snap kept")
        return "record snap"
    if whole in _QUIT_EXACT:
        print(f"Shutdown phrase kept: {whole}")
        return whole
    if quit_hit in _QUIT_EXACT and whole in {"", quit_hit}:
        print(f"Shutdown phrase kept: {quit_hit}")
        return quit_hit
    dance = _whole_phrase(dance_hit)
    if whole in _DANCE_EXACT:
        print(f"Dance kept: {whole}")
        return whole
    if dance in _DANCE_EXACT and whole in {"", dance}:
        print(f"Dance kept: {dance}")
        return dance
    if whole in _STIPPLE_ARM:
        print(f"Stipple arm kept: {whole}")
        return whole
    stipple = _whole_phrase(stipple_hit)
    if stipple in _STIPPLE_ARM and whole in {"", stipple}:
        print(f"Stipple arm kept: {stipple}")
        return stipple
    return ""


def transcripts_from(audio):
    """Known phrases first. Stop is accepted only if open recognition agrees."""
    if speech_language == "id" and _indonesian_listener is not None:
        try:
            raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            heard = _whisper_text(samples, "id")
            english = _whisper_text(samples, "en")
        except Exception as exc:
            print(f"Indonesian listener error: {exc}")
            return []
        texts = [text for text in (heard, english) if _whole_phrase(text)]
        if texts and all(_whole_phrase(text) in _RECORD_EXACT for text in texts):
            print("Record snap kept")
            return ["record snap"]
        if texts and all(_whole_phrase(text) in _QUIT_EXACT for text in texts):
            phrase = _whole_phrase(texts[0])
            print(f"Shutdown phrase kept: {phrase}")
            return [phrase]
        if texts and all(_whole_phrase(text) in _DANCE_EXACT for text in texts):
            phrase = _whole_phrase(texts[0])
            print(f"Dance kept: {phrase}")
            return [phrase]
        canvas_exact = _canvas_exact(heard) or _canvas_exact(english)
        if canvas_exact:
            print(f"Canvas kept: {canvas_exact}")
            return [canvas_exact]
        anime_exact = _anime_exact(heard) or _anime_exact(english)
        if anime_exact:
            if anime_exact.startswith("stop ") or anime_exact.startswith("berhenti "):
                print(f"Anime stop kept: {anime_exact}")
            else:
                print(f"Anime kept: {anime_exact}")
            return [anime_exact]
        if (heard or "").strip() == "stop dance" or (english or "").strip() == "stop dance":
            print("Stop dance kept")
            return ["stop dance"]
        if (heard or "").strip() == "dance" or (english or "").strip() == "dance":
            print("Dance kept")
            return ["dance"]
        for candidate in (heard, english):
            if candidate and wants_wake_name(candidate):
                print(f"Wake name kept: {candidate}")
                return ["asmamir"]
            if candidate and (wants_stop(candidate) or wants_standby(candidate)):
                print(f"Camera screen kept: {candidate}")
                return [candidate]
            if _close_kind(candidate):
                print(f"Close tab kept: {candidate}")
                return [candidate]
        if _is_fog_mirror(heard) or _is_fog_mirror(english):
            print("Fog mirror kept")
            return ["fog mirror"]
        guesses = [heard] if heard else []
        if english and english not in guesses and (
            switch_target(english) == "en"
            or "shutdown" in english.split()
            or wants_canvas(english)
            or wants_filter(english)
            or wants_anime(english)
            or wants_open_app(english)
            or wants_youtube_play(english)
            or wants_wechat_action(english)
            or wants_fog(english)
            or wants_pointer(english)
            or wants_look(english)
            or wants_airbus(english)
            or wants_standby(english)
            or wants_clear_draw(english)
            or wants_pen_color(english)
            or wants_counting(english)
        ):
            guesses.append(english)
        return guesses
    open_first = _whole_phrase(_vosk_text(audio, None))
    if _standby_only(open_first):
        print(f"Standby phrase kept: {open_first}")
        return [open_first]
    kept = _kept_command(
        _vosk_text(audio, None),
        _vosk_phrase(audio, QUIT_PHRASES),
        _vosk_phrase(audio, RECORD_SNAP_PHRASES),
        _vosk_phrase(audio, DANCE_PHRASES),
        _vosk_phrase(audio, STIPPLE_ARM_PHRASES),
    )
    if kept:
        return [kept]
    open_restart = _whole_phrase(_vosk_text(audio, None))
    anime_phrase = _whole_phrase(_vosk_phrase(audio, ANIME_PHRASES))
    if open_restart == "restart anime" or (
        anime_phrase == "restart anime" and open_restart in {"", "restart anime"}
    ):
        print("Restart anime kept.")
        return ["restart anime"]
    anime_hit = _vosk_phrase(audio, ANIME_PHRASES)
    anime_canon = _anime_exact(anime_hit)
    # Bare "art" is not in the forced grammar. A one-word guess must not
    # replace standby, youtube, or any other sentence.
    if anime_canon == "art":
        anime_canon = ""
    if _anime_starts(anime_canon):
        print(f"Anime kept: {anime_canon}")
        return [anime_canon]
    if anime_canon.startswith("stop ") or anime_canon.startswith("berhenti "):
        print(f"Anime stop kept: {anime_canon}")
        return [anime_canon]
    close_hit = _vosk_phrase(audio, CLOSE_PHRASES)
    if _close_kind(close_hit):
        print(f"Close tab kept: {close_hit}")
        return [close_hit]
    fog_hit = _vosk_text(audio, FOG_PHRASES)
    if fog_hit == "fog mirror":
        print("Fog mirror kept")
        return ["fog mirror"]
    mode_hit = _vosk_text(audio, MODE_PHRASES)
    hinted = _vosk_text(audio, VOSK_PHRASES)
    open_text = _vosk_text(audio, None)
    wake_hit = _vosk_phrase(audio, WAKE_PHRASES)
    dance_hit = _vosk_phrase(audio, DANCE_PHRASES)
    open_anime = _anime_exact(open_text)
    if _anime_starts(open_anime):
        print(f"Anime kept: {open_anime}")
        return [open_anime]
    if open_anime.startswith("stop ") or open_anime.startswith("berhenti "):
        print(f"Anime stop kept: {open_anime}")
        return [open_anime]
    if dance_hit == "stop dance" or (open_text or "").strip() == "stop dance":
        print("Stop dance kept")
        return ["stop dance"]
    if dance_hit == "dance" or (open_text or "").strip() == "dance":
        print("Dance kept")
        return ["dance"]
    if wants_wake_name(wake_hit) or wants_wake_name(open_text) or wants_wake_name(hinted):
        print("Wake name kept")
        return ["asmamir"]
    ordered = []
    for text in (mode_hit, hinted, open_text):
        if text and text not in ordered:
            ordered.append(text)
    for text in (open_text, mode_hit, hinted):
        if text and (wants_stop(text) or wants_standby(text)):
            agreed = (
                text == open_text
                or not open_text
                or wants_stop(open_text)
                or wants_standby(open_text)
            )
            if agreed:
                print(f"Camera screen kept: {text}")
                return [text]
    count_hits = _confirmed_keep(
        lambda text: wants_counting(text) and not wants_stop(text),
        "Count",
        mode_hit,
        hinted,
        open_text,
    )
    if count_hits:
        return count_hits
    if open_text and wants_youtube_play(open_text):
        print(f"YouTube play kept: {open_text}")
        return [open_text]
    if open_text and wants_wechat_action(open_text):
        print(f"WeChat action kept: {open_text}")
        return [open_text]
    canvas_hits = _confirmed_keep(
        lambda text: wants_canvas(text) and not wants_canvas_off(text),
        "Canvas",
        mode_hit,
        hinted,
        open_text,
        need_open=True,
    )
    if canvas_hits:
        return canvas_hits
    filter_hits = _confirmed_keep(
        lambda text: wants_filter(text) and not wants_filter_off(text),
        "Filter",
        mode_hit,
        hinted,
        open_text,
    )
    if filter_hits:
        return filter_hits
    anime_hits = _confirmed_keep(
        lambda text: wants_anime(text) and not wants_anime_off(text),
        "Anime",
        mode_hit,
        hinted,
        open_text,
    )
    if anime_hits:
        return anime_hits
    fog_hits = _confirmed_keep(
        lambda text: wants_fog(text) and not wants_fog_off(text),
        "Fog",
        mode_hit,
        hinted,
        open_text,
        need_open=True,
    )
    if fog_hits:
        return fog_hits
    pointer_hits = _confirmed_keep(
        wants_pointer,
        "Mouse",
        mode_hit,
        hinted,
        open_text,
    )
    if pointer_hits:
        return pointer_hits
    open_app_hits = _confirmed_keep(
        wants_open_app,
        "Open app",
        mode_hit,
        hinted,
        open_text,
    )
    if open_app_hits:
        return open_app_hits
    look_hits = _confirmed_keep(
        wants_look,
        "Look",
        mode_hit,
        hinted,
        open_text,
    )
    if look_hits:
        return look_hits
    airbus_hits = _confirmed_keep(
        lambda text: wants_airbus(text) and not wants_airbus_off(text),
        "Airbus",
        mode_hit,
        hinted,
        open_text,
        need_open=True,
    )
    if airbus_hits:
        return airbus_hits
    if hinted in {"stop counting", "ignore my fingers", "ignore fingers"}:
        ignore_heard = hinted.startswith("ignore") and "ignore" in open_text and "finger" in open_text
        if hinted not in open_text and not ignore_heard:
            print(f"Ignored forced phrase '{hinted}'. Open hearing: '{open_text or 'unclear'}'")
            return [open_text] if open_text else []
    open_canvas = bool(open_text and wants_canvas(open_text))
    open_airbus = bool(open_text and wants_airbus(open_text))
    open_fog = bool(open_text and wants_fog(open_text))
    open_pointer = bool(open_text and wants_pointer(open_text))
    ordered = [
        text for text in ordered
        if not (
            (wants_canvas(text) and not open_canvas)
            or (wants_airbus(text) and not open_airbus)
            or (wants_fog(text) and not open_fog)
            or (wants_pointer(text) and not open_pointer)
        )
    ]
    return ordered

frame_lock = threading.Lock()
latest_jpeg = b""
latest_frame = None
vision_busy = False
vision_label = "Looking"
_page_reader = None

def finger_context():
    """Finger text for the model. Empty once counting has been turned off."""
    if speech_language == "id":
        if not system_active or last_total_count < 0:
            return "Jangan sebut jumlah jari. Penghitungan sedang mati."
        return f"Jumlah jari yang terakhir {last_total_count}. Pakai angka itu saja."
    if not system_active or last_total_count < 0:
        return (
            "Finger counting is off. Do not mention fingers, a finger count, "
            "or how many fingers are raised."
        )
    return (
        f"The latest finger count is {last_total_count}. Use that number and no other."
    )

def identity_rule():
    return (
        f"Your name is {ASSISTANT_NAME}. You are {PRODUCT_NAME}. "
        f"You are not {USER_NICKNAME}. {USER_NICKNAME} is the person speaking to you. "
        f"His full name is {USER_FULL_NAME}. He created you. Call him {USER_NICKNAME}. "
        f"Never say that you are {USER_NICKNAME}, and never say that your name is {USER_FULL_NAME}."
    )

def reply_rule():
    if speech_language == "id":
        return (
            "Jawab dalam bahasa Indonesia lisan, satu atau dua kalimat pendek. "
            "Langsung ke inti. Jangan pembuka, jangan minta maaf, jangan mengulang pertanyaan."
        )
    return (
        "Reply in spoken English in one or two short sentences. "
        "Be direct. No greeting, no apology, and do not restate the question."
    )

_MATH_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "nol": "0", "satu": "1", "dua": "2", "tiga": "3", "empat": "4",
    "lima": "5", "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9", "sepuluh": "10",
}

def _spoken_expr(expr):
    """Turn a SymPy result into a short spoken phrase."""
    from sympy import Integer, Rational, simplify
    expr = simplify(expr)
    indonesian = speech_language == "id"
    if not expr.free_symbols and expr.is_number:
        if isinstance(expr, Integer) or getattr(expr, "is_Integer", False):
            return str(int(expr))
        if isinstance(expr, Rational):
            joiner = " per " if indonesian else " over "
            return f"{expr.p}{joiner}{expr.q}"
        shown = str(expr.evalf(8))
    else:
        shown = str(expr)
    power = " pangkat " if indonesian else " to the power "
    over = " per " if indonesian else " over "
    shown = shown.replace("**", power).replace("*", " ").replace("/", over)
    return re.sub(r"\s+", " ", shown).strip()

def _math_expression(text):
    from sympy import oo
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )
    cleaned = text.replace("^", "**")
    cleaned = re.sub(r"[^0-9a-z+\-*/().\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)
    if not cleaned or not re.search(r"\d|[a-z]", cleaned):
        return None
    transformations = standard_transformations + (implicit_multiplication_application,)
    return parse_expr(cleaned, transformations=transformations, local_dict={"oo": oo})

def math_reply(command):
    """Exact arithmetic or calculus. None when this is not a calculation."""
    from sympy import SympifyError, diff, integrate, limit, oo, symbols
    words = [_MATH_WORDS.get(word, word) for word in re.sub(r"[?!,]", " ", command).split()]
    text = " ".join(words)
    text = re.sub(
        r"\b(what is|whats|what's|calculate|compute|hitung|hitungkan|berapa|hasil dari|tolong|please)\b",
        " ",
        text,
    )
    text = re.sub(r"\b(sin|cos|tan|log|exp|sqrt|ln)\s+([a-z0-9]+)", r"\1(\2)", text)
    text = re.sub(r"(\d)\s+per\s+", r"\1 / ", text)
    text = re.sub(r"\bdivided by\b|\bbagi\b|\bover\b", " / ", text)
    text = re.sub(r"\bmultiplied by\b|\btimes\b|\bkali\b", " * ", text)
    text = re.sub(r"\bplus\b|\badd\b|\btambah\b", " + ", text)
    text = re.sub(r"\bminus\b|\bsubtract\b|\bkurang\b", " - ", text)
    text = re.sub(r"\bsquared\b|\bkuadrat\b", " **2 ", text)
    text = re.sub(r"\bcubed\b", " **3 ", text)
    text = re.sub(r"\bto the power of\b|\bpangkat\b", " ** ", text)
    text = re.sub(r"\binfinity\b|\binfinite\b|\btak hingga\b", " oo ", text)
    text = re.sub(r"\s+", " ", text).strip()
    indonesian = speech_language == "id"
    try:
        limit_match = re.search(
            r"\b(?:limit of|limit)\b\s+(.+?)\s+\b(?:as|saat)\b\s+([a-z])\s+\b(?:approaches|mendekati)\b\s+(.+)$",
            text,
        )
        if limit_match:
            body, name, point = limit_match.groups()
            variable = symbols(name)
            point_expr = oo if point.strip() in {"oo", "infinity"} else _math_expression(point)
            value = limit(_math_expression(body), variable, point_expr)
            spoken = _spoken_expr(value)
            return f"Limitnya {spoken}." if indonesian else f"The limit is {spoken}."
        derivative_match = re.search(r"\b(?:derivative of|derivative|turunan dari|turunan)\b\s+(.+)$", text)
        if derivative_match:
            body = _math_expression(derivative_match.group(1))
            if body is None:
                return None
            variable = symbols("x")
            if body.free_symbols:
                variable = sorted(body.free_symbols, key=str)[0]
            spoken = _spoken_expr(diff(body, variable))
            return f"Turunannya {spoken}." if indonesian else f"The derivative is {spoken}."
        integral_match = re.search(r"\b(?:integral of|integral)\b\s+(.+)$", text)
        if integral_match:
            integral_text = re.sub(r"\bd[a-z]\b", " ", integral_match.group(1))
            body = _math_expression(integral_text)
            if body is None:
                return None
            variable = symbols("x")
            if body.free_symbols:
                variable = sorted(body.free_symbols, key=str)[0]
            spoken = _spoken_expr(integrate(body, variable))
            if indonesian:
                return f"Integralnya {spoken}, ditambah konstanta."
            return f"The integral is {spoken}, plus a constant."
        if not re.search(r"\d", text) or not re.search(r"[+\-*/]", text):
            return None
        spoken = _spoken_expr(_math_expression(text))
        return f"Hasilnya {spoken}." if indonesian else f"The answer is {spoken}."
    except (SympifyError, TypeError, ValueError, AttributeError, SyntaxError):
        if re.search(r"\b(derivative|integral|limit|turunan)\b", text) or (
            re.search(r"\d", text) and re.search(r"[+\-*/]", text)
        ):
            return "Itu tidak bisa dihitung." if indonesian else "I could not calculate that."
        return None

def normalize_written_math(text):
    """Turn camera text such as '2 x 8 = ?' into a calculation phrase."""
    cleaned = text.lower()
    cleaned = cleaned.replace("×", "*").replace("∙", "*").replace("÷", "/")
    cleaned = cleaned.replace("−", "-").replace("–", "-").replace("—", "-")
    cleaned = cleaned.replace("²", "**2").replace("³", "**3").replace("^", "**")
    cleaned = re.sub(
        r"(\d+(?:\.\d+)?)\s*%\s*(?:of|from|dari)\s*(\d+(?:\.\d+)?)",
        r"(\1/100)*\2",
        cleaned,
    )
    cleaned = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:of|from|dari)\s*(\d+(?:\.\d+)?)\s*%",
        r"(\2/100)*\1",
        cleaned,
    )
    cleaned = re.sub(r"d\s*/\s*d\s*([a-z])", r" derivative of ", cleaned)
    cleaned = re.sub(r"(\d+)\s*/\s*(\d+)", r"(\1/\2)", cleaned)
    cleaned = re.sub(r"(?<=[\d)])\s*x\s*(?=[\d(])", " * ", cleaned)
    cleaned = re.sub(r"=\s*\?+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" =")
    return cleaned

_FORMULA_WORDS = {
    "derivative", "integral", "limit", "turunan",
    "sin", "cos", "tan", "log", "exp", "sqrt", "ln", "oo",
}

def _is_short_formula(cleaned):
    """True only for one short formula. Prose that happens to contain '=' is not."""
    if not cleaned or len(cleaned) > 80 or not re.search(r"\d", cleaned):
        return False
    prose = [
        word for word in re.findall(r"[a-z]+", cleaned)
        if len(word) > 3 and word not in _FORMULA_WORDS
    ]
    if len(prose) >= 3:
        return False
    if not re.search(r"=|\d\s*[*+/^]\s*\d|derivative|integral|limit|turunan|\*\*", cleaned):
        return False
    if "=" in cleaned:
        left, right = cleaned.split("=", 1)
        for side in (left.strip(), right.replace("?", "").strip()):
            if not side or len(side) > 40:
                return False
            if re.search(r"[a-z]{4,}", side) and not re.search(
                r"\b(derivative|integral|limit|turunan)\b", side
            ):
                return False
    return True

def solve_written(text):
    """Answer a written problem. None when the text is not a calculation."""
    from sympy import Eq, Expr, SympifyError, solve
    try:
        cleaned = normalize_written_math(text)
        if not _is_short_formula(cleaned):
            return None
        indonesian = speech_language == "id"
        if "=" in cleaned:
            left, right = cleaned.split("=", 1)
            right = right.replace("?", "").strip()
            left = left.strip()
            if right:
                equation = Eq(_math_expression(left), _math_expression(right))
                symbols_in = list(equation.free_symbols)
                if symbols_in:
                    values = solve(equation, symbols_in[0])
                    if not values:
                        return None
                    name = str(symbols_in[0])
                    spoken = " and ".join(_spoken_expr(value) for value in values)
                    if indonesian:
                        return f"{name} sama dengan {spoken}."
                    return f"{name} equals {spoken}."
                lhs, rhs = equation.lhs, equation.rhs
                if isinstance(lhs, Expr) and isinstance(rhs, Expr) and lhs.equals(rhs):
                    return "Itu benar." if indonesian else "That is true."
                return "Itu salah." if indonesian else "That is false."
        if not re.search(r"[+\-*/]|derivative|integral|limit|turunan", cleaned):
            return None
        return math_reply(cleaned)
    except (TypeError, ValueError, AttributeError, SyntaxError, SympifyError):
        return None

def wants_solve(command):
    words = set(command.split())
    if words & {"solve", "kerjakan", "calculate", "compute"}:
        return True
    if "answer" in words and "this" in words:
        return True
    return "hitung" in words and bool(words & {"ini", "itu", "soal", "this", "problem"})

def _hermes_messages(messages):
    """Ollama-style messages (optional images) → OpenAI chat content for Hermes /v1."""
    out = []
    for msg in messages:
        role = msg.get("role") or "user"
        text = msg.get("content") or ""
        images = msg.get("images") or []
        if images:
            parts = []
            if text:
                parts.append({"type": "text", "text": text})
            for image in images:
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                })
            out.append({"role": role, "content": parts})
        else:
            out.append({"role": role, "content": text})
    return out


def _openai_assistant_text(body):
    choices = body.get("choices") or []
    if not choices:
        return None
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                text = str(item.get("text") or item.get("content") or "").strip()
                if text:
                    parts.append(text)
        return " ".join(parts).strip() or None
    return None


def _post_hermes_chat(messages, timeout, allow_tools=False):
    """One local Hermes /v1/chat/completions call. Raises on transport errors."""
    key = hermes_api_key()
    if not key:
        raise RuntimeError("Hermes API_SERVER_KEY is missing")
    payload = {
        "model": HERMES_MODEL,
        "messages": _hermes_messages(messages),
        "stream": False,
    }
    if not allow_tools:
        payload["tool_choice"] = "none"
    request = urllib.request.Request(
        f"{HERMES_HOST}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:240].decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} {detail}") from exc
    return _openai_assistant_text(body)


def _vision_unusable(reply):
    """Hermes sometimes answers 200 with a 404 / cannot-load image instead of a description."""
    if not reply:
        return True
    text = reply.lower()
    if "404" in text:
        return True
    clues = (
        "failed to load",
        "couldn't find that",
        "could not be analyzed",
        "couldn't be analyzed",
        "nothing came through",
        "failed to load image",
        "image file at that path",
        "couldn't see the image",
        "can't see the image",
        "cannot see the image",
    )
    return any(clue in text for clue in clues)


def _try_hermes_chat(messages, timeout, label, allow_tools=False, reject_blind=False):
    """Hermes first. None when down, empty, or failed — caller then tries Ollama."""
    if not hermes_is_up():
        print(f"{label}: Hermes is down at {HERMES_HOST}/health. Trying Ollama.")
        return None
    try:
        reply = _post_hermes_chat(messages, timeout, allow_tools=allow_tools)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, RuntimeError) as exc:
        print(f"{label}: Hermes failed ({exc}). Trying Ollama.")
        return None
    if reject_blind and _vision_unusable(reply):
        print(f"{label}: Hermes did not describe the picture. Trying Ollama.")
        return None
    if reply:
        print(f"{label} → Hermes {HERMES_MODEL} at {HERMES_HOST}.")
        return reply
    print(f"{label}: Hermes returned empty. Trying Ollama.")
    return None


def _post_ollama_chat(model, messages, predict, temperature, timeout):
    """One local Ollama /api/chat call. Raises on transport errors. think=False so content is not empty."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"num_predict": predict, "temperature": temperature},
    }
    request = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:240].decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} {detail}") from exc
    message = body.get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    return None


def _ollama_chat_with_fallback(messages, predict, temperature, timeout, label, first_timeout=None):
    """Walk gemma4:12b → llama3.2:latest → qwen2.5-coder:14b → llama3.1:8b → deepseek-r1:14b."""
    if not ollama_is_up():
        print(f"{label}: Ollama is down at http://127.0.0.1:11434. Skipped.")
        return None
    chain = ollama_fallback_chain()
    if not chain:
        print(f"{label}: Ollama lists none of the fallback models. Skipped.")
        return None
    last_exc = None
    for index, model in enumerate(chain):
        if index == 0:
            wait = first_timeout if first_timeout is not None else timeout
        else:
            wait = min(timeout, 20)
        try:
            reply = _post_ollama_chat(model, messages, predict, temperature, wait)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, RuntimeError) as exc:
            print(f"{label}: {model} failed ({exc}). Next in chain.")
            last_exc = exc
            continue
        if reply:
            print(f"{label} → Ollama {model}.")
            return reply
        print(f"{label}: {model} returned empty. Next in chain.")
    if last_exc:
        print(f"{label}: all Ollama models failed. Last error: {last_exc}")
    else:
        print(f"{label}: all Ollama models returned empty.")
    return None


def ask_language_model(user_text):
    """One short reply: local Hermes, then Ollama. Never OpenAI cloud."""
    system = (
        f"{identity_rule()} "
        f"{finger_context()} "
        f"{reply_rule()}"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]
    reply = _try_hermes_chat(messages, 30, "Open question")
    if reply:
        return reply
    return _ollama_chat_with_fallback(
        messages,
        predict=80,
        temperature=0.4,
        timeout=25,
        label="Open question",
    )

def wants_look(command):
    """Full look/describe phrases only. A stray 'see' must not switch this path."""
    text = command.replace("-", " ").lower().strip()
    if not text:
        return False
    if text in {"what do you see", "look at this", "describe this", "lihat", "look"}:
        return True
    if text.startswith("what do you see") or text.startswith("look at this") or text.startswith("describe this"):
        return True
    words = text.split()
    return "lihat" in words and len(words) <= 3

def wants_language(command):
    return switch_target(command)

def remember_frame(display, page):
    """Keep an upright JPEG for look commands and the same upright frame for reading."""
    global latest_jpeg, latest_frame
    height, width = display.shape[:2]
    scale = 640 / width if width else 1
    view = cv2.resize(display, (640, max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", view, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        return
    with frame_lock:
        latest_jpeg = encoded.tobytes()
        latest_frame = page.copy()

def wants_read(command):
    words = command.split()
    if "read" in words or "baca" in words:
        return True
    if "say" in words and any(word in words for word in ("text", "page", "book")):
        return True
    return "text" in words and any(word in words for word in ("book", "page"))

def prepare_page(frame):
    """Lift contrast and enlarge small print so a page is easier to read."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    height, width = gray.shape[:2]
    if width < 1400:
        gray = cv2.resize(gray, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
    sharp = cv2.GaussianBlur(gray, (0, 0), 1.0)
    gray = cv2.addWeighted(gray, 1.5, sharp, -0.5, 0)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

def page_reader():
    global _page_reader
    if _page_reader is None:
        from rapidocr_onnxruntime import RapidOCR
        _page_reader = RapidOCR()
    return _page_reader

def page_bands(frame):
    """Cut a tall page into overlapping bands so the bottom lines are still read."""
    height = frame.shape[0]
    band_height = 900
    overlap = 140
    if height <= band_height:
        return [frame]
    bands = []
    top = 0
    while top < height:
        bands.append(frame[top:min(height, top + band_height)])
        if top + band_height >= height:
            break
        top += band_height - overlap
    return bands

def read_page():
    """Read printed text on the latest camera frame. None when the frame is missing."""
    with frame_lock:
        frame = None if latest_frame is None else latest_frame.copy()
    if frame is None:
        return None
    lines = []
    try:
        for band in page_bands(frame):
            result, _elapsed = page_reader()(prepare_page(band))
            if not result:
                continue
            ordered = sorted(
                result,
                key=lambda item: (min(point[1] for point in item[0]), min(point[0] for point in item[0])),
            )
            for _box, text, score in ordered:
                cleaned = text.strip()
                try:
                    confidence = float(score)
                except (TypeError, ValueError):
                    continue
                if confidence < 0.45 or not cleaned:
                    continue
                if lines and lines[-1] == cleaned:
                    continue
                lines.append(cleaned)
    except Exception as exc:
        print(f"Page reader unavailable: {exc}")
        return None
    return re.sub(r"\s+", " ", " ".join(lines)).strip()

def ask_vision(user_text, jpeg=None):
    """Describe the latest camera frame via Hermes, then Ollama. None when both fail.

    Hermes JPEG first. Then gemma4:12b → llama3.2:latest → qwen2.5-coder:14b → llama3.1:8b → deepseek-r1:14b.
    Ollama JPEG only for a vision model (gemma4:12b). Never OpenAI cloud. No web overlay.
    """
    if jpeg is None:
        with frame_lock:
            jpeg = latest_jpeg
    if not jpeg:
        print("Look/describe: no camera frame yet.")
        return None
    encoded = base64.b64encode(jpeg).decode("ascii")
    hermes_messages = [
        {
            "role": "system",
            "content": (
                f"{identity_rule()} "
                "Describe only what is visible in the camera image. "
                f"{finger_context()} "
                f"{reply_rule()} Do not invent objects."
            ),
        },
        {"role": "user", "content": user_text, "images": [encoded]},
    ]
    reply = _try_hermes_chat(
        hermes_messages,
        90,
        "Look/describe",
        allow_tools=True,
        reject_blind=True,
    )
    if reply:
        return reply
    if not ollama_is_up():
        print("Look/describe: Ollama is down at http://127.0.0.1:11434. Skipped.")
        return None
    refresh_ollama_models()
    chain = ollama_fallback_chain()
    if not chain:
        print("Look/describe: Ollama lists no usable model. Skipped.")
        return None
    caps_by_name = {name: caps for name, caps in list_ollama_models()}
    last_exc = None
    for index, model in enumerate(chain):
        wait = 90 if index == 0 else 25
        if _model_has_vision(model, caps_by_name):
            user_message = {
                "role": "user",
                "content": user_text,
                "images": [encoded],
            }
            system = (
                f"{identity_rule()} "
                "Describe only what is visible in the camera image. "
                f"{finger_context()} "
                f"{reply_rule()} Do not invent objects."
            )
            kind = "vision JPEG, no web overlay"
        else:
            user_message = {"role": "user", "content": user_text}
            system = (
                f"{identity_rule()} "
                "There is no vision model on this computer. The user asked you to look at "
                "the camera. Say in one short sentence that you cannot see the picture. "
                f"{reply_rule()}"
            )
            kind = "no vision capability; text only"
        messages = [{"role": "system", "content": system}, user_message]
        try:
            reply = _post_ollama_chat(model, messages, 120, 0.2, wait)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, RuntimeError) as exc:
            print(f"Look/describe: {model} failed ({exc}). Next in chain.")
            last_exc = exc
            continue
        if reply:
            print(f"Look/describe → Ollama {model} ({kind}).")
            return reply
        print(f"Look/describe: {model} returned empty. Next in chain.")
    if last_exc:
        print(f"Look/describe failed softly: {last_exc}")
    else:
        print("Look/describe: Ollama returned nothing. Staying silent.")
    return None


def start_look_background(user_text):
    """Call Hermes then Ollama after look/describe without blocking the listener or the web overlay."""
    global vision_busy, vision_label
    if vision_busy:
        print("Look/describe already running in the background.")
        return
    vision_label = "Looking"
    print("Opening the camera for look.")
    if not wait_for_camera_frame():
        vision_busy = False
        print("Look/describe: camera did not open.")
        speak(line("no_picture"))
        return
    with frame_lock:
        jpeg = latest_jpeg
    if not jpeg:
        vision_busy = False
        print("Look/describe: no camera frame yet.")
        speak(line("no_picture"))
        return
    if not hermes_is_up() and not ollama_is_up():
        vision_busy = False
        print("Look/describe: Hermes and Ollama are both down. Skipped.")
        return
    if ollama_is_up():
        refresh_ollama_models()
    vision_busy = True
    vision_label = "Looking"
    print("Looking at the camera (Hermes, then Ollama if needed)...")

    def worker():
        global vision_busy
        try:
            reply = ask_vision(user_text, jpeg=jpeg)
            if reply:
                print(f"Look/describe: {reply}")
                if not heard_herself(reply):
                    speak(reply)
                else:
                    print("Look/describe: skipped echo of recent speech.")
            else:
                print("Look/describe: Hermes and Ollama returned nothing. Staying silent.")
        except Exception as exc:
            print(f"Look/describe failed softly: {exc}")
        finally:
            vision_busy = False

    threading.Thread(target=worker, daemon=True, name="look").start()

def wants_counting(command):
    text = command.replace("-", " ").lower().strip()
    words = set(text.split())
    if words & {"stop", "berhenti", "ignore", "abaikan"}:
        return False
    if text in {
        "start", "count", "counting", "start count", "start counting",
        "mulai", "hitung", "menghitung", "mulai hitung", "mulai menghitung",
    }:
        return True
    if "hitung" in words or "menghitung" in words:
        if words & {"ini", "itu", "soal", "this", "problem"}:
            return False
        return True
    if "count" in words or "counting" in words:
        return True
    if "jari" in words and ("mulai" in words or "hitung" in words):
        return True
    return ("count" in words and "start" in words) or ("hitung" in words and "mulai" in words)

def wants_fruit(command):
    words = command.split()
    return "fruit" in words or "buah" in words

def wants_deagle(command):
    """Voice gate: desert eagle / deagle / elang gurun only."""
    text = command.replace("-", " ").lower()
    words = set(text.split())
    if "deagle" in words or "desert eagle" in text:
        return True
    if "elang" in words and "gurun" in words:
        return True
    return "pistol" in words and "deagle" in text

def wants_dragon(command):
    text = command.replace("-", " ").lower()
    words = set(text.split())
    return "dragon" in words or "naga" in words


def wants_airbus(command):
    """Whole short command only. Noise must not become air + bus."""
    text = re.sub(r"[-.]+", " ", command.lower())
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    if not words or len(words) > 4:
        return False
    if "airbus" in words:
        return True
    return any(words[i] == "air" and words[i + 1] == "bus" for i in range(len(words) - 1))


def wants_airbus_off(command):
    if not wants_airbus(command):
        return False
    words = command.split()
    return "stop" in words or "berhenti" in words or "mati" in words or "off" in words

def wants_canvas(command):
    """The whole transcript is canvas, draw, or drawing. Nothing else opens it."""
    return bool(_canvas_exact(command))

def wants_canvas_off(command):
    if not wants_canvas(command):
        return False
    words = command.split()
    return "stop" in words or "berhenti" in words or "mati" in words or "off" in words


def wants_filter(command):
    """Voice gate: filter / filters / filter kamera / camera filter. Short whole phrase."""
    text = command.replace("-", " ").lower().strip()
    words = text.split()
    if not words or len(words) > 4:
        return False
    return "filter" in words or "filters" in words


_CANVAS_EXACT = {"canvas", "draw", "drawing"}

_ANIME_EXACT = {
    "anime",
    "stipple",
    "stipple anime",
    "stipple art",
    "art",
    "stippled",
    "stippled anime",
    "anime stipple",
    "anime mode",
    "anime kamera",
    "anime camera",
    "kamera anime",
    "camera anime",
    "stop anime",
    "stop stipple",
    "stop stipple art",
    "stop art",
    "berhenti anime",
}
_ANIME_ALIAS = {
    "a me": "anime",
    "enemy": "anime",
    "stippled": "stipple",
    "stippled anime": "stippled anime",
}


def _canvas_exact(command):
    """Normalized canvas / draw / drawing, or empty."""
    if not command:
        return ""
    text = " ".join(command.replace("-", " ").lower().split())
    return text if text in _CANVAS_EXACT else ""


def _anime_exact(command):
    """Normalized anime phrase, or empty. Other words do not match.

    The small model hears "anime" as "a me" or "enemy", and "stippled anime"
    is its own phrase. "stipple art" and a transcript that is only "art"
    start the same mode. "art" inside a longer phrase does not.
    """
    if not command:
        return ""
    text = " ".join(
        token for token in command.replace("-", " ").lower().split() if token != "[unk]"
    )
    text = _ANIME_ALIAS.get(text, text)
    return text if text in _ANIME_EXACT else ""


def _anime_starts(canon):
    """True when the phrase opens the board. Stop phrases only close it."""
    if not canon:
        return False
    if canon.startswith("stop ") or canon.startswith("berhenti "):
        return False
    if "camera" in canon or "kamera" in canon:
        return False
    return True


def _stipple_arm_phrase(command):
    """The whole transcript is start, capture, start capture, or take screenshot."""
    if not command:
        return False
    text = " ".join(command.replace("-", " ").lower().split())
    return text in _STIPPLE_ARM


def wants_anime(command):
    """Exact anime phrase only. A longer sentence does not start the mode."""
    return bool(_anime_exact(command))


def wants_anime_camera(command):
    """Optional webcam still. Default anime is a screen grab."""
    if not wants_anime(command):
        return False
    words = set(command.replace("-", " ").lower().split())
    return bool(words & {"kamera", "camera", "webcam"})


def wants_anime_off(command):
    if not wants_anime(command):
        return False
    words = command.split()
    return "stop" in words or "berhenti" in words or "mati" in words or "off" in words


def wants_youtube_play(command):
    from web import youtube_play
    return youtube_play.wants(command)


def wants_wechat_action(command):
    from web import wechat_actions
    return wechat_actions.parse(command) is not None


def _is_fog_mirror(command):
    """Exact phrase only. Not cermin kabut, not a color, not open YouTube."""
    if not command:
        return False
    return " ".join(command.replace("-", " ").lower().split()) == "fog mirror"


def wants_fog(command):
    return _is_fog_mirror(command)


def wants_fog_off(command):
    return False


def wants_pointer(command):
    from web import pointer_hands
    return pointer_hands.wants_on(command) or pointer_hands.wants_off(command)


def wants_filter_off(command):
    if not wants_filter(command):
        return False
    words = command.split()
    return "stop" in words or "berhenti" in words or "mati" in words or "off" in words


_open_apps_mod = None


def _load_open_apps():
    global _open_apps_mod
    if _open_apps_mod is not None:
        return _open_apps_mod
    import importlib.util

    path = Path(__file__).resolve().parent / "web" / "open_apps.py"
    spec = importlib.util.spec_from_file_location("asmamir_open_apps", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("web/open_apps.py missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _open_apps_mod = module
    return module


def wants_open_app(command):
    """Voice gate: open youtube / excel / browser / wechat / whatsapp. Open only."""
    return _load_open_apps().wants(command)


def launch_named_app(command):
    """Start the desktop app or URL. Does not type or send. Does not change overlay mode."""
    return _load_open_apps().launch_from_command(command)

def _standby_only(command):
    """True when the utterance is only standby, or stand by, repeated. Nothing else."""
    words = _whole_phrase(command).split()
    if not words:
        return False
    if all(word == "standby" for word in words):
        return True
    return len(words) % 2 == 0 and all(
        words[index] == "stand" and words[index + 1] == "by"
        for index in range(0, len(words), 2)
    )


def wants_standby(command):
    """Whole transcript only. A longer sentence does not leave the current mode."""
    return _standby_only(command)


def wants_dance(command):
    """Exact word dance. Cycles the Arissa clips. Does not open the camera window."""
    if not command:
        return False
    return " ".join(command.replace("-", " ").lower().split()) == "dance"


def wants_named_dance(command):
    """Exact twerk, rumba, or salsa. A longer sentence is not that dance."""
    whole = _whole_phrase(command)
    if whole in _DANCE_EXACT:
        return whole
    return ""


def wants_wake_name(command):
    """The spoken name that shows the 3D standby. Not a longer sentence."""
    if not command:
        return False
    skip = {"hey", "hi", "ok", "okay", "please", "the"}
    words = [word for word in command.replace("-", " ").lower().split() if word not in skip]
    if not words or len(words) > 4:
        return False
    blob = " ".join(words)
    tight = "".join(words)
    if "asmamir" in tight or "asmamir" in blob:
        return True
    return blob in {"as mamir", "as ma mir", "asma mir", "as my mirror", "ask mamir"}

def wants_clear_draw(command):
    text = command.replace("-", " ").lower()
    words = set(text.split())
    return "clear" in words or "hapus" in words

def wants_pen_color(command):
    if _is_fog_mirror(command):
        return False
    text = command.replace("-", " ").lower()
    words = set(text.split())
    return bool(words & {"red", "blue", "green", "yellow", "cyan", "merah", "biru", "hijau", "kuning"})

def wants_dragon_off(command):
    if not wants_dragon(command):
        return False
    words = command.split()
    return "stop" in words or "berhenti" in words or "mati" in words or "off" in words

def wants_deagle_off(command):
    if not wants_deagle(command):
        return False
    words = command.split()
    return "stop" in words or "berhenti" in words or "mati" in words or "off" in words

def wants_shutdown(command):
    """Quit only when the whole transcript is a shutdown phrase."""
    return _whole_phrase(command) in _QUIT_EXACT

_shutting_down = False


def request_shutdown(voice=False):
    """Voice thread only raises the flag. The camera thread closes the window."""
    global shutdown_requested
    shutdown_requested = True
    cut_speech()
    print("Shutdown by voice" if voice else "Shutdown", flush=True)
    if threading.current_thread() is threading.main_thread():
        finish_shutdown()


def finish_shutdown():
    """Release the camera, stop audio, close overlay sockets, then exit.

    OpenCV on Windows hangs if destroyAllWindows runs off this thread while
    waitKey is in progress. Do not join threads and do not call Server.shutdown.
    """
    global _shutting_down
    if threading.current_thread() is not threading.main_thread():
        return
    if _shutting_down:
        return
    _shutting_down = True
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass
    capture = globals().get("cap")
    if capture is not None:
        try:
            capture.release()
        except Exception:
            pass
    for name in ("_deagle_mod", "_airbus_mod"):
        module = globals().get(name)
        stop = getattr(module, "stop_servers", None) if module is not None else None
        if stop is None:
            continue
        try:
            stop()
        except Exception as exc:
            print(f"Shutdown servers: {exc}")
    for closer, label in (
        (_close_p5_board, "anime"),
        (_close_dance_window, "dance"),
        (_close_fog_window, "fog"),
        (_close_select, "select"),
    ):
        try:
            closer()
        except Exception as exc:
            print(f"Shutdown {label}: {exc}")
    titles = (
        globals().get("WINDOW"),
        globals().get("DANCE_WINDOW"),
        globals().get("FOG_WINDOW"),
        globals().get("SELECT_WINDOW"),
        globals().get("ANIME_CAM"),
        "Anime stipple",
    )
    try:
        import ctypes
        user32 = ctypes.windll.user32
        for title in titles:
            if not title:
                continue
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                user32.PostMessageW(hwnd, 0x0010, 0, 0)
    except Exception:
        pass
    try:
        cv2.destroyAllWindows()
        cv2.waitKey(1)
    except Exception:
        pass
    _stop_chat_companions()
    # sys.exit runs GC, and ufbx's destructor access-violates after skinning.
    os._exit(0)

def _stop_chat_companions():
    """Ollama, Hermes, and the Deepseek harness run only while this app does."""
    if getattr(_stop_chat_companions, "done", False):
        return
    _stop_chat_companions.done = True
    print("Stopping Ollama, Hermes, and the Deepseek harness.", flush=True)
    subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            "$ids = @(); "
            "foreach ($port in 11434,8642,3080) { "
            "Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | "
            "ForEach-Object { $ids += $_.OwningProcess } }; "
            "Get-CimInstance Win32_Process | Where-Object { "
            "$c = [string]$_.CommandLine; "
            "($_.Name -eq 'ollama.exe' -and ($c -match 'serve' -or $c -match 'launch\\s+dsh')) -or "
            "($c -match 'Hermes_Gateway' -or ($c -match 'hermes' -and $c -match 'gateway')) "
            "} | ForEach-Object { $ids += $_.ProcessId }; "
            "$ids | Select-Object -Unique | Where-Object { $_ -gt 0 } | "
            "ForEach-Object { taskkill /F /T /PID $_ | Out-Null }",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=20,
    )


def wants_quiet(command):
    """Cut the current speech and return to listening. Does not stop finger counting."""
    words = command.split()
    if command in {"quiet", "diam", "cukup", "enough", "hush", "silence"}:
        return True
    return words[:2] in (["stop", "talking"], ["berhenti", "bicara"])

def wants_stop(command):
    words = command.split()
    if "ignore" in words and any(word.startswith("finger") for word in words):
        return True
    if "abaikan" in words and any(word.startswith("jari") for word in words):
        return True
    if not words or words[0] not in {"stop", "berhenti"}:
        return False
    return len(words) == 1 or words[1] in {
        "count", "counting", "finger", "fingers", "hitung", "menghitung", "jari",
        "deagle", "dragon", "naga", "draw", "gambar", "canvas", "kanvas",
        "airbus", "filter", "filters", "anime", "fog", "mirror", "standby",
        "drawing", "dance",
    }

def clear_finger_count():
    """Drop the last total so the screen and the model stop talking about fingers."""
    global last_total_count, stable_total, stable_hits
    last_total_count = -1
    stable_total = -1
    stable_hits = 0


_show_camera = False


def _pointer_module():
    return globals().get("_pointer_mod")


def _vision_modes_on():
    return bool(
        vision_busy
        or system_active
        or fruit_active
        or deagle_active
        or dragon_active
        or canvas_active
        or airbus_active
        or filter_active
        or anime_active
        or fog_active
    )


def vision_camera_needed():
    """True while a vision mode is on, or the hand cursor needs the webcam."""
    return _vision_modes_on() or bool(_load_pointer().needs_camera())


def _drop_latest_frame():
    global latest_jpeg, latest_frame
    with frame_lock:
        latest_jpeg = b""
        latest_frame = None


def request_hologram():
    """Leave vision modes. The window thread shows the hologram. It stays hidden until this."""
    global vision_busy, _standby_visible
    set_session_mode(None)
    clear_finger_count()
    vision_busy = False
    _standby_visible = True
    _drop_latest_frame()
    from web import hologram_dance
    hologram_dance.begin_situp()
    print("Hologram.")


def request_dance(name=""):
    """Close every other mode window. The window thread opens the dance window."""
    global vision_busy, _standby_visible
    set_session_mode(None)
    clear_finger_count()
    vision_busy = False
    _standby_visible = True
    _drop_latest_frame()
    from web import hologram_dance
    if name:
        hologram_dance.play(name)
    else:
        hologram_dance.cycle()
    print("Dance window.")


def wait_for_camera_frame(timeout=18):
    """Open the webcam on the window thread and wait for one upright frame."""
    global vision_busy
    vision_busy = True
    deadline = time.time() + timeout
    while time.time() < deadline:
        with frame_lock:
            if latest_frame is not None and latest_jpeg:
                return True
        if shutdown_requested:
            return False
        time.sleep(0.05)
    return False


def _close_kind(command):
    from web import close_tabs
    return close_tabs.kind_from(command or "")


def request_camera_screen():
    """Ask the window thread to close the stipple page and sit up. Voice must not touch OpenCV."""
    global anime_pending, _recording_snap, _snap_save, _need_ui_standby
    anime_pending = None
    _recording_snap = False
    _need_ui_standby = True
    request_hologram()


def _return_camera_voice(guesses, interrupt=False):
    """Stop, standby, or a close-tab phrase. The view changes before she speaks."""
    if any(wants_stop(guess) or wants_standby(guess) for guess in guesses):
        if interrupt:
            cut_speech()
        request_camera_screen()
        speak("ok, back to standby mode")
        return True
    close_guess = next((guess for guess in guesses if _close_kind(guess)), "")
    if not close_guess:
        return False
    if interrupt:
        cut_speech()
    kind = _close_kind(close_guess)
    shown = {"youtube": "YouTube", "airbus": "Airbus", "desert eagle": "Desert Eagle"}.get(kind, kind)
    from web import close_tabs
    ok = close_tabs.close_kind(kind)
    request_camera_screen()
    speak(line("tab_closed" if ok else "tab_missing", name=shown))
    return True

_recording_snap = False
_motion_frames = []
_snap_reason = "camera snap"


def _snap_folder():
    folder = Path(__file__).resolve().parent / "models" / "snaps"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _snap_sample_path():
    """First missing wav. When snap-1 through snap-5 already exist, replace from snap-1."""
    folder = _snap_folder()
    for number in range(1, 6):
        wav = folder / f"snap-{number}.wav"
        if not wav.is_file() or wav.stat().st_size == 0:
            return wav, False
    marker = folder / "next.txt"
    number = 1
    if marker.is_file():
        try:
            number = int(marker.read_text(encoding="utf-8").strip() or "1")
        except ValueError:
            number = 1
    number = min(5, max(1, number))
    return folder / f"snap-{number}.wav", True


def _advance_replaced_slot(number):
    nxt = 1 if number >= 5 else number + 1
    (_snap_folder() / "next.txt").write_text(str(nxt), encoding="utf-8")


def _keep_record_frame(frame):
    if frame is None or getattr(frame, "size", 0) == 0:
        return
    _motion_frames.append(frame.copy())
    if len(_motion_frames) > 14:
        del _motion_frames[:-14]


_snap_save = None
_snap_close = False


def _capture_record_frame():
    """One camera frame and a window pump. No file write and no hand model on this path."""
    global cap, cam_index, cam_backend, cam_backend_name, last_good, miss_frames
    if _p5_armed:
        return
    if cap is None or not cap.isOpened():
        opened = _open_best_camera()
        if opened is None:
            return
        cap, cam_index, cam_backend, cam_backend_name = opened
        last_good = None
        miss_frames = 0
    ok, frame = cap.read()
    if not ok or frame is None or getattr(frame, "size", 0) == 0:
        cv2.waitKey(1)
        return
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    frame = cv2.flip(frame, 1)
    _show_anime_camera(frame)
    _keep_record_frame(frame)


def _finish_snap_save():
    """Close the writer, log the slot, and drop the Anime camera."""
    global _snap_save
    job = _snap_save
    _snap_save = None
    writer = job.get("writer")
    if writer is not None:
        writer.release()
    video = job["video"]
    if job.get("wrote"):
        print(f"Saved {video}.", flush=True)
    elif not job.get("frames"):
        print(f"No camera frames for {video}.", flush=True)
    number = job["number"]
    if number < 5:
        print(f"Say record snap, then snap once, for snap-{number + 1}.mp4.", flush=True)
    else:
        print("Say record snap, then snap once, to replace snap-1.", flush=True)
    if not (_p5_open and not _p5_armed):
        _hide_anime_camera()


def _pump_snap_save():
    """Write the wav once, then one video frame, and keep the window answering."""
    global _snap_save
    import wave

    job = _snap_save
    if job is None:
        return
    frames = job["frames"]
    shown = frames[-1] if frames else None
    if shown is not None:
        _show_anime_camera(shown)
    if not job["wav_done"]:
        path = job["path"]
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(job["width"])
            handle.setframerate(job["rate"])
            handle.writeframes(job["raw"])
        job["wav_done"] = True
        if job["replacing"]:
            print(f"Replaced snap-{job['number']}.", flush=True)
            _advance_replaced_slot(job["number"])
        print(f"Saved {path}. Peak {job['peak']} ({job['peak'] / 32767:.2f}).", flush=True)
        return
    if not frames:
        _finish_snap_save()
        return
    writer = job.get("writer")
    if writer is None:
        height, width = frames[0].shape[:2]
        job["size"] = (width, height)
        writer = cv2.VideoWriter(str(job["video"]), cv2.VideoWriter_fourcc(*"mp4v"), 10, (width, height))
        job["writer"] = writer
        if not writer.isOpened():
            for index, frame in enumerate(frames, start=1):
                cv2.imwrite(str(job["path"].with_name(f"{job['path'].stem}-{index:02d}.jpg")), frame)
            job["wrote"] = False
            print(f"Saved frames next to {job['path'].name}.", flush=True)
            _finish_snap_save()
            return
    index = job["index"]
    if index >= len(frames):
        job["wrote"] = True
        _finish_snap_save()
        return
    frame = frames[index]
    width, height = job["size"]
    if frame.shape[1] != width or frame.shape[0] != height:
        frame = cv2.resize(frame, (width, height))
    writer.write(frame)
    job["index"] = index + 1


def _record_next_snap(source):
    """Wait for the snap on the mic. The window thread writes the wav and the mp4."""
    global _recording_snap, _motion_frames, _snap_save, _snap_close

    path, replacing = _snap_sample_path()
    video = path.with_suffix(".mp4")
    rate = int(source.SAMPLE_RATE)
    width = int(source.SAMPLE_WIDTH)
    chunk = int(source.CHUNK)
    seconds = 0.7
    need = int(rate * seconds) * width
    pre_keep = int(rate * 0.15) * width
    _motion_frames = []
    _recording_snap = True
    print(f"Snap once. Wav {path}. Video {video}.", flush=True)
    try:
        def read_block():
            return source.stream.read(chunk)

        ambient = 0
        heard = []
        started = time.time()
        while time.time() - started < 0.25:
            block = read_block()
            samples = np.frombuffer(block, dtype=np.int16)
            if samples.size:
                ambient = max(ambient, int(np.max(np.abs(samples))))
            heard.append(block)
        threshold = max(6000, ambient * 6)
        pre = [b"".join(heard)[-pre_keep:]]
        previous = ambient
        triggered = False
        pieces = []
        total = 0
        deadline = time.time() + 6.0
        while total < need:
            if not triggered and time.time() >= deadline:
                break
            block = read_block()
            samples = np.frombuffer(block, dtype=np.int16)
            level = int(np.max(np.abs(samples))) if samples.size else 0
            if not triggered:
                pre.append(block)
                raw_pre = b"".join(pre)
                if len(raw_pre) > pre_keep:
                    pre = [raw_pre[-pre_keep:]]
                if level >= threshold and level > previous * 2:
                    triggered = True
                    pieces = [b"".join(pre)]
                    total = len(pieces[0])
                previous = level
                continue
            pieces.append(block)
            total += len(block)
        if not triggered:
            print("No snap arrived. Say record snap and snap again.", flush=True)
            return
        raw = b"".join(pieces)[:need]
        audio = np.frombuffer(raw, dtype=np.int16)
        peak = int(np.max(np.abs(audio))) if audio.size else 0
        _snap_save = {
            "path": path,
            "video": video,
            "raw": raw,
            "rate": rate,
            "width": width,
            "peak": peak,
            "replacing": replacing,
            "number": int(path.stem.split("-")[1]),
            "frames": list(_motion_frames),
            "index": 0,
            "wav_done": False,
            "writer": None,
            "wrote": False,
        }
    finally:
        _recording_snap = False
        if _snap_save is None:
            _snap_close = True


def _on_standby():
    """Sit-up hologram only. Anime, dance, fog, canvas, and the other modes are not this."""
    if not _standby_visible or _vision_modes_on() or _p5_open:
        return False
    try:
        from web import hologram_dance
        if hologram_dance.active():
            return False
    except Exception:
        return False
    return True


def _take_voice_quit(guesses):
    """Quit only from standby. Anywhere else, the same phrase returns to the sit-up."""
    if not any(wants_shutdown(guess) for guess in guesses):
        return False
    if _on_standby():
        request_shutdown(voice=True)
        return True
    print("Shutdown phrase returns to standby.", flush=True)
    request_camera_screen()
    speak("ok, back to standby mode")
    return True


def _take_restart_anime(guesses):
    """Whole transcript only. Close the held picture and open selection again."""
    global _restart_anime
    if not any(_whole_phrase(guess) == "restart anime" for guess in guesses):
        return False
    _restart_anime = True
    print("Restart anime.", flush=True)
    return True


def _take_leave_to_standby(guesses):
    """Standby, repeated, or stop anime / stop stipple art. The app keeps running."""
    leave = {"stop anime", "stop stipple art"}
    if not any(_standby_only(guess) or _whole_phrase(guess) in leave for guess in guesses):
        return False
    print("Standby phrase closes anime.", flush=True)
    request_camera_screen()
    speak("ok, back to standby mode")
    return True


def _take_record_snap(guesses, source):
    if not any(_whole_phrase(guess) in _RECORD_EXACT for guess in guesses):
        return False
    print("Record snap armed", flush=True)
    try:
        _record_next_snap(source)
    except Exception as exc:
        print(f"Snap recording failed: {exc}", flush=True)
    return True


def listen_for_command():
    """Listen continuously for English commands and profile questions."""
    global shutdown_requested, vision_busy, vision_label, speech_language, anime_pending
    recognizer.dynamic_energy_threshold = True
    recognizer.dynamic_energy_ratio = 1.3
    recognizer.pause_threshold = 1.05
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.8)
        # USBAudio1.0 is often quieter than a laptop array. Cap low = more sensitive.
        recognizer.energy_threshold = min(max(recognizer.energy_threshold, 80), 220)
        print(
            f"[Voice ready] Vosk on {microphone_label}. "
            f"threshold {recognizer.energy_threshold:.0f}. Say 'start counting'."
        )

        while True:
            try:
                while speaking or not speech_queue.empty() or time.time() < quiet_after:
                    if not speaking:
                        time.sleep(0.05)
                        continue
                    try:
                        heard = recognizer.listen(source, timeout=0.5, phrase_time_limit=1.4)
                    except sr.WaitTimeoutError:
                        continue
                    guesses = transcripts_from(heard)
                    if _take_voice_quit(guesses):
                        continue
                    if _take_record_snap(guesses, source):
                        continue
                    if _take_restart_anime(guesses):
                        continue
                    if _take_leave_to_standby(guesses):
                        continue
                    if _return_camera_voice(guesses, interrupt=True):
                        print("Heard: " + " | ".join(guesses))
                        continue
                    if any(wants_quiet(guess) for guess in guesses):
                        print("Heard: " + " | ".join(guesses))
                        cut_speech()
                print("Listening for you...")
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=6)
                if speaking or time.time() < quiet_after:
                    print("Ignored speaker playback.")
                    continue
                guesses = transcripts_from(audio)
                if _take_voice_quit(guesses):
                    continue
                if _take_record_snap(guesses, source):
                    continue
                if _take_restart_anime(guesses):
                    continue
                if _take_leave_to_standby(guesses):
                    continue
                if _p5_open and not _p5_armed and any(_stipple_arm_phrase(guess) for guess in guesses):
                    print("Heard: " + " | ".join(guesses))
                    _arm_stipple("voice")
                    continue
                if _p5_open and not _p5_armed and _matches_saved_snap(audio):
                    _arm_stipple("sound match")
                    continue
                if not guesses:
                    print("Heard audio, but the words were not clear.")
                    continue
                if _audio_too_short(audio):
                    print("Heard a short burst, ignored.")
                    continue
                print("Heard: " + " | ".join(guesses))
                if _take_voice_quit(guesses):
                    continue
                if _take_record_snap(guesses, source):
                    continue
                if _take_restart_anime(guesses):
                    continue
                if _take_leave_to_standby(guesses):
                    continue
                if any(wants_wake_name(guess) for guess in guesses):
                    print("Voice asmamir. Standby.")
                    request_camera_screen()
                    speak(line("wake"))
                    continue
                if not _standby_visible:
                    print("Quiet. Snap thumb to middle, or say asmamir.")
                    continue
                if _return_camera_voice(guesses):
                    continue
                named_dance = next((wants_named_dance(guess) for guess in guesses if wants_named_dance(guess)), "")
                if named_dance:
                    request_dance(named_dance)
                    continue
                if any(wants_dance(guess) for guess in guesses):
                    request_dance()
                    continue
                screen_hit = any(
                    wants_anime(guess) and not wants_anime_off(guess) and not wants_anime_camera(guess)
                    for guess in guesses
                )
                camera_hit = any(
                    wants_anime_camera(guess) and not wants_anime_off(guess) for guess in guesses
                )
                if camera_hit and not screen_hit:
                    print("Anime kamera ignored. Screen capture only.")
                    continue
                if screen_hit:
                    set_session_mode("anime")
                    anime_pending = "screen"
                    print("Anime ON screen")
                    speak(line("anime_on"))
                    continue
                if any(wants_fog(guess) for guess in guesses):
                    set_session_mode("fog")
                    print("Fog mirror ON")
                    speak(line("fog_on"))
                    continue
                if any(wants_canvas(guess) for guess in guesses) and not any(
                    wants_canvas_off(guess) for guess in guesses
                ):
                    set_session_mode("canvas")
                    print("Canvas ON")
                    speak(line("canvas_on"))
                    continue
                if any(wants_filter(guess) for guess in guesses) and not any(
                    wants_filter_off(guess) for guess in guesses
                ):
                    set_session_mode("filter")
                    filter_reset_gestures()
                    print("Filter ON")
                    speak(line("filter_on"))
                    continue
                if any(_load_pointer().wants_off(guess) for guess in guesses):
                    _load_pointer().suppress()
                    print("Pointer OFF")
                    speak(line("pointer_off"))
                    continue
                if any(_load_pointer().wants_on(guess) for guess in guesses):
                    _load_pointer().arm()
                    print("Pointer ON. Index moves the Windows cursor.")
                    speak(line("pointer_on"))
                    continue
                if any(wants_airbus(guess) for guess in guesses) and not any(
                    wants_airbus_off(guess) for guess in guesses
                ):
                    set_session_mode("airbus")
                    print("Airbus ON")
                    speak(line("airbus_on"))
                    continue
                if all(heard_herself(guess) for guess in guesses) or (
                    last_spoken_fruit and any(last_spoken_fruit in guess for guess in guesses)
                ):
                    print("Ignored own voice.")
                    continue
                app_guess = next((guess for guess in guesses if wants_open_app(guess)), None)
                if app_guess:
                    app, ok = launch_named_app(app_guess)
                    label = {
                        "youtube": "app_youtube",
                        "excel": "app_excel",
                        "browser": "app_browser",
                        "wechat": "app_wechat",
                        "whatsapp": "app_whatsapp",
                    }.get(app)
                    shown = {
                        "youtube": "YouTube",
                        "excel": "Excel",
                        "browser": "the browser",
                        "wechat": "WeChat",
                        "whatsapp": "WhatsApp",
                    }.get(app, app or "that app")
                    if ok and label:
                        print(f"Open {app} ON")
                        speak(line(label))
                    else:
                        print(f"Open {app or app_guess}: missing")
                        speak(line("app_missing", name=shown))
                    continue

                about = next((profile_reply(guess) for guess in guesses if profile_reply(guess)), None)
                target = next((wants_language(guess) for guess in guesses if wants_language(guess)), None)
                if target:
                    if target == speech_language:
                        speak(line("language_same"))
                    elif target == "id" and not ensure_indonesian_listener():
                        speak(line("no_indonesian_ear"))
                    else:
                        speech_language = target
                        print(f"Language {speech_language}")
                        speak(line("language_en" if target == "en" else "language_id"))
                elif about:
                    speak(about)
                elif any(wants_standby(guess) for guess in guesses):
                    request_camera_screen()
                    speak("ok, back to standby mode")
                elif any(wants_clear_draw(guess) for guess in guesses):
                    canvas_clear_ink()
                    print("Canvas cleared")
                    speak("cleared" if speech_language == "en" else "sudah dihapus")
                elif any(wants_pen_color(guess) for guess in guesses):
                    named = next((wants_pen_color(guess) and guess for guess in guesses if wants_pen_color(guess)), "cyan")
                    picked = canvas_set_color(named)
                    print(f"Pen {picked}")
                    speak(picked or "cyan")
                elif any(wants_read(guess) for guess in guesses):
                    vision_label = "Reading"
                    print("Opening the camera to read.")
                    if not wait_for_camera_frame():
                        vision_busy = False
                        speak(line("page_missing"))
                        continue
                    print("Reading the page...")
                    page_text = read_page()
                    vision_busy = False
                    if page_text is None:
                        speak(line("page_missing"))
                    elif not page_text:
                        speak(line("page_blank"))
                    else:
                        print(f"Page: {page_text}")
                        solved = solve_written(page_text)
                        if solved:
                            print(f"Solved: {solved}")
                            speak(solved)
                        else:
                            speak(page_text)
                elif any(wants_solve(guess) for guess in guesses):
                    vision_label = "Reading"
                    print("Opening the camera to read.")
                    if not wait_for_camera_frame():
                        vision_busy = False
                        speak(line("page_missing"))
                        continue
                    print("Solving the writing...")
                    page_text = read_page()
                    vision_busy = False
                    solved = solve_written(page_text or "")
                    if page_text is None:
                        speak(line("page_missing"))
                    elif solved:
                        print(f"Page: {page_text}")
                        print(f"Solved: {solved}")
                        speak(solved)
                    elif not page_text:
                        speak(line("page_blank"))
                    else:
                        speak("I could not calculate that." if speech_language == "en" else "Itu tidak bisa dihitung.")
                elif any(wants_look(guess) for guess in guesses):
                    start_look_background(
                        next(guess for guess in guesses if wants_look(guess))
                    )
                elif any(wants_fruit(guess) for guess in guesses):
                    set_session_mode("fruit")
                    print("Fruit ON")
                    speak(line("fruit_on", name=USER_NICKNAME))
                elif any(wants_counting(guess) for guess in guesses):
                    set_session_mode("count")
                    print("Counting ON")
                    speak(line("count_on", name=USER_NICKNAME))
                elif any(wants_deagle(guess) for guess in guesses) and not any(
                    wants_deagle_off(guess) for guess in guesses
                ):
                    set_session_mode("deagle")
                    print("Deagle ON")
                    speak(line("deagle_on"))
                elif any(wants_dragon(guess) for guess in guesses) and not any(
                    wants_dragon_off(guess) for guess in guesses
                ):
                    set_session_mode("dragon")
                    print("Dragon ON")
                    speak(line("dragon_on"))
                elif _take_voice_quit(guesses):
                    pass
                elif any(wants_quiet(guess) for guess in guesses):
                    cut_speech()
                elif any(wants_stop(guess) for guess in guesses) or any(
                    wants_deagle_off(guess) for guess in guesses
                ) or any(wants_dragon_off(guess) for guess in guesses) or any(
                    wants_canvas_off(guess) for guess in guesses
                ) or any(wants_airbus_off(guess) for guess in guesses) or any(
                    wants_filter_off(guess) for guess in guesses
                ) or any(wants_anime_off(guess) for guess in guesses) or any(
                    wants_standby(guess) for guess in guesses
                ):
                    request_camera_screen()
                    speak("ok, back to standby mode")
                else:
                    calculated = None
                    for guess in guesses:
                        calculated = math_reply(guess)
                        if calculated:
                            break
                    if calculated:
                        print(f"Math: {calculated}")
                        speak(calculated)
                    else:
                        asked = guesses[0]
                        def _answer_later(text=asked):
                            try:
                                reply = ask_language_model(text)
                                if reply and not heard_herself(reply):
                                    speak(reply)
                            except Exception as exc:
                                print(f"Open question failed: {exc}", flush=True)
                        threading.Thread(target=_answer_later, daemon=True).start()
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                print("Heard audio, but the words were not clear.")
            except sr.RequestError as exc:
                print(f"Speech-to-text needs internet: {exc}")
                time.sleep(1)
            except Exception as exc:
                text = str(exc)
                if "-9988" in text or "-9999" in text or "Stream closed" in text:
                    print("Microphone stream closed. Opening it again.", flush=True)
                    raise
                print(f"Voice listener error: {exc}", flush=True)
                time.sleep(0.2)

# Jalankan pendengar suara di thread terpisah agar tidak mengganggu kamera
_standby_visible = False
threading.Thread(target=listen_for_command, daemon=True).start()

# =====================================================================
# 3. INISIALISASI MEDIAPIPE (DETEKSI 2 TANGAN)
# =====================================================================
# Menambahkan '# type: ignore' untuk menghilangkan garis merah palsu dari VS Code Pylance
mp_hands = mp.solutions.hands  # type: ignore
mp_draw = mp.solutions.drawing_utils  # type: ignore

# max_num_hands=2 diaktifkan untuk mendeteksi tangan kanan & kiri bersamaan
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2, 
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

FINGER_TIPS = [4, 8, 12, 16, 20]
FRUIT_NAMES = {"apple", "banana", "orange"}
fruit_active = False
stable_fruit = ""
fruit_hits = 0
fruit_misses = 0
fruit_log_tick = 0
last_spoken_fruit = ""

def mediapipe_model(path):
    """Load model bytes. An absolute path is prefixed with site-packages on this MediaPipe build."""
    return mp.tasks.BaseOptions(model_asset_buffer=path.read_bytes())

FRUIT_MODEL = Path(__file__).resolve().parent / "models" / "efficientdet_lite0.tflite"
fruit_detector = None
if FRUIT_MODEL.exists():
    fruit_detector = mp.tasks.vision.ObjectDetector.create_from_options(
        mp.tasks.vision.ObjectDetectorOptions(
            base_options=mediapipe_model(FRUIT_MODEL),
            score_threshold=0.35,
            max_results=3,
        )
    )
    print("Fruit detector ready: apple, banana, orange.")
else:
    print(f"Fruit model missing: {FRUIT_MODEL}")

GALLERY_PATH = Path(__file__).resolve().parent / "models" / "fruit_gallery.npz"
EMBEDDER_PATH = Path(__file__).resolve().parent / "models" / "mobilenet_v3_small.tflite"
gallery_names = []
gallery_vectors = None
fruit_embedder = None
if GALLERY_PATH.exists() and EMBEDDER_PATH.exists():
    saved = np.load(GALLERY_PATH, allow_pickle=False)
    gallery_names = [str(name) for name in saved["names"]]
    gallery_vectors = saved["vectors"].astype(np.float32)
    fruit_embedder = mp.tasks.vision.ImageEmbedder.create_from_options(
        mp.tasks.vision.ImageEmbedderOptions(
            base_options=mediapipe_model(EMBEDDER_PATH),
            l2_normalize=True,
            quantize=False,
        )
    )
    print("Trained fruits: " + ", ".join(gallery_names))

# =====================================================================
# 4. WEBCAM
# Format dipaksa (1080p/60 atau MJPG) sering membuat eMeet mengirim frame
# hitam. Bandingkan indeks apa adanya, pakai yang paling terang.
# =====================================================================
last_total_count = -1
stable_total = -1
stable_hits = 0
WINDOW = PRODUCT_NAME
FOG_WINDOW = "Fog mirror"
ANIME_BOARD = "Anime board"
SELECT_WINDOW = "Anime select"
ANIME_CAM = "Anime camera"
DANCE_WINDOW = "Dance"
_anime_cam_open = False
_anime_cam_hold = False
_need_ui_standby = False
_restart_anime = False
_fog_window_open = False
_standby_parked = False
_standby_window = False
_standby_hidden = False
_dance_window_open = False
_surface = None
_anime_board_open = False
_anime_board_hidden = False
_p5_httpd = None
_p5_port = None
_p5_proc = None
_p5_open = False
_p5_armed = False
_p5_crop = None
_p5_filled = False
_mouse_was_down = False
_reselect_drag = False
_select_open = False
_select_shot = None
_select_origin = (0, 0, 0, 0)
_select_scale = (1.0, 1.0)
_select_raised = False
_drag_anchor = None
_drag_point = None
_drag_rect = None
_capture_frame = None
_pointer_mod = None
_draw_deagle = None
_deagle_mod = None
_draw_dragon = None


def draw_deagle_overlay(frame, results):
    """Load web/deagle_cv.py on first use so Standby never pays for overlay."""
    global _draw_deagle, _deagle_mod
    if _draw_deagle is None:
        import importlib.util

        path = Path(__file__).resolve().parent / "web" / "deagle_cv.py"
        spec = importlib.util.spec_from_file_location("asmamir_deagle_cv", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("web/deagle_cv.py missing")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _deagle_mod = module
        _draw_deagle = module.draw_deagle_overlay
    return _draw_deagle(frame, results)


def draw_dragon_overlay(frame, results):
    """Load web/dragon_cv.py on first use."""
    global _draw_dragon
    if _draw_dragon is None:
        import importlib.util

        path = Path(__file__).resolve().parent / "web" / "dragon_cv.py"
        spec = importlib.util.spec_from_file_location("asmamir_dragon_cv", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("web/dragon_cv.py missing")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _draw_dragon = module.draw_dragon_overlay
    return _draw_dragon(frame, results)


_draw_airbus = None
_airbus_mod = None


def draw_airbus_overlay(frame, results):
    """Load web/airbus_cv.py on first use."""
    global _draw_airbus, _airbus_mod
    if _draw_airbus is None:
        import importlib.util

        path = Path(__file__).resolve().parent / "web" / "airbus_cv.py"
        spec = importlib.util.spec_from_file_location("asmamir_airbus_cv", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("web/airbus_cv.py missing")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _airbus_mod = module
        _draw_airbus = module.draw_airbus_overlay
    return _draw_airbus(frame, results)


_draw_canvas = None
_canvas_mod = None


def _load_canvas_mod():
    global _draw_canvas, _canvas_mod
    if _canvas_mod is not None:
        return _canvas_mod
    import importlib.util

    path = Path(__file__).resolve().parent / "web" / "canvas_cv.py"
    spec = importlib.util.spec_from_file_location("asmamir_canvas_cv", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("web/canvas_cv.py missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _canvas_mod = module
    _draw_canvas = module.draw_canvas_overlay
    return module


def draw_canvas_overlay(frame, results):
    """Load web/canvas_cv.py on first use."""
    return _load_canvas_mod().draw_canvas_overlay(frame, results)


def canvas_clear_ink():
    _load_canvas_mod().clear_ink()


def canvas_set_color(command):
    words = command.replace("-", " ").lower().split()
    for word in words:
        named = _load_canvas_mod().set_color(word)
        if named:
            return named
    return _load_canvas_mod().ink_name()


_draw_filter = None
_filter_mod = None


def _load_filter_mod():
    global _draw_filter, _filter_mod
    if _filter_mod is not None:
        return _filter_mod
    import importlib.util

    path = Path(__file__).resolve().parent / "web" / "filter_cv.py"
    spec = importlib.util.spec_from_file_location("asmamir_filter_cv", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("web/filter_cv.py missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _filter_mod = module
    _draw_filter = module.draw_filter_overlay
    return module


def draw_filter_overlay(frame, results):
    """Load web/filter_cv.py on first use. Uses this process camera + Hands."""
    return _load_filter_mod().draw_filter_overlay(frame, results)


def filter_reset_gestures():
    _load_filter_mod().reset_gestures()


def _load_anime_mod():
    global _anime_mod
    if _anime_mod is not None:
        return _anime_mod
    import importlib.util

    path = Path(__file__).resolve().parent / "web" / "anime_cv.py"
    spec = importlib.util.spec_from_file_location("asmamir_anime_cv", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("web/anime_cv.py missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _anime_mod = module
    return module


def _load_fog():
    global _fog_mod
    if _fog_mod is not None:
        return _fog_mod
    import importlib.util

    path = Path(__file__).resolve().parent / "web" / "fog_cv.py"
    spec = importlib.util.spec_from_file_location("asmamir_fog_cv", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("web/fog_cv.py missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _fog_mod = module
    return module


def draw_fog_overlay(frame, results):
    """Load web/fog_cv.py on first use. Same camera and Hands."""
    return _load_fog().draw_fog_overlay(frame, results)


def _capture_box():
    global _capture_frame
    if _capture_frame is None:
        from web.anime_region import RegionFrame
        _capture_frame = RegionFrame()
    return _capture_frame


def _hide_overlay_window():
    """Move Asmamir windows off the capture box so the grab sees the desktop there."""
    try:
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, 2, 2)
        cv2.moveWindow(WINDOW, -32000, -32000)
        cv2.waitKey(1)
        _hide_anime_board()
        if _capture_frame is not None:
            _capture_frame.hide()
    except Exception as exc:
        print(f"Anime: could not hide overlay ({exc})")
    time.sleep(0.22)


def _show_overlay_window():
    try:
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.waitKey(1)
    except Exception as exc:
        print(f"Anime: could not restore overlay ({exc})")


def _front_chrome_rect():
    """Screen rectangle of the front Chrome window. None when Chrome is not open."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, ctypes.c_ssize_t)
    def visit(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        klass = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, klass, 256)
        if klass.value != "Chrome_WidgetWin_1":
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value or ""
        low = title.lower()
        if "google chrome" not in low or "asmamir" in low:
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width < 240 or height < 180:
            return True
        found.append((int(rect.left), int(rect.top), width, height, title))
        return True

    user32.EnumWindows(visit, 0)
    if not found:
        return None
    left, top, width, height, title = found[0]
    print(f"Anime Chrome: {title}")
    return left, top, width, height


def anime_begin(source="screen", rect=None):
    """Finger-box still, or the latest webcam still. Camera-thread only.

    Screen capture uses `rect` (left, top, width, height). It does not grab the monitor.
    """
    module = _load_anime_mod()
    if source == "camera":
        if _capture_frame is not None:
            _capture_frame.hide()
        with frame_lock:
            frame = None if latest_frame is None else latest_frame.copy()
        if frame is None:
            print("Anime: no camera frame yet.")
            return False
        return bool(module.begin(frame))
    if not rect or len(rect) != 4:
        return False
    left, top, width, height = (int(v) for v in rect)
    if width < 2 or height < 2:
        return False
    _hide_overlay_window()
    try:
        frame = module.grab_region(left, top, width, height)
    finally:
        _park_for_anime()
    if frame is None or getattr(frame, "size", 0) == 0:
        print("Anime: capture box grab failed.")
        return False
    print(f"Anime box {width}x{height} at {left},{top}")
    frame = module.crop_page_photo(frame)
    return bool(module.begin(frame))


def _placement():
    global _box_place
    if _box_place is None:
        from web.anime_region import Placement
        _box_place = Placement()
    return _box_place


def _screen_bounds():
    global _monitor_bounds
    if _monitor_bounds is None:
        from web import anime_region
        _monitor_bounds = anime_region.primary_bounds()
    return _monitor_bounds


def _draw_finger_box(frame, image_rect):
    x, y, width, height = image_rect
    color = (248, 189, 56)
    cv2.rectangle(frame, (x, y), (x + width, y + height), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x, y), (x + width, y), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x, y + height), (x + width, y + height), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x, y), (x, y + height), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x + width, y), (x + width, y + height), color, 3, cv2.LINE_AA)


def _place_anime_box(frame, results):
    """Show the desktop rectangle between two index tips. Peace places it later."""
    global _anime_ready
    from web import anime_region
    tips = anime_region.index_tips(results)
    height, width = frame.shape[:2]
    origin_x, origin_y, screen_w, screen_h = _screen_bounds()
    image_rect = None
    screen_rect = None
    if tips:
        image_rect, screen_rect = anime_region.rect_from_tips(
            tips[0], tips[1], width, height, origin_x, origin_y, screen_w, screen_h,
        )
    if image_rect is None:
        return
    _capture_box().show(screen_rect)
    place = _placement()
    locked = place.update(screen_rect, time.time())
    if locked:
        _anime_ready = locked
    elif place._locked is None:
        _anime_ready = None


def _commit_anime_box():
    """Peace grabs the held desktop rectangle and stipples it on the board."""
    global _anime_ready
    rect = _anime_ready
    if not rect:
        print("Anime: hold the box with two index fingers, then peace.")
        return
    if not anime_begin("screen", rect=rect):
        speak(line("no_picture"))
        return
    _anime_ready = None
    _placement().release()
    if _capture_frame is not None:
        _capture_frame.hide()


def draw_anime_overlay(frame):
    """Paint stipple into `frame`. The camera loop passes a copy for the board window."""
    return _load_anime_mod().draw_anime_overlay(frame)


def _load_pointer():
    global _pointer_mod
    if _pointer_mod is None:
        from web import pointer_hands
        _pointer_mod = pointer_hands
    return _pointer_mod


def _drive_pointer(frame, rgb_frame, results=None):
    """Index tip moves the Windows cursor. Overlay modes do not call this."""
    module = _load_pointer()
    module.watch_youtube_window()
    if not module.armed():
        return
    if results is None:
        results = hands.process(rgb_frame)
    module.drive(frame, results)


def _browser_exe():
    """Edge, then Chrome. The stipple board is a page, not an OpenCV window."""
    names = (
        r"Microsoft\Edge\Application\msedge.exe",
        r"Google\Chrome\Application\chrome.exe",
    )
    roots = (
        os.environ.get("PROGRAMFILES(X86)", ""),
        os.environ.get("PROGRAMFILES", ""),
        os.environ.get("LOCALAPPDATA", ""),
    )
    for name in names:
        for root in roots:
            if not root:
                continue
            path = Path(root) / name
            if path.is_file():
                return path
    return None


def _crop_has_ink(crop):
    """Near-white paper is not a picture. The board drops those pixels too."""
    if crop is None or getattr(crop, "size", 0) == 0 or crop.ndim != 3:
        return False
    sample = crop[::4, ::4].astype(np.float32)
    tone = (0.2126 * sample[:, :, 2] + 0.7152 * sample[:, :, 1] + 0.0722 * sample[:, :, 0]) / 255.0
    return bool(np.any(tone <= 0.93))


class _AnimeBoardHandler(BaseHTTPRequestHandler):
    """The crop, p5, and the board page. Nothing else on this port."""

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        root = Path(__file__).resolve().parent / "web"
        if path in ("/", "/index.html"):
            self._send(root / "anime_board.html", "text/html; charset=utf-8", nostore=True)
        elif path == "/p5.min.js":
            self._send(root / "p5.min.js", "text/javascript; charset=utf-8")
        elif path == "/crop.png":
            self._send(_p5_crop, "image/png", nostore=True)
        elif path == "/arm":
            self._bytes(b"go" if _p5_armed else b"hold", "text/plain", nostore=True)
        elif path == "/filled":
            _note_p5_filled()
            self._bytes(b"ok", "text/plain")
        else:
            self.send_error(404)

    def log_message(self, _fmt, *_args):
        return

    def _send(self, path, content_type, nostore=False):
        if path is None or not Path(path).is_file():
            self.send_error(404)
            return
        self._bytes(Path(path).read_bytes(), content_type, nostore=nostore)

    def _bytes(self, body, content_type, nostore=False):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if nostore:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def _note_p5_filled():
    global _p5_filled
    if _p5_filled:
        return
    _p5_filled = True
    print("Anime stipple filled.")


def _ensure_p5_server():
    global _p5_httpd, _p5_port
    if _p5_httpd is not None:
        return _p5_port
    for port in range(8791, 8796):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), _AnimeBoardHandler)
        except OSError:
            continue
        threading.Thread(target=httpd.serve_forever, name="anime-p5", daemon=True).start()
        _p5_httpd = httpd
        _p5_port = port
        return port
    return None


def _arm_stipple(reason):
    """Start the heart. A snap or an exact voice phrase sets this. Dance does not."""
    global _p5_armed, _anime_cam_hold
    if not _p5_open or _p5_armed:
        return
    _p5_armed = True
    _anime_cam_hold = True
    print(f"Anime stipple started by {reason}.", flush=True)


def _open_p5_board(crop):
    """Full-screen still of this crop. The heart waits for a snap or voice."""
    global _p5_open, _p5_proc, _p5_crop, _p5_filled, _p5_armed, _preview_cam_logged
    _preview_cam_logged = False
    folder = Path(os.environ.get("LOCALAPPDATA", "")) / "asmamir"
    folder.mkdir(parents=True, exist_ok=True)
    crop_path = folder / "anime-crop.png"
    if not cv2.imwrite(str(crop_path), crop):
        print("Anime board: could not save the crop.")
        return False
    if _p5_open or _p5_proc is not None:
        _close_p5_board()
    _p5_crop = crop_path
    _p5_filled = False
    _p5_armed = False
    _anime_cam_hold = False
    port = _ensure_p5_server()
    browser = _browser_exe()
    if port is None or browser is None:
        print("Anime board: the p5 page did not start.")
        return False
    profile = folder / "anime-p5-profile"
    url = f"http://127.0.0.1:{port}/?n={int(time.time())}"
    edge = browser.name.lower().startswith("msedge")
    if edge:
        command = [
            str(browser),
            "--kiosk", url,
            "--edge-kiosk-type=fullscreen",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
        ]
    else:
        command = [
            str(browser),
            f"--app={url}",
            "--start-fullscreen",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
        ]
    _p5_proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _p5_open = True
    from web import hologram_dance
    hologram_dance.reset_preview_snap()
    print("Anime preview holding. Snap, or say start, capture, start capture, or take screenshot.")
    return True


def _close_stipple_browser():
    """Close every Edge window whose title contains Anime stipple, and that profile."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found = []

    def visit(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if "Anime stipple" not in buf.value:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        user32.PostMessageW(hwnd, 0x0010, 0, 0)
        if pid.value:
            found.append(int(pid.value))
        return True

    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(proto(visit), 0)
    for pid in sorted(set(found)):
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -match 'msedge|chrome' -and $_.CommandLine -like '*anime-p5-profile*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
    )
    return bool(found)


def _close_p5_board():
    """Stop the stipple page, including an Edge window left after the handle is gone."""
    global _p5_open, _p5_proc, _p5_armed
    _hide_anime_camera()
    had_board = _p5_open or _p5_proc is not None
    _p5_armed = False
    _p5_open = False
    proc = _p5_proc
    _p5_proc = None
    if proc is not None and proc.poll() is None:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        had_board = True
    if _close_stipple_browser():
        had_board = True
    if had_board:
        print("Anime board closed.")


def _show_anime_board(image):
    """Full-screen stipple. The photo keeps its aspect, letterboxed on black."""
    global _anime_board_open, _anime_board_hidden
    if image is None:
        return
    if not _anime_board_open:
        cv2.namedWindow(ANIME_BOARD, cv2.WINDOW_NORMAL)
        cv2.moveWindow(ANIME_BOARD, 0, 0)
        cv2.setWindowProperty(ANIME_BOARD, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        _foreground(ANIME_BOARD)
        _anime_board_open = True
        _anime_board_hidden = False
        print("Anime board full screen.")
    elif _anime_board_hidden:
        cv2.moveWindow(ANIME_BOARD, 0, 0)
        cv2.setWindowProperty(ANIME_BOARD, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        _foreground(ANIME_BOARD)
        _anime_board_hidden = False
    cv2.imshow(ANIME_BOARD, image)
    _pin_anime_board()


def _hide_anime_board():
    """Move the board off the desktop before a screen grab."""
    global _anime_board_hidden
    if not _anime_board_open:
        return
    try:
        cv2.moveWindow(ANIME_BOARD, -32000, -32000)
        cv2.waitKey(1)
        _anime_board_hidden = True
    except Exception as exc:
        print(f"Anime: could not hide board ({exc})")


def _pin_anime_board():
    """Board stays above the camera. The finger box, while shown, stays above both."""
    try:
        import ctypes
        from web import anime_region
        user32 = ctypes.windll.user32
        if _capture_frame is not None and _capture_frame.visible:
            _capture_frame.raise_topmost()
        if _anime_board_open and not _anime_board_hidden:
            anime_region.raise_topmost(user32, anime_region.hwnd_by_title(user32, ANIME_BOARD))
    except Exception as exc:
        print(f"Anime board: {exc}")


def _close_select():
    """Drop the drag overlay. The picture, if one was taken, stays."""
    global _select_open, _select_shot, _drag_anchor, _drag_point, _drag_rect
    _select_shot = None
    _drag_anchor = None
    _drag_point = None
    _drag_rect = None
    if not _select_open:
        return
    try:
        cv2.destroyWindow(SELECT_WINDOW)
    except Exception:
        pass
    _select_open = False


def _close_anime_board():
    """Camera thread only. Leaving anime mode drops the board and the drag overlay."""
    global _anime_board_open, _anime_board_hidden
    _close_select()
    _close_p5_board()
    if _capture_frame is not None:
        _capture_frame.close()
    if not _anime_board_open:
        return
    try:
        cv2.destroyWindow(ANIME_BOARD)
    except Exception:
        pass
    _anime_board_open = False
    _anime_board_hidden = False


def _screen_pixels():
    """Primary size in this process. OpenCV and the mouse use these pixels."""
    import ctypes
    user32 = ctypes.windll.user32
    return max(1, int(user32.GetSystemMetrics(0))), max(1, int(user32.GetSystemMetrics(1)))


def _named_hwnd(title):
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = ctypes.c_void_p
    return user32.FindWindowW(None, title) or None


def _show_named(title, show):
    """Hide without leaving fullscreen. Restoring fullscreen makes a tiny window."""
    import ctypes
    hwnd = _named_hwnd(title)
    if not hwnd:
        return
    ctypes.windll.user32.ShowWindow(ctypes.c_void_p(hwnd), 5 if show else 0)


def _select_mouse(event, x, y, _flags, _param):
    """Left-button drag on the frozen screen. Release stores the rectangle."""
    global _drag_anchor, _drag_point, _drag_rect
    shot = _select_shot
    if shot is None:
        return
    width, height = _screen_pixels()
    x = max(0, min(width - 1, int(x)))
    y = max(0, min(height - 1, int(y)))
    if event == cv2.EVENT_LBUTTONDOWN:
        if _reselect_drag and _drag_anchor is not None:
            return
        _drag_anchor = (x, y)
        _drag_point = (x, y)
        _drag_rect = None
        print("Anime select: drag started.")
    elif event == cv2.EVENT_MOUSEMOVE and _drag_anchor is not None and _drag_rect is None:
        _drag_point = (x, y)
    elif event == cv2.EVENT_LBUTTONUP and _drag_anchor is not None:
        x0, y0 = _drag_anchor
        left, right = sorted((x0, x))
        top, bottom = sorted((y0, y))
        _drag_anchor = None
        _drag_point = None
        scale_x, scale_y = _select_scale
        shot_h, shot_w = shot.shape[:2]
        left = max(0, min(shot_w - 2, int(round(left * scale_x))))
        top = max(0, min(shot_h - 2, int(round(top * scale_y))))
        right = max(left + 1, min(shot_w, int(round(right * scale_x))))
        bottom = max(top + 1, min(shot_h, int(round(bottom * scale_y))))
        if right - left >= 16 and bottom - top >= 16:
            _drag_rect = (left, top, right - left, bottom - top)


def _left_down():
    import ctypes
    return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)


def _note_mouse():
    """True on the frame the left button goes down."""
    global _mouse_was_down
    down = _left_down()
    edge = down and not _mouse_was_down
    _mouse_was_down = down
    return edge


def _cursor_xy():
    import ctypes
    from ctypes import wintypes
    point = wintypes.POINT()
    user32 = ctypes.windll.user32
    user32.GetCursorPos(ctypes.byref(point))
    hwnd = _named_hwnd(SELECT_WINDOW)
    if hwnd:
        user32.ScreenToClient(ctypes.c_void_p(hwnd), ctypes.byref(point))
    width, height = _screen_pixels()
    return max(0, min(width - 1, int(point.x))), max(0, min(height - 1, int(point.y)))


def _start_reselect():
    """A new drag while the board is up. The next picture waits again."""
    global _select_shot, _select_origin, _drag_anchor, _drag_point, _drag_rect, _reselect_drag
    import ctypes
    from ctypes import wintypes
    point = wintypes.POINT()
    user32 = ctypes.windll.user32
    user32.GetCursorPos(ctypes.byref(point))
    saved_x, saved_y = int(point.x), int(point.y)
    _show_named("Anime stipple", False)
    cv2.waitKey(1)
    shot, origin = _grab_desktop()
    if shot is None:
        _show_named("Anime stipple", True)
        print("Anime: the new grab failed. The picture stays.")
        return
    _select_shot = shot
    _select_origin = origin
    _drag_rect = None
    _reselect_drag = True
    _open_select()
    _pin_select_window()
    point.x, point.y = saved_x, saved_y
    hwnd = _named_hwnd(SELECT_WINDOW)
    if hwnd:
        user32.ScreenToClient(ctypes.c_void_p(hwnd), ctypes.byref(point))
    width, height = _screen_pixels()
    x = max(0, min(width - 1, int(point.x)))
    y = max(0, min(height - 1, int(point.y)))
    _drag_anchor = (x, y)
    _drag_point = (x, y)
    print("Anime: drag a new rectangle.")


def _grab_desktop():
    """One still of the primary screen after our windows have moved aside."""
    _park_for_anime()
    _hide_anime_board()
    cv2.waitKey(1)
    time.sleep(0.25)
    from web.anime_region import primary_bounds
    left, top, width, height = primary_bounds()
    shot = _load_anime_mod().grab_region(left, top, width, height)
    return shot, (int(left), int(top), int(width), int(height))


def _open_select():
    """Create the drag window. Size and z-order are applied after the first image."""
    global _select_open, _select_raised
    if _select_open:
        return
    cv2.namedWindow(SELECT_WINDOW, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(SELECT_WINDOW, _select_mouse)
    _select_open = True
    _select_raised = False


def _select_display(shot):
    """Fit the still to the screen so a click lands on the pixel under the cursor."""
    global _select_scale
    width, height = _screen_pixels()
    view = cv2.resize(shot, (width, height), interpolation=cv2.INTER_LINEAR)
    _select_scale = (shot.shape[1] / width, shot.shape[0] / height)
    return view


def _pin_select_window():
    """Borderless, topmost, and the size of the primary monitor. Photos stays behind."""
    global _select_raised
    import ctypes
    hwnd = _named_hwnd(SELECT_WINDOW)
    if not hwnd:
        return
    user32 = ctypes.windll.user32
    width, height = _screen_pixels()
    GWL_STYLE = -16
    WS_POPUP = 0x80000000
    WS_VISIBLE = 0x10000000
    user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_STYLE, WS_POPUP | WS_VISIBLE)
    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = ctypes.c_int
    # Show and apply the new style. Do not activate mid-drag or the button-up is lost.
    flags = 0x0040 | 0x0020
    if _drag_anchor is not None:
        flags |= 0x0010
    user32.SetWindowPos(ctypes.c_void_p(hwnd), ctypes.c_void_p(-1), 0, 0, width, height, flags)
    if _drag_anchor is None:
        user32.ShowWindow(ctypes.c_void_p(hwnd), 9)
        user32.keybd_event(0x12, 0, 0, 0)
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
        user32.keybd_event(0x12, 0, 2, 0)
    if not _select_raised:
        _select_raised = True
        print(f"Anime select on top. {width}x{height}")


def _show_anime_camera(frame):
    """Visible while recording a snap, or while a selected still is waiting."""
    global _anime_cam_open
    if _p5_armed or _anime_cam_hold:
        _hide_anime_camera(force=True)
        return
    if not _anime_cam_open:
        cv2.namedWindow(ANIME_CAM, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(ANIME_CAM, int(frame.shape[1]), int(frame.shape[0]))
        cv2.moveWindow(ANIME_CAM, 24, 24)
        _anime_cam_open = True
        if _recording_snap:
            print("Anime camera on for record snap.", flush=True)
        else:
            print("Anime camera on. The still is waiting.", flush=True)
    cv2.imshow(ANIME_CAM, frame)
    try:
        cv2.setWindowProperty(ANIME_CAM, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass
    cv2.waitKey(1)


def _hide_anime_camera(force=False):
    """Drop the snap camera. Call this from the window thread only."""
    global _anime_cam_open
    if not force and not _anime_cam_open and not _p5_armed and not _anime_cam_hold:
        return
    if _recording_snap and not _p5_armed and not _anime_cam_hold and not force:
        return
    was = _anime_cam_open
    _anime_cam_open = False
    try:
        cv2.destroyWindow(ANIME_CAM)
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        found = []

        def visit(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if title != ANIME_CAM and not title.startswith("Anime camera"):
                return True
            found.append(hwnd)
            user32.ShowWindow(hwnd, 0)
            user32.PostMessageW(hwnd, 0x0010, 0, 0)
            return True

        proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(proto(visit), 0)
        was = was or bool(found)
    except Exception:
        pass
    cv2.waitKey(1)
    if was:
        print("Anime camera off.", flush=True)


def _present_anime():
    """Show the screen, then hold the dragged photo until a snap or voice."""
    global anime_pending, _reselect_drag, _select_warned, _select_shot, _select_origin
    if _p5_armed:
        _hide_anime_camera()
        _ui_key(cv2.waitKey(1) & 0xFF)
        return
    edge = _note_mouse()
    if _p5_open and _select_shot is None and edge:
        _start_reselect()
    if _reselect_drag and _select_open and _drag_anchor is not None and not _left_down():
        x, y = _cursor_xy()
        _select_mouse(cv2.EVENT_LBUTTONUP, x, y, 0, None)
        _reselect_drag = False
    if anime_pending:
        anime_pending = None
        _load_anime_mod().reset()
        _close_select()
        _close_p5_board()
        _reselect_drag = False
        _select_warned = False
        print("Anime: drag a rectangle.")
    if _p5_open and _select_shot is None:
        if not _p5_armed:
            try:
                if _watch_wake_snap(preview=True):
                    _arm_stipple(_snap_reason)
            except Exception as exc:
                print(f"Snap watch stayed up: {exc}")
                time.sleep(0.05)
        if _p5_armed:
            _hide_anime_camera()
        _ui_key(cv2.waitKey(1) & 0xFF)
        return
    _hide_anime_camera()
    _drain_camera()
    _park_for_anime()
    if _capture_frame is not None and _capture_frame.visible:
        _capture_frame.hide()
    if _select_shot is None:
        shot, origin = _grab_desktop()
        if shot is None:
            if not _select_warned:
                _select_warned = True
                print("Anime: the screen grab failed.")
                speak(line("no_picture"))
            _ui_key(cv2.waitKey(1) & 0xFF)
            return
        _select_shot = shot
        _select_origin = origin
        _open_select()
    view = _select_display(_select_shot)
    if _drag_anchor is not None and _drag_point is not None:
        cv2.rectangle(view, _drag_anchor, _drag_point, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.rectangle(view, _drag_anchor, _drag_point, (255, 255, 255), 1, cv2.LINE_AA)
    if _drag_rect is not None and _select_shot is not None:
        x, y, width, height = _drag_rect
        crop = np.ascontiguousarray(_select_shot[y:y + height, x:x + width])
        was_reselect = _reselect_drag
        _reselect_drag = False
        _close_select()
        if crop.size == 0 or not _crop_has_ink(crop):
            print("Anime: that rectangle had no picture.")
            if was_reselect and (_p5_proc is not None):
                _show_named("Anime stipple", True)
            else:
                speak(line("no_picture"))
        else:
            print(f"Anime drag {width}x{height} at {x},{y}")
            _open_p5_board(crop)
        _ui_key(cv2.waitKey(1) & 0xFF)
        return
    cv2.imshow(SELECT_WINDOW, view)
    try:
        cv2.setWindowProperty(SELECT_WINDOW, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass
    _pin_select_window()
    _ui_key(cv2.waitKey(1) & 0xFF)


def _park_for_anime():
    """Hide standby so the grab and the drag overlay are the screen."""
    global _anime_parked
    if not _standby_window:
        return
    try:
        _show_named(WINDOW, False)
        _anime_parked = True
    except Exception as exc:
        print(f"Anime: could not move the standby window ({exc})")


def _unpark_after_anime():
    """Bring the standby window back after anime ends."""
    global _anime_parked
    if not _anime_parked or not _standby_window:
        _anime_parked = False
        return
    _anime_parked = False
    try:
        _show_named(WINDOW, True)
        cv2.moveWindow(WINDOW, 0, 0)
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    except Exception as exc:
        print(f"Anime: could not restore the standby window ({exc})")


def _stipple_board():
    """Full-screen black board. The stipple is letterboxed to the photo."""
    module = _load_anime_mod()
    if not module.has_picture():
        return None
    from web.anime_region import primary_bounds
    _left, _top, width, height = primary_bounds()
    board = np.zeros((max(360, int(height)), max(640, int(width)), 3), dtype=np.uint8)
    return module.draw_anime_overlay(board)


def apply_camera_screen():
    """Camera thread. Fullscreen live view in front. Closes the stipple board."""
    global _show_camera
    if not _show_camera:
        return
    _show_camera = False
    _close_anime_board()
    try:
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.moveWindow(WINDOW, 0, 0)
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, WINDOW)
        if hwnd:
            user32.ShowWindow(hwnd, 9)
            user32.keybd_event(0x12, 0, 0, 0)
            user32.SetForegroundWindow(hwnd)
            user32.keybd_event(0x12, 0, 2, 0)
    except Exception as exc:
        print(f"Camera screen: {exc}")


def anime_poll_gestures(results):
    """Peace or one fist recapture the screen. Two fists do not. Only called while anime_active (not Airbus)."""
    return _load_anime_mod().poll_gestures(results)


def _has_picture(frame):
    """Reject empty, tiny, or black/scanline pads. Do not treat noise as a live image."""
    if frame is None or getattr(frame, "size", 0) == 0:
        return False
    if frame.ndim == 2:
        gray = frame
    elif frame.ndim == 3:
        gray = frame.mean(axis=2)
    else:
        return False
    h, w = gray.shape[:2]
    if h < 80 or w < 80:
        return False
    sample = np.asarray(gray[::8, ::8], dtype=np.float32)
    mean = float(sample.mean())
    hi = float(np.percentile(sample, 92))
    spread = float(sample.std())
    if hi < 22 or mean < 8:
        return False
    if spread < 4 and mean < 18:
        return False
    return True


def _arm_capture(capture):
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    try:
        capture.set(cv2.CAP_PROP_CONVERT_RGB, 1)
    except Exception:
        pass
    capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)


def _probe(index, backend, backend_name):
    # OpenCV 4.11 menolak CAP_PROP_OPEN_TIMEOUT_MSEC pada DSHOW,
    # lalu isOpened() jadi false meskipun webcam bebas.
    # MSMF is not opened. Its Media Foundation reader (the NVIDIA virtual
    # camera) access-violates on the next read, with no Python traceback,
    # while the microphone thread is already running.
    capture = cv2.VideoCapture(index, backend)
    if not capture.isOpened():
        capture.release()
        return None
    _arm_capture(capture)
    brightest = -1.0
    shape = None
    live = 0
    for _ in range(12):
        ok, sample = capture.read()
        cv2.waitKey(1)
        if not ok or sample is None or sample.size == 0:
            continue
        if not _has_picture(sample):
            continue
        live += 1
        brightest = max(brightest, float(sample.mean()))
        shape = (sample.shape[1], sample.shape[0])
    if live < 2 or shape is None:
        capture.release()
        print(f"index {index} / {backend_name}: tidak ada gambar (hitam/kosong)")
        return None
    print(f"index {index} / {backend_name}: {shape[0]}x{shape[1]}, kecerahan {brightest:.1f}")
    return brightest, capture


def _open_best_camera(skip=None):
    """DirectShow only. Keep the capture that already showed a picture.

    Releasing that capture and opening it again, or opening MSMF at all,
    kills the process while it is still waiting for a snap.
    """
    found = []
    skip = skip or ()
    for index in (0, 1, 2):
        backend, backend_name = cv2.CAP_DSHOW, "DSHOW"
        if (index, backend) in skip:
            continue
        probed = _probe(index, backend, backend_name)
        if probed is None:
            time.sleep(0.08)
            continue
        score, capture = probed
        found.append((score, index, backend, backend_name, capture))
        # The next DirectShow index is the NVIDIA virtual camera. Opening it
        # and then releasing it access-violates a few seconds later, after
        # the real camera is already on and a phrase came back unclear.
        break
    if not found:
        return None
    found.sort(key=lambda item: item[0], reverse=True)
    brightness, index, backend, backend_name, capture = found[0]
    for extra in found[1:]:
        try:
            extra[4].release()
        except Exception:
            pass
    if brightness < 25:
        capture.set(cv2.CAP_PROP_BRIGHTNESS, 180)
        capture.set(cv2.CAP_PROP_GAIN, 100)
    print(f"--> Dipakai index {index} / {backend_name} (kecerahan {brightness:.1f})")
    return capture, index, backend, backend_name


cap = None
cam_index = None
cam_backend = None
cam_backend_name = ""
last_good = None
miss_frames = 0
_hologram_tick = 0

print("\n[Asmamir] Quiet. No window until a thumb-to-middle snap or the word asmamir. Chat: Hermes 127.0.0.1:8642, then Ollama 127.0.0.1:11434.")

def _drain_camera():
    """One hidden read while the anime overlay is up, so the open camera stays live."""
    if cap is None or not cap.isOpened():
        return
    try:
        cap.read()
    except Exception:
        pass


def _release_camera():
    """Drop the webcam. The hologram does not keep a capture open."""
    global cap, last_good, miss_frames
    if cap is None:
        return
    try:
        cap.release()
    except Exception:
        pass
    cap = None
    last_good = None
    miss_frames = 0
    _drop_latest_frame()
    print("Camera released.")


def _foreground(title):
    try:
        import ctypes
        hwnd = _named_hwnd(title)
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        user32.ShowWindow(ctypes.c_void_p(hwnd), 9)
        user32.keybd_event(0x12, 0, 0, 0)
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
        user32.keybd_event(0x12, 0, 2, 0)
    except Exception as exc:
        print(f"Window focus: {exc}")


def _present_fog(frame):
    """Own fullscreen window. The 3D standby window is moved aside."""
    global _fog_window_open
    if not _fog_window_open:
        cv2.namedWindow(FOG_WINDOW, cv2.WINDOW_NORMAL)
        try:
            cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
            cv2.moveWindow(WINDOW, -32000, -32000)
        except Exception as exc:
            print(f"Standby hide: {exc}")
        cv2.setWindowProperty(FOG_WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        _foreground(FOG_WINDOW)
        _fog_window_open = True
        print("Fog window open.")
    cv2.imshow(FOG_WINDOW, frame)


def _close_fog_window():
    """Camera thread. Drop the fog window. The caller shows the next window."""
    global _fog_window_open
    if not _fog_window_open:
        return
    try:
        cv2.destroyWindow(FOG_WINDOW)
    except Exception:
        pass
    _fog_window_open = False
    print("Fog window closed.")


def _ensure_standby_window():
    global _standby_window
    if _standby_window:
        return
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.moveWindow(WINDOW, 0, 0)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    _foreground(WINDOW)
    _standby_window = True
    print("Standby is on screen.")


def _show_hologram():
    global _hologram_tick
    from web import hologram_cv, hologram_mesh
    _ensure_standby_window()
    hologram_mesh.warm()
    _hologram_tick += 1
    plate = hologram_cv.render(*_screen_pixels(), _hologram_tick)
    cv2.imshow(WINDOW, plate)


def _hide_standby():
    """Hide Arissa. Leaving fullscreen would shrink her to a tiny window on screen."""
    global _standby_hidden
    if _standby_window:
        try:
            _show_named(WINDOW, False)
        except Exception as exc:
            print(f"Standby hide: {exc}")
    _standby_hidden = True


def _reveal_standby():
    """The Arissa window is the only one on screen."""
    global _standby_hidden, _anime_parked, _standby_parked
    _anime_parked = False
    _standby_parked = False
    _standby_hidden = False
    _ensure_standby_window()
    try:
        _show_named(WINDOW, True)
        cv2.moveWindow(WINDOW, 0, 0)
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        _foreground(WINDOW)
    except Exception as exc:
        print(f"Standby show: {exc}")


def _ensure_dance_window():
    global _dance_window_open
    if _dance_window_open:
        return
    cv2.namedWindow(DANCE_WINDOW, cv2.WINDOW_NORMAL)
    cv2.moveWindow(DANCE_WINDOW, 0, 0)
    cv2.setWindowProperty(DANCE_WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    _foreground(DANCE_WINDOW)
    _dance_window_open = True
    print("Dance window open.")


def _close_dance_window():
    global _dance_window_open
    if not _dance_window_open:
        return
    try:
        cv2.destroyWindow(DANCE_WINDOW)
    except Exception:
        pass
    _dance_window_open = False
    print("Dance window closed.")


def _exclusive(keep):
    """One mode window. Standby, dance, anime, fog, or the camera vision window."""
    global _surface
    if _surface == keep:
        return
    _surface = keep
    if keep != "anime":
        _close_anime_board()
        if _capture_frame is not None and _capture_frame.visible:
            _capture_frame.hide()
    if keep != "fog":
        _close_fog_window()
    if keep != "dance":
        _close_dance_window()
    if keep in ("dance", "anime", "fog"):
        _hide_standby()
    else:
        _reveal_standby()
    print(f"Window: {keep}")


def _present_dance():
    """Full-screen dance. Hands still orbit and snap. Standby stays hidden."""
    global cap, cam_index, cam_backend, cam_backend_name, last_good, miss_frames, _hologram_tick
    from web import hologram_cv, hologram_mesh, hologram_dance, hologram_orbit
    _ensure_dance_window()
    if cap is None or not cap.isOpened():
        opened = _open_best_camera()
        if opened is None:
            hologram_mesh.warm()
            _hologram_tick += 1
            cv2.imshow(DANCE_WINDOW, hologram_cv.render(*_screen_pixels(), _hologram_tick))
            _ui_key(cv2.waitKey(1) & 0xFF)
            time.sleep(0.05)
            return
        cap, cam_index, cam_backend, cam_backend_name = opened
        last_good = None
        miss_frames = 0
    success, frame = cap.read()
    if success and frame is not None and frame.size != 0 and _has_picture(frame):
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        frame = cv2.flip(frame, 1)
        rgb_frame = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        rgb_frame.flags.writeable = False
        seen = hands.process(rgb_frame)
        landmarks = getattr(seen, "multi_hand_landmarks", None)
        hologram_orbit.apply(
            landmarks,
            frame.shape[1],
            frame.shape[0],
            getattr(seen, "multi_handedness", None),
        )
        if hologram_dance.feed_snap(landmarks):
            hologram_dance.cycle()
    hologram_mesh.warm()
    _hologram_tick += 1
    cv2.imshow(DANCE_WINDOW, hologram_cv.render(*_screen_pixels(), _hologram_tick))
    _ui_key(cv2.waitKey(1) & 0xFF)


def _foreground_hwnd(hwnd):
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)
        user32.keybd_event(0x12, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(0x12, 0, 2, 0)
    except Exception as exc:
        print(f"Window focus: {exc}")


def _park_standby():
    """Move the 3D window off the desktop so YouTube and the cursor stay visible."""
    global _standby_parked
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, 320, 180)
    cv2.moveWindow(WINDOW, -32000, -32000)
    if _standby_parked:
        return
    _standby_parked = True
    hwnd = _load_pointer().youtube_hwnd()
    if hwnd:
        _foreground_hwnd(hwnd)
    print("YouTube in front. Index moves the cursor. Pinch plays and pauses.")


def _restore_standby_window():
    """Bring the 3D standby back after YouTube no longer needs the cursor."""
    global _standby_parked
    if not _standby_parked:
        return
    _standby_parked = False
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.moveWindow(WINDOW, 0, 0)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    _foreground(WINDOW)
    print("YouTube cursor off. Standby.")


_snap_cam_warned = False
_preview_cam_logged = False


def _watch_wake_snap(preview=False):
    """Hidden camera. One thumb-to-middle snap wakes her. A clap does not.

    preview=True uses the looser held-board detector and does not cycle dance.
    """
    global cap, cam_index, cam_backend, cam_backend_name, last_good, miss_frames, _snap_cam_warned, _preview_cam_logged, _snap_reason
    from web import hologram_dance
    if cap is None or not cap.isOpened():
        opened = _open_best_camera()
        if opened is None:
            if not _snap_cam_warned:
                _snap_cam_warned = True
                print("Camera did not open. Say asmamir to wake.")
            time.sleep(0.4)
            return False
        cap, cam_index, cam_backend, cam_backend_name = opened
        last_good = None
        miss_frames = 0
        if _recording_snap or preview:
            print("Anime camera opening.", flush=True)
        else:
            print("Camera on, no window. Snap thumb to middle, or say asmamir.")
    try:
        ok, frame = cap.read()
    except Exception as exc:
        print(f"Snap camera read failed: {exc}")
        time.sleep(0.2)
        return False
    if not ok or frame is None or getattr(frame, "size", 0) == 0 or not _has_picture(frame):
        time.sleep(0.03)
        return False
    try:
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        elif frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        frame = cv2.flip(frame, 1)
        if _p5_armed or _anime_cam_hold:
            _hide_anime_camera(force=True)
            return False
        if (_recording_snap or preview) and not _p5_armed:
            _show_anime_camera(frame)
            if preview and not _preview_cam_logged:
                _preview_cam_logged = True
                print(
                    f"Anime camera reading {frame.shape[1]}x{frame.shape[0]}, "
                    f"brightness {float(frame.mean()):.0f}.",
                    flush=True,
                )
        if _recording_snap:
            _keep_record_frame(frame)
        rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        rgb.flags.writeable = False
        seen = hands.process(rgb)
        landmarks = getattr(seen, "multi_hand_landmarks", None)
        try:
            hologram_dance.note_motion(landmarks)
        except Exception as exc:
            print(f"Snap motion skipped: {exc}", flush=True)
            landmarks = None
        if preview and not _p5_armed:
            _show_anime_camera(frame)
            distance = hologram_dance.latest_thumb_middle()
            if distance is not None:
                matched = hologram_dance.hand_matches_snap1()
                score = hologram_dance.motion_score_now()
                print(
                    f"Anime hand thumb-middle {distance:.2f}. snap-1 score {score:.2f}. "
                    f"match {'yes' if matched else 'no'}.",
                    flush=True,
                )
            if hologram_dance.matches_saved_motion():
                _snap_reason = "motion match"
                snapped = True
            else:
                snapped = False
        else:
            snapped = hologram_dance.feed_snap(landmarks)
    except Exception as exc:
        print(f"Snap watch stayed up: {exc}")
        time.sleep(0.05)
        return False
    time.sleep(0.01)
    return snapped


def _ui_key(key):
    if key == ord("q"):
        request_shutdown()
    if key == ord("f"):
        set_session_mode("fruit")
        print("Fruit ON")
    if key == ord("c"):
        set_session_mode("count")
        print("Counting ON")
    if key == ord(" "):
        cut_speech()


# =====================================================================
# 5. LOOP UTAMA PROGRAM
# =====================================================================
while True:
    if shutdown_requested:
        finish_shutdown()
    if _restart_anime:
        _restart_anime = False
        _anime_cam_hold = False
        _p5_armed = False
        _select_shot = None
        _close_p5_board()
        _hide_anime_camera(force=True)
        set_session_mode("anime")
        anime_pending = "screen"
        print("Restart anime. Drag a rectangle.", flush=True)
    if _need_ui_standby:
        _need_ui_standby = False
        _anime_cam_hold = False
        job = _snap_save
        _snap_save = None
        writer = job.get("writer") if isinstance(job, dict) else None
        if writer is not None:
            try:
                writer.release()
            except Exception:
                pass
        _close_p5_board()
        _hide_anime_camera(force=True)
    if _p5_armed or _anime_cam_hold:
        if _anime_cam_open:
            _hide_anime_camera(force=True)
        cv2.waitKey(1)
        continue
    elif _snap_save is not None:
        _pump_snap_save()
        continue
    elif _recording_snap:
        _capture_record_frame()
        continue
    if _snap_close:
        _snap_close = False
        if not (_p5_open and not _p5_armed):
            _hide_anime_camera()
    load_indonesian_listener()
    from web import hologram_dance
    if anime_active:
        _exclusive("anime")
        _present_anime()
        continue
    if hologram_dance.active():
        _exclusive("dance")
        _present_dance()
        continue
    if not _vision_modes_on():
        _unpark_after_anime()
        if not _standby_visible:
            try:
                snapped = _watch_wake_snap()
            except Exception as exc:
                print(f"Snap watch stayed up: {exc}")
                time.sleep(0.2)
                continue
            if snapped:
                print("Snap. Assistant is awake.")
                request_camera_screen()
                speak(line("wake"))
            continue
        _exclusive("standby")
        if _fog_window_open:
            _close_fog_window()
        pointer = _load_pointer()
        pointer.watch_youtube_window()
        if cap is None or not cap.isOpened():
            _show_hologram()
            cv2.waitKey(1)
            opened = _open_best_camera()
            if opened is None:
                print("Camera did not open. Hologram stays up. Orbit waits.")
                _show_hologram()
                _ui_key(cv2.waitKey(1) & 0xFF)
                time.sleep(0.4)
                continue
            cap, cam_index, cam_backend, cam_backend_name = opened
            last_good = None
            miss_frames = 0
            print("Camera on to read orbit hands. The hologram stays on screen.")
        success, frame = cap.read()
        youtube_cursor = pointer.armed() and pointer.youtube_showing()
        if success and frame is not None and frame.size != 0 and _has_picture(frame):
            if frame.ndim == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            frame = cv2.flip(frame, 1)
            rgb_frame = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            rgb_frame.flags.writeable = False
            seen = hands.process(rgb_frame)
            if not youtube_cursor:
                from web import hologram_dance, hologram_orbit
                landmarks = getattr(seen, "multi_hand_landmarks", None)
                hologram_orbit.apply(
                    landmarks,
                    frame.shape[1],
                    frame.shape[0],
                    getattr(seen, "multi_handedness", None),
                )
                if hologram_dance.feed_snap(landmarks):
                    hologram_dance.cycle()
            if pointer.armed():
                pointer.drive(frame, seen)
        if youtube_cursor:
            _show_hologram()
        else:
            _restore_standby_window()
            _show_hologram()
        _ui_key(cv2.waitKey(1) & 0xFF)
        if youtube_cursor:
            _park_standby()
        continue
    _exclusive("fog" if fog_active else "vision")
    if _standby_parked:
        _restore_standby_window()
    if cap is None or not cap.isOpened():
        _show_hologram()
        cv2.waitKey(1)
        opened = _open_best_camera()
        if opened is None:
            print("Camera did not open. Staying on the hologram.")
            _show_hologram()
            _ui_key(cv2.waitKey(1) & 0xFF)
            time.sleep(0.4)
            continue
        cap, cam_index, cam_backend, cam_backend_name = opened
        last_good = None
        miss_frames = 0
        print("Camera on.")
    if anime_active:
        _park_for_anime()
    else:
        _unpark_after_anime()
        apply_camera_screen()
    success, frame = cap.read()
    if not success or frame is None or frame.size == 0 or not _has_picture(frame):
        if shutdown_requested:
            finish_shutdown()
        miss_frames += 1
        if last_good is None:
            if miss_frames in (1, 30, 90):
                print("Kamera kosong/hitam — menunggu gambar, tidak menampilkan pad hitam.")
            if miss_frames >= 45:
                print("Buka ulang kamera (DSHOW)...")
                try:
                    cap.release()
                except Exception:
                    pass
                again = _open_best_camera(skip=((cam_index, cam_backend),))
                if again is None:
                    again = _open_best_camera()
                if again is not None:
                    cap, cam_index, cam_backend, cam_backend_name = again
                    globals()["cap"] = cap
                    miss_frames = 0
            if shutdown_requested:
                finish_shutdown()
            cv2.waitKey(1)
            continue
        frame = last_good.copy()
        if miss_frames >= 45:
            print("Buka ulang kamera (DSHOW)...")
            try:
                cap.release()
            except Exception:
                pass
            again = _open_best_camera()
            if again is not None:
                cap, cam_index, cam_backend, cam_backend_name = again
                globals()["cap"] = cap
                miss_frames = 0
    else:
        miss_frames = 0
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        # Webcam buffers are usually selfie-mirrored. Undo that so left-right matches the room.
        frame = cv2.flip(frame, 1)
        last_good = frame.copy()

    page = frame
    remember_frame(frame, page)
    deagle_now = deagle_active
    dragon_now = dragon_active
    canvas_now = canvas_active
    airbus_now = airbus_active
    filter_now = filter_active
    anime_now = anime_active
    fog_now = fog_active
    count_now = system_active
    fruit_now = fruit_active
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    current_total = 0
    hand_seen = False

    if deagle_now:
        results = hands.process(rgb_frame)
        draw_deagle_overlay(frame, results)
    elif dragon_now:
        results = hands.process(rgb_frame)
        draw_dragon_overlay(frame, results)
    elif canvas_now:
        results = hands.process(rgb_frame)
        draw_canvas_overlay(frame, results)
    elif filter_now:
        results = hands.process(rgb_frame)
        draw_filter_overlay(frame, results)
    elif anime_now:
        if _capture_frame is not None and _capture_frame.visible:
            _capture_frame.hide()
    elif fog_now:
        results = hands.process(rgb_frame)
        draw_fog_overlay(frame, results)
        _present_fog(frame)
    elif airbus_now:
        results = hands.process(rgb_frame)
        draw_airbus_overlay(frame, results)
    elif count_now:
        results = hands.process(rgb_frame)

        if results.multi_hand_landmarks is not None and results.multi_handedness is not None:
            hand_seen = True
            height, width = frame.shape[:2]
            ranked = []
            for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks): # type: ignore
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                landmarks = hand_landmarks.landmark
                # MediaPipe labels as if the picture were mirrored, even on the upright frame.
                hand_label = results.multi_handedness[hand_idx].classification[0].label
                fingers = []

                if hand_label == "Left":
                    fingers.append(1 if landmarks[FINGER_TIPS[0]].x > landmarks[FINGER_TIPS[0] - 1].x else 0)
                else:
                    fingers.append(1 if landmarks[FINGER_TIPS[0]].x < landmarks[FINGER_TIPS[0] - 1].x else 0)
                for i in range(1, 5):
                    fingers.append(1 if landmarks[FINGER_TIPS[i]].y < landmarks[FINGER_TIPS[i] - 2].y else 0)

                ranked.append((landmarks[0].x, landmarks, fingers))

            ranked.sort(key=lambda item: item[0])
            overlay_n = 0
            for _, landmarks, fingers in ranked:
                current_total += fingers.count(1)
                for i, raised in enumerate(fingers):
                    if not raised:
                        continue
                    overlay_n += 1
                    if overlay_n > 10:
                        break
                    tip = FINGER_TIPS[i]
                    tx = int(landmarks[tip].x * width)
                    ty = int(landmarks[tip].y * height)
                    cv2.putText(
                        frame, str(overlay_n), (tx - 14, max(36, ty - 16)),
                        cv2.FONT_HERSHEY_DUPLEX, 1.35, (0, 0, 0), 5, cv2.LINE_8,
                    )
            current_total = min(10, current_total)

            if current_total == stable_total:
                stable_hits += 1
            else:
                stable_total = current_total
                stable_hits = 1
            if stable_hits >= 6 and stable_total != last_total_count:
                last_total_count = stable_total
                print(f"Fingers: {stable_total}")
                if stable_total == 0:
                    speak("Tidak ada jari." if speech_language == "id" else "Zero fingers.")
                elif stable_total == 1:
                    speak("Satu jari." if speech_language == "id" else "There is 1 finger.")
                elif stable_total <= 10:
                    speak(
                        f"{stable_total} jari."
                        if speech_language == "id"
                        else f"There are {stable_total} fingers."
                    )

        if hand_seen and last_total_count >= 0:
            cv2.putText(frame, str(last_total_count), (40, 160),
                        cv2.FONT_HERSHEY_DUPLEX, 4.5, (0, 0, 0), 8)

    if fruit_now and (fruit_detector is not None or fruit_embedder is not None):
        best_name = ""
        best_score = 0.0
        best_box = None
        fruit_log_tick += 1
        check_fruit = fruit_log_tick % 8 == 0 and not speaking
        if check_fruit and fruit_embedder is not None and gallery_vectors is not None:
            height, width = rgb_frame.shape[:2]
            crop = rgb_frame[int(height * 0.2):int(height * 0.8), int(width * 0.2):int(width * 0.8)]
            small = cv2.resize(crop, (224, 224), interpolation=cv2.INTER_AREA)
            small = np.ascontiguousarray(small)
            embedded = fruit_embedder.embed(mp.Image(image_format=mp.ImageFormat.SRGB, data=small))
            vector = np.asarray(embedded.embeddings[0].embedding, dtype=np.float32)
            scores = gallery_vectors @ vector
            winner = int(np.argmax(scores))
            best_score = float(scores[winner])
            if best_score >= 0.55:
                best_name = gallery_names[winner]
                if fruit_log_tick % 40 == 0:
                    print(f"Fruit score {best_name} {best_score:.2f}")
            elif fruit_log_tick % 40 == 0:
                print(f"No fruit match {best_score:.2f}")
        if check_fruit and not best_name and fruit_detector is not None:
            height, width = rgb_frame.shape[:2]
            crop = rgb_frame[int(height * 0.2):int(height * 0.8), int(width * 0.2):int(width * 0.8)]
            detect_view = np.ascontiguousarray(cv2.resize(crop, (320, 320), interpolation=cv2.INTER_AREA))
            detected = fruit_detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=detect_view))
            for detection in detected.detections:
                category = detection.categories[0]
                name = category.category_name.lower()
                if name in FRUIT_NAMES and category.score > best_score:
                    best_name = name
                    best_score = category.score
        if best_name:
            fruit_misses = 0
            if best_box is not None:
                x = best_box.origin_x
                y = best_box.origin_y
                cv2.rectangle(frame, (x, y), (x + best_box.width, y + best_box.height), (0, 0, 0), 3)
            if best_name == stable_fruit:
                fruit_hits += 1
            else:
                stable_fruit = best_name
                fruit_hits = 1
            if fruit_hits == 2 and stable_fruit != last_spoken_fruit:
                last_spoken_fruit = stable_fruit
                print(f"Fruit: {stable_fruit}")
                article = "an" if stable_fruit[:1] in "aeiou" else "a"
                speak(line("fruit", article=article, name=stable_fruit))
        elif check_fruit:
            fruit_misses += 1
            if fruit_misses >= 2:
                stable_fruit = ""
                last_spoken_fruit = ""
                fruit_hits = 0
    if _show_camera:
        if last_good is not None:
            frame = last_good
        apply_camera_screen()
    elif not anime_now:
        _close_anime_board()
    if not (deagle_now or dragon_now or canvas_now or filter_now or anime_now or fog_now or airbus_now or count_now or fruit_now) and not _show_camera:
        _drive_pointer(frame, rgb_frame)
    if not fog_now:
        if _fog_window_open:
            _close_fog_window()
        if anime_now:
            _park_for_anime()
        else:
            _unpark_after_anime()
            cv2.imshow(WINDOW, frame)
    if anime_now and (_anime_board_open or (_capture_frame is not None and _capture_frame.visible)):
        _pin_anime_board()
    if shutdown_requested:
        finish_shutdown()

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        request_shutdown()
    if key == ord('f'):
        set_session_mode("fruit")
        print("Fruit ON")
    if key == ord('c'):
        set_session_mode("count")
        print("Counting ON")
    if key == ord(' '):
        cut_speech()

deadline = time.time() + 6
while (speaking or not speech_queue.empty()) and time.time() < deadline:
    time.sleep(0.05)
if cap is not None:
    cap.release()
cv2.destroyAllWindows()
