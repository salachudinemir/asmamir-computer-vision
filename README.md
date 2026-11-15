# Asmamir Computer Vision AI Assistant

Asmamir Computer Vision AI Assistant is a Windows desktop application. One process, `app.py`, uses the webcam and microphone on this computer. After launch there is no window. Wake it with a thumb-to-middle finger snap, or by saying `asmamir`. The standby view is a hologram. Voice commands open the other modes. English speech recognition runs locally with Vosk.

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

## Hermes, Ollama, and the Deepseek harness

Chat and “look at this” try Hermes at `http://127.0.0.1:8642` first, then Ollama at `http://127.0.0.1:11434`. The Deepseek harness (`ollama launch dsh`) is not the chat path and does not bind port 3080.

`app.py` starts `ollama serve` when port 11434 is quiet. It does not start the Hermes gateway. `scripts/start_login.cmd` starts Hermes only when `http://127.0.0.1:8642/health` is down and `%LOCALAPPDATA%\hermes\gateway-service\Hermes_Gateway.vbs` exists, then starts the harness only when `ollama launch dsh` is not already running, then starts one `app.py` if none is running. This repository does not register a Windows login task.

Those three processes may run only while `python -m app.py` is running. Process exit stops listeners on ports 11434, 8642, and 3080, plus `ollama serve`, `ollama launch dsh`, and the Hermes gateway. If both chat endpoints are down, the app keeps running and skips that sentence.

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

1. **Wake.** One thumb-to-middle snap, or the whole phrase `asmamir`. One clap does nothing.
2. **Standby.** Mixamo Arissa, smaller, facing the camera. The sit-up plays once and holds. A pinch plus the other index finger orbits the figure. The whole phrases `twerk`, `rumba`, and `salsa` open `asmamir_dancing_twerk.fbx`, `asmamir_rumba_dancing.fbx`, and `asmamir_salsa_dancing.fbx`. The single word `dance` cycles those three. `stop dance` or a transcript that is only `standby` (repeated is still standby) returns to the sit-up.
3. **Anime.** Whole phrase only: `anime`, `stipple`, `stipple anime`, `stippled anime`, `stipple art`, or a transcript that is only `art`. Drag a rectangle. The still photo holds. The window titled `Anime camera` is visible only while that photo is waiting, or while `record snap` is recording. The 10 second fill starts on a sound match to `models/snaps/snap-*.wav` (score at least 0.82), or a motion like `snap-1.motion` (thumb open near 1.3, then one step down to about 0.86), or the whole phrase `start`, `capture`, `start capture`, or `take screenshot`. A longer sentence does not start it. A finger that is already closed when it enters the frame does not start it. The heart grows from the center for 10 seconds, then the color picture freezes. `restart anime` closes the held picture and opens selection again. `standby`, `stop anime`, and `stop stipple art` close the animation, the Anime camera, and the Edge page titled Anime stipple, then return to the sit-up. The app keeps running.
5. **Canvas.** Only when the whole phrase is `canvas`, `draw`, or `drawing`.
6. **YouTube.** `open youtube` opens the site. `play …` or `putar …` opens the first result.
7. **Fog.** Only the exact phrase `fog mirror`.
8. **Shutdown.** From standby only, the whole phrase `shutdown`, `shut down`, `shutdown and quit`, `shut down and quit`, `quit`, `exit`, `goodbye`, or `good bye` exits. From any other mode the same phrase returns to the sit-up and leaves the app running. Say it again from standby to quit. `record snap` saves `models/snaps/snap-N.wav` and `snap-N.mp4` (gitignored, five slots, then overwrite from snap-1). That phrase is not sent to chat. A transcript that is only `standby` is not sent to chat.

The same process can also count fingers, read a page, apply camera filters, and open Airbus, Desert Eagle, dragon, and a hand cursor.

## License

Code written for this project is MIT. Mixamo FBX files, 3D models, textures, Vosk weights, the Piper voice, and Whisper weights stay under their own licenses and are not distributed from this repository.
