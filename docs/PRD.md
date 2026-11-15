# Product requirements

**Product:** Asmamir Computer Vision AI Assistant (`asmamir_comvi`)  
**Window title:** Asmamir Computer Vision AI Assistant  
**Spoken name:** Asmamir

## Purpose

One local Windows process, `app.py`, uses the webcam and the microphone. After launch there is no window. The operator wakes it, then uses voice and hand gestures for a standby hologram, dance clips, an anime stipple board, and the other vision modes.

Chat is Hermes at `http://127.0.0.1:8642`, then Ollama at `http://127.0.0.1:11434`. The Deepseek harness (`ollama launch dsh`) is not the chat path.

## Wake and standby

- Wake with one thumb-to-middle snap, or the whole phrase `asmamir`. One clap does nothing.
- Standby shows Mixamo Arissa, smaller, face toward the camera. The sit-up plays once, then holds.
- A pinch plus the other index orbits the figure.
- Whole-phrase dance names open one file: `twerk` → `web/hologram/asmamir_dancing_twerk.fbx`, `rumba` → `asmamir_rumba_dancing.fbx`, `salsa` → `asmamir_salsa_dancing.fbx`. The single word `dance` cycles those three. `stop dance`, or a transcript that is only `standby` (one or more times), returns to the sit-up.

## Anime

Whole phrase only: `anime`, `stipple`, `stipple anime`, `stippled anime`, `stipple art`, or a transcript that is only `art`. The primary screen is captured. A left-button drag selects a rectangle. The still photo holds.

The OpenCV window titled `Anime camera` appears only while that photo is waiting for a command, or while `record snap` is recording. It is destroyed on the same turn the fill starts and stays closed through the freeze.

The 10 second fill starts when any one of these is true:

- The sound matches a wav in `models/snaps/` with score at least 0.82.
- The hand moves like `snap-1.motion`: thumb open near 1.3, then one step close to about 0.86.
- The whole transcript is `start`, `capture`, `start capture`, or `take screenshot`.

A longer sentence that merely contains those words does not start the fill. A finger that is already closed when it enters the frame does not start it. Mouse release does not start it.

The heart grows from the center for 10 seconds. The finished color picture then freezes.

`restart anime` (whole phrase) closes the held picture and the Anime camera, then opens image selection again. The app does not exit and does not stop at the sit-up.

`standby`, `stop anime`, and `stop stipple art` close the animation, the Anime camera, and the Edge page whose title contains `Anime stipple`, then return to the sit-up. The app keeps running.

## YouTube finger cursor

The whole phrase `open youtube` opens the site and arms the index-finger cursor immediately. It does not wait for a window title that already contains YouTube. The sit-up hologram window is hidden and left off screen so it does not go fullscreen every frame and hide the mouse. YouTube stays in front. The index finger moves the Windows cursor, a pinch clicks, and two fingers scroll. The Windows cursor is shown again after each frame. Closing YouTube brings the sit-up figure back. A voice arm (`mouse` or `kursor`) stays on after YouTube closes until `stop mouse` or `stop kursor`.

## Record snap and shutdown

The whole phrase `record snap` or `records snap` saves `models/snaps/snap-N.wav` and `snap-N.mp4`. The folder is gitignored. There are five slots. When all five exist, the next recording overwrites from snap-1 and the log names the replaced number. The Anime camera stays up for the recording. This phrase is not sent to Hermes or Ollama.

A transcript that is only the word `standby`, repeated any number of times, or only `stand by` repeated, closes anime and returns to the sit-up. It is not rewritten and is not sent to chat.

From standby only, the whole phrase `shutdown`, `shut down`, `shutdown and quit`, `shut down and quit`, `quit`, `exit`, `goodbye`, or `good bye` exits the process. From any other mode the same phrase returns to the sit-up and leaves the app running. Say it again from standby to quit.

## Standalone animations

`animation/` is not a voice mode. It runs on its own, from the project folder: `python -m animation.ascii_reveal`, `python -m animation.cosmic_bloom`, `python -m animation.neon_thread_heart`, and `python -m animation.aqua_mandala`. `ascii_reveal` needs `--image` and writes an mp4 (`--out` sets the path). The other three open a window and wait until it is closed. Generated video files stay out of git.

## Companions

Ollama on port 11434, Hermes on port 8642, and `ollama launch dsh` may run only while `python -m app.py` is running. `app.py` starts `ollama serve` when port 11434 is quiet. It does not start the Hermes gateway. Process exit stops listeners on 11434, 8642, and 3080, and stops `ollama serve`, `ollama launch dsh`, and the Hermes gateway.

`scripts/start_login.cmd` is optional. This repository does not register a Windows login task. If an operator points a logon task at that script, the script checks Hermes health, starts the local gateway only when health is down and `Hermes_Gateway.vbs` is present, runs `scripts/start_dsh.ps1` only when `ollama launch dsh` is not already running, then starts one `app.py` if none is running. Port 3080 is not bound.

## Identity

The spoken name and the operator’s name come from `.env`, which is not committed. When those values are empty, the app uses `User` and `friend`.
