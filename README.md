# Asmamir Computer Vision

Asmamir Computer Vision is a Windows desktop application. One process, `app.py`, uses the webcam and microphone on this computer. After launch there is no window. Wake it with a thumb-to-middle finger snap, or by saying `asmamir`. The standby view is a hologram. Voice commands open the other modes. English speech recognition runs locally with Vosk.

The Python and HTML written for this project are MIT licensed. Third-party assets are not included. Read [SECURITY.md](SECURITY.md) before you run a copy or publish one.

## What is not in this repository

Download these yourself. Do not add them to git:

- The Vosk model, the Whisper cache, the Piper voice, and any other weights under `models/`.
- Mixamo FBX clips. The Mixamo license generally does not allow redistributing the FBX files. The names the code expects, in `web/hologram/`, are `asmamir_situp_to_idle.fbx`, `asmamir_rumba_dancing.fbx`, `asmamir_salsa_dancing.fbx`, and `asmamir_dancing_twerk.fbx`.
- Other 3D models (`*.glb`, `*.usdz`, `*.npz`), textures, and the folders `web/hologram/source/`, `web/airbus/`, and `web/deagle/`.
- `.env`, `venv/`, `dataset/`, `dataset_aug/`, and local logs.

Without the FBX clips the app can still wake, but the hologram has no motion.

## Setup (Windows, Python 3.12)

Use Python 3.12. `requirements.txt` is a full `pip freeze` of one development environment, not a minimal install list. It includes heavy packages the application does not import, including `jax`. Install the packages the code actually imports:

`opencv-python`, `mediapipe`, `numpy`, `SpeechRecognition`, `PyAudio`, `vosk`, `sounddevice`, `comtypes`, `piper-tts`, `faster-whisper`, `sympy`, `rapidocr-onnxruntime`, `pillow`, `mss`, `websockets`, `ufbx`.

```bat
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -U pip
venv\Scripts\python.exe -m pip install opencv-python mediapipe numpy SpeechRecognition PyAudio vosk sounddevice comtypes piper-tts faster-whisper sympy rapidocr-onnxruntime pillow mss websockets ufbx
```

On Windows, `PyAudio` often needs a wheel built for Python 3.12. If a native import fails, install the Microsoft Visual C++ Redistributable.

`web/p5.min.js` is p5.js (LGPL-2.1). Keep it in the repository only together with its license notice.

## Speech models

The Vosk model is not vendored. Download `vosk-model-small-en-us-0.15` from [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models) and extract it so this folder exists:

`models/vosk-model-small-en-us-0.15`

It must contain `am/` and `graph/`. `app.py` loads that path.

Indonesian speech is optional. Place the Piper voice `id_ID-news_tts-medium.onnx` in `models/piper/`. On first use, `faster-whisper` downloads Whisper tiny into `models/whisper/`. Leave both out of git.

## Hermes and Ollama (optional)

Chat and “look at this” try Hermes at `http://127.0.0.1:8642` first, then Ollama at `http://127.0.0.1:11434`. `app.py` does not start the Hermes gateway. If both are down, the app keeps running and skips that sentence.

The spoken name is read from `.env`, which is not committed:

- `ASMAMIR_USER_FULL_NAME`
- `ASMAMIR_USER_NICKNAME`

When those are empty, the app uses `User` and `friend`. Optional SAPI pronunciation is `ASMAMIR_SAID_FULL`, `ASMAMIR_SAID_GIVEN`, `ASMAMIR_SAID_FAMILY`, and `ASMAMIR_SAID_NICK`. Point the microphone at a device with `ASMAMIR_MIC`.

## Run

```bat
venv\Scripts\python.exe app.py
```

Task Scheduler is optional and is not registered by this repository. You may point a logon task at `scripts/start_login.cmd` without administrator rights. The script uses the project folder above `scripts`. It checks Hermes at `http://127.0.0.1:8642/health`, starts the local gateway only when health is down and a launcher is present, then runs `scripts/start_dsh.cmd` (`ollama launch dsh` only if that process is not already running), then one `app.py`. It does not open a second camera window.

## Commands

1. **Wake.** Thumb-to-middle snap, or the spoken name Asmamir. A clap does not wake the app.
2. **Standby.** The hologram. The sit-up plays once and holds. A pinch plus the other index finger orbits the figure.
3. **Dance.** The word `dance`, or the same snap after wake, cycles rumba, salsa, then twerk. `stop dance` or `standby` plays the sit-up again. A snap while the anime board is up does not cycle dance.
4. **Anime.** `anime`, `stipple`, `stipple anime`, `stippled anime`, `stipple art`, or a transcript that is only `art`. Not `anime kamera`. The primary screen is captured and a left-button drag selects a rectangle. `web/anime_board.html` then shows that photo and holds. The heart and the colored dots start only after one thumb-to-middle snap, or when the whole transcript is `start`, `capture`, or `take screenshot`. A longer sentence that merely contains those words does not start it. The heart grows from the center to the edges over 10 seconds. A dot appears only when the heart reaches it. At 10 seconds the heart is gone and the color picture freezes. A new drag replaces the photo and holds again.
5. **Canvas.** Only when the whole phrase is `canvas`, `draw`, or `drawing`.
6. **YouTube.** `open youtube` opens the site. `play …` or `putar …` opens the first result.
7. **Fog.** Only the exact phrase `fog mirror`.
8. **Shutdown.** `shutdown`, `shut down`, `matikan`, or the `q` key.

The same process can also count fingers, read a page, apply camera filters, and open Airbus, Desert Eagle, dragon, and a hand cursor.

## License

Code written for this project is MIT. Mixamo FBX files, 3D models, textures, Vosk weights, the Piper voice, and Whisper weights stay under their own licenses and are not distributed from this repository.
