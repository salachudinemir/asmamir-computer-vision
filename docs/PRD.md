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
- The whole phrase `dance mode` cycles `web/hologram/asmamir_dancing_twerk.fbx`, `asmamir_rumba_dancing.fbx`, and `asmamir_salsa_dancing.fbx`. Bare `twerk`, `rumba`, `salsa`, and `dance` do not start a mode. `stop dance`, or a transcript that is only `standby` or `standby mode`, returns to the sit-up.

## Anime

Whole phrase only: `anime mode`. The primary screen is captured. A left-button drag selects a rectangle. The still photo holds.

The OpenCV window titled `Anime camera` appears only while that photo is waiting for a command, or while `record snap` is recording. It is destroyed on the same turn the fill starts and stays closed through the freeze.

The 10 second fill starts when any one of these is true:

- The sound matches a wav in `models/snaps/` with score at least 0.82.
- The hand moves like `snap-1.motion`: thumb open near 1.3, then one step close to about 0.86.
- The whole transcript is `start`, `capture`, `start capture`, or `take screenshot`.

A longer sentence that merely contains those words does not start the fill. A finger that is already closed when it enters the frame does not start it. Mouse release does not start it.

The heart grows from the center for 10 seconds. The finished color picture then freezes.

`restart anime` and `restart anime mode` (whole phrases) close the held picture and the Anime camera, then open image selection again. The app does not exit and does not stop at the sit-up.

`standby`, `standby mode`, `stop anime`, `stop stipple`, `stop stipple art`, `stop art`, and `berhenti anime` close the held picture, the Anime camera, and the Edge page whose title contains `Anime stipple`, including after the heart has finished, then show the Arissa sit-up. The app keeps running.

## YouTube finger cursor

The whole phrase `youtube mode` opens the site and arms the index-finger cursor immediately. `open youtube` does not. It does not wait for a window title that already contains YouTube. The sit-up hologram window is hidden and left off screen so it does not go fullscreen every frame and hide the mouse. YouTube stays in front. The index finger moves the Windows cursor, a pinch clicks, and two fingers scroll. The Windows cursor is shown again after each frame. Closing YouTube brings the sit-up figure back. A voice arm (`mouse mode`) stays on after YouTube closes until `stop mouse` or `stop kursor`.

## Record snap and shutdown

The whole phrase `record snap` or `records snap` saves `models/snaps/snap-N.wav` and `snap-N.mp4`. The folder is gitignored. There are five slots. When all five exist, the next recording overwrites from snap-1 and the log names the replaced number. The Anime camera stays up for the recording. This phrase is not sent to Hermes or Ollama.

A transcript that is only the word `standby`, repeated any number of times, or only `stand by` repeated, closes anime and returns to the sit-up. It is not rewritten and is not sent to chat.

From standby only, including after `standby mode`, the whole phrase `shutdown`, `shut down`, `shutdown and quit`, `shut down and quit`, `quit`, `exit`, `goodbye`, or `good bye` exits the process. A mode phrase does not replace one of these. From any other mode the same phrase returns to the sit-up and leaves the app running. Say it again from standby to quit. If stopping a companion fails, the process still exits.

## Hand bloom

The whole phrase `hand bloom mode` turns the mode on. `hand bloom` and `hand blossom` do not, and the phrase does not open anime. Red roses are drawn on the camera frame the assistant already uses. No second webcam is opened. A pinch grows a stem from each fingertip and opens a red rose. The picture shows Grow and Bloom. Anime, dance, YouTube, canvas, and the sit-up hologram are left so they do not cover that camera. `standby` and `standby mode` leave the mode and return to the sit-up. The app keeps running.

## Standalone animations

`animation/` is a shared set of standalone scripts. They are not voice modes. Hand bloom is the assistant mode described above. From the project folder, run `python .\animation\<file>.py` or `python -m animation.<name>` with a dotted module name. A Windows relative path after `-m` (such as `python -m .\animation\string_art.py`) is not a module name and fails. `ascii_reveal` requires `--image` and `--out` and writes an mp4. The other scripts each open their own window: `aqua_mandala`, `botanical_lily`, `butterfly_curve`, `clover_art`, `cosmic_bloom`, `flower`, `koi_fish`, `make_a_wish`, `math_plate`, `neon_thread_heart`, `radar_scanner`, `rose_art`, `spiderman_particles`, `stippling_art`, and `string_art`. Closing a turtle window while the drawing is still running exits quietly. Generated mp4 files and `animation/monalisa.jpg` stay out of git. `stippling_art` looks for that image beside the script. `koi_fish` is a pygame pond (`python animation/koi_fish.py`). Default is interactive procedural fish (click/tap call, Space scatter, ripples, swim-state variety, depth cues) with smooth FPS (F11 / `--fullscreen` for SCALED fullscreen). Optional MP4 overlay (`--overlay` or `O`) uses local `animation/assets/koi_fish_swimming_animated_overlay.mp4` (gitignored), keyed once into a Surface cache and played clock-synced; while overlay is on, procedural fish are hidden so the modes do not mix.

## Companions

Ollama on port 11434, Hermes on port 8642, and the Deepseek harness may run only while `python app.py` or `python -m app.py` is running. That process starts the Hermes gateway when health is down, runs `scripts/start_dsh.cmd` when port 3080 is closed, and starts `ollama serve` when port 11434 is quiet. Process exit stops listeners on 11434, 8642, and 3080, and stops `ollama serve`, `ollama launch dsh`, and the Hermes gateway. Windows logon does not start them. This repository does not install a Startup shortcut or a login task.

## Identity

The spoken name and the operator’s name come from `.env`, which is not committed. When those values are empty, the app uses `User` and `friend`.
