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

Chat and “look at this” try Hermes at `http://127.0.0.1:8642` first, then Ollama at `http://127.0.0.1:11434`. The Deepseek harness (`ollama launch dsh`) is not the chat path.

`python app.py` or `python -m app.py` starts the Hermes gateway when health is down, runs `scripts/start_dsh.cmd` when port 3080 is closed, and starts `ollama serve` when port 11434 is quiet. Each one is left alone when it is already up. Windows logon does not start them. This repository does not install a Startup shortcut or a login task.

Those processes run only while the app is running. Process exit stops listeners on ports 11434, 8642, and 3080, plus `ollama serve`, `ollama launch dsh`, and the Hermes gateway. If both chat endpoints are down, the app keeps running and skips that sentence.

The spoken name is read from `.env`, which is not committed:

- `ASMAMIR_USER_FULL_NAME`
- `ASMAMIR_USER_NICKNAME`

When those are empty, the app uses `User` and `friend`. Optional SAPI pronunciation is `ASMAMIR_SAID_FULL`, `ASMAMIR_SAID_GIVEN`, `ASMAMIR_SAID_FAMILY`, and `ASMAMIR_SAID_NICK`. Point the microphone at a device with `ASMAMIR_MIC`.

## Run

```bat
venv\Scripts\python.exe app.py
```

Start the assistant only by running that command. A reboot does not start it. The process starts Hermes, the Deepseek harness, and Ollama in the background when they are down, and stops them when it exits. It does not open a second camera window.

## Commands

1. **Wake.** One thumb-to-middle snap, or the whole phrase `asmamir`. One clap does nothing.
2. **Standby.** Mixamo Arissa, smaller, facing the camera. The sit-up plays once and holds. A pinch plus the other index finger orbits the figure. The whole phrase `dance mode` cycles `asmamir_dancing_twerk.fbx`, `asmamir_rumba_dancing.fbx`, and `asmamir_salsa_dancing.fbx`. Bare `twerk`, `rumba`, `salsa`, and `dance` do not. `stop dance`, `standby`, or `standby mode` returns to the sit-up.
3. **Anime.** Whole phrase only: `anime mode`. Drag a rectangle. The still photo holds. The window titled `Anime camera` is visible only while that photo is waiting, or while `record snap` is recording. The 10 second fill starts on a sound match to `models/snaps/snap-*.wav` (score at least 0.82), or a motion like `snap-1.motion` (thumb open near 1.3, then one step down to about 0.86), or the whole phrase `start`, `capture`, `start capture`, or `take screenshot`. A longer sentence does not start it. A finger that is already closed when it enters the frame does not start it. The heart grows from the center for 10 seconds, then the color picture freezes. `restart anime` and `restart anime mode` close the held picture and open selection again. They do not quit and do not go to the sit-up. `standby` and `standby mode`, including after the heart has finished, close the held picture, the Anime camera, and the Edge page titled Anime stipple, then show the Arissa sit-up. The same close runs for `stop anime`, `stop stipple`, `stop stipple art`, `stop art`, and `berhenti anime`. The app keeps running.
4. **Hand bloom.** Whole phrase `hand bloom mode`. Red roses are drawn on the existing camera frame. `standby` or `standby mode` returns to the sit-up.
5. **Other modes.** Whole phrase only: `canvas mode`, `fog mirror mode`, `filter mode`, `airbus mode`, `deagle mode`, `dragon mode`, `count mode`, `fruit mode`, `mouse mode`.
6. **YouTube.** `youtube mode` opens the site and arms the index-finger cursor immediately, without waiting for a window title that already contains YouTube. `open youtube` does not. The sit-up hologram is hidden and left off screen so it does not go fullscreen every frame and hide the mouse. YouTube stays in front. The index finger moves the Windows cursor, a pinch clicks, and two fingers scroll. The Windows cursor is shown again after each frame. Closing YouTube brings the sit-up figure back. `play …` or `putar …` opens the first result.
7. **Apps.** Whole phrases that already open Excel, the browser, WeChat, and WhatsApp stay as they are.
8. **Shutdown.** From standby only, including after `standby mode`, the whole phrase `shutdown`, `shut down`, `shutdown and quit`, `shut down and quit`, `quit`, `exit`, `goodbye`, or `good bye` exits. A mode phrase does not replace one of these. From any other mode the same phrase returns to the sit-up and leaves the app running. Say it again from standby to quit. `record snap` saves `models/snaps/snap-N.wav` and `snap-N.mp4` (gitignored, five slots, then overwrite from snap-1). That phrase is not sent to chat. A transcript that is only `standby` is not sent to chat.

The same process can also count fingers, read a page, apply camera filters, and open Airbus, Desert Eagle, dragon, and a hand cursor.

## Standalone animations

`animation/` is not started by a voice command. From the project folder, use dotted module names with `-m` (`python -m animation.string_art`) or run the file path (`python .\animation\string_art.py`). Do not pass a Windows relative path to `-m` (for example `python -m .\animation\string_art.py` fails). The shareable scripts are `aqua_mandala`, `ascii_reveal`, `botanical_lily`, `butterfly_curve`, `clover_art`, `cosmic_bloom`, `flower`, `koi_fish`, `make_a_wish`, `math_plate`, `neon_thread_heart`, `radar_scanner`, `rose_art`, `spiderman_particles`, `stippling_art`, and `string_art`.

```bat
python -m animation.ascii_reveal --image path\to\image.jpg --out animation\reveal.mp4
python -m animation.string_art
python -m animation.stippling_art
python animation\koi_fish.py
```

`ascii_reveal` writes an mp4. The others open a window. `stippling_art` expects a local `monalisa.jpg` next to the script, and that image is not committed. Generated mp4 files are not committed.

`animation/koi_fish.py` is a standalone pygame koi pond. Default is interactive procedural `RealisticKoi` (click/tap call, Space scatter, ripples, swim states, depth; nagomi-inspired; original pygame). Smooth 60 FPS with `F11` / `--fullscreen` (SCALED + vsync when available). Optional keyed MP4 overlay (`--overlay` or `O`) uses `animation/assets/koi_fish_swimming_animated_overlay.mp4` (gitignored; provide locally) — OpenCV keys frames once into a Surface cache and plays them clock-synced. When overlay is on, procedural fish are hidden (no mix); `O` toggles back to interactive. Esc quits. Requires `pygame` (+ `opencv-python` only if you use the overlay).

## License

Code written for this project is MIT. Mixamo FBX files, 3D models, textures, Vosk weights, the Piper voice, and Whisper weights stay under their own licenses and are not distributed from this repository.
