# Technical notes

**Product:** Asmamir Computer Vision AI Assistant (`asmamir_comvi`)  
**Window:** `Asmamir Computer Vision AI Assistant`  
**Requirements:** [SRS.md](SRS.md) and [PRD.md](PRD.md)

These notes describe the code that is in the repository. They do not record a personal checkout path.

## Layout

| Area | Where |
| --- | --- |
| Process, voice, anime camera, shutdown | `app.py` |
| Sit-up, dance files, preview motion | `web/hologram_dance.py` |
| Exit that also closes the stipple browser | `web/hologram_fbx.py` |
| Stipple page, 10 second fill | `web/anime_board.html` |
| Hermes and harness while the app runs | `app.py` (`ensure_hermes`, `ensure_deepseek_harness`, `ensure_ollama`, `_stop_chat_companions`) |
| Snap samples | `models/snaps/` (gitignored) |

`PRODUCT_NAME` is `Asmamir Computer Vision AI Assistant`. The spoken identity line uses that name. The operator’s name is read from `.env` and is not stored in the repository.

## Wake

The camera can open with no window so a thumb-to-middle snap can wake the process. The whole phrase `asmamir` does the same. A single clap is ignored.

## Standby and dance

The hologram is Mixamo Arissa, scaled down, facing the camera. `asmamir_situp_to_idle.fbx` plays once and holds. Pinch plus the other index orbits.

Dance names are whole phrases only:

| Phrase | File |
| --- | --- |
| `twerk` | `web/hologram/asmamir_dancing_twerk.fbx` |
| `rumba` | `web/hologram/asmamir_rumba_dancing.fbx` |
| `salsa` | `web/hologram/asmamir_salsa_dancing.fbx` |
| `dance` | cycles the three |

`stop dance` or standby returns to the sit-up. The FBX files are local and gitignored.

## Anime

Selection is the whole phrase `anime mode`. A bare `anime` does not open it.

After the drag, the still is held. `Anime camera` is an OpenCV window. It is created on the window thread and only while the photo is waiting or `record snap` is in progress. `cv2` calls from the voice thread are not used to close it, because that froze the window. When the fill starts, the window thread hides and destroys it and then only pumps messages until the freeze ends.

Fill triggers:

- Sound: 30 ms peak envelope at 16 kHz compared with `snap-*.wav` resampled from 44100 Hz. Threshold 0.82. The score is printed.
- Motion: thumb-to-middle distance like `snap-1.motion` (open near 1.3, then one step to about 0.86). A series that is already closed at the first sample does not match. The score is printed on each frame that sees a hand.
- Voice: whole phrase `start`, `capture`, `start capture`, or `take screenshot`.

`web/anime_board.html` reveals dots from the center for 10 seconds (`REVEAL_MS = 10000`). A resize after start does not clear the ink. The finished plate is held.

`restart anime` and `restart anime mode` set a flag that the window thread handles: close the board and the camera, clear the old selection, and open a new drag. They do not quit and do not go to the sit-up. `standby` and `standby mode`, including after the heart has finished, close the held picture, the Anime camera, and the p5 browser (window title `Anime stipple`, including the Edge InPrivate suffix, and the `anime-p5-profile` command line), then show the Arissa sit-up. The same close runs for `stop anime`, `stop stipple`, `stop stipple art`, `stop art`, and `berhenti anime`. The process keeps running.

## Record snap

`record snap` and `records snap` are kept before chat, even if another grammar rewrites the open text. The camera window opens at once. Audio is captured on the listener. The wav and the mp4 are written on the window thread, one piece at a time, so the window keeps answering. Slots are `snap-1` through `snap-5`. A marker `models/snaps/next.txt` advances the overwrite after all five wavs exist. The log line is `Replaced snap-N.`

## Standalone animation folder

`animation/` is a package with an empty `__init__.py`. It is meant to be shared on its own. The assistant does not import it, and no voice phrase starts these files. Hand bloom lives in `web/hand_bloom.py`.

From the project folder:

- `python .\animation\<file>.py`
- `python -m animation.<name>`

`ascii_reveal` requires `--image` and `--out`. `--seconds` defaults to 9. It writes a cell reveal: a green trail, then the source pixels. A comma or a filesystem path after `-m` is not a module name. Generated mp4 files are gitignored.

The other scripts open their own window: `aqua_mandala`, `botanical_lily`, `butterfly_curve`, `clover_art`, `cosmic_bloom`, `flower`, `make_a_wish`, `math_plate`, `neon_thread_heart`, `radar_scanner`, `rose_art`, and `spiderman_particles`. Closing a turtle window during `aqua_mandala`, `butterfly_curve`, `flower`, `math_plate`, or `neon_thread_heart` is caught and the process exits quietly.

## Hand bloom

The whole phrase `hand bloom mode` is kept before the anime grammar. `web/hand_bloom.py` draws red roses on the frame from the webcam `app.py` already opened. It does not open a second camera. Thumb tip to index tip sets the pinch distance. That distance grows a stem from each fingertip and, once the stem has grown, a red rose. The overlay prints Grow and Bloom. The mode hides the sit-up, anime, dance, YouTube, and canvas surfaces. `standby` and `standby mode` clear the mode and return to the sit-up. The process keeps running.

## YouTube finger cursor

The whole phrase `youtube mode` calls `expect_youtube()` before the browser title exists, so the pointer is armed on that phrase. `open youtube` does not. The standby loop then hides the sit-up window with `ShowWindow` and does not call the fullscreen hologram paint while that cursor is active. After `waitKey`, the Windows cursor is shown again. The index tip calls `SetCursorPos`. A pinch sends a left click. Two fingers send a wheel. When the scan no longer sees a visible YouTube title, and the short expect window has elapsed, the cursor disarms unless `mouse mode` armed it, and the sit-up window is shown again.

## Quit and standby grammar

Quit phrases are whole transcripts and exit only when standby is the only mode (sit-up visible, no vision mode, no anime page, no dance). Otherwise they return to standby.

Standby is recognized from the open transcript when every word is `standby`, or the words are only `stand` `by` repeated. A grammar rewrite that adds other words is discarded. The phrase is not sent to Hermes or Ollama.

## Companions

| Process | Role |
| --- | --- |
| Hermes `127.0.0.1:8642` | Started by `app.py` when health is down, through the local gateway launcher. |
| Deepseek harness | Started by `app.py` through `scripts/start_dsh.cmd` when port 3080 is closed. |
| Ollama `127.0.0.1:11434` | Started by `app.py` when the port is quiet. |
| Ollama `127.0.0.1:11434` | Second chat and look endpoint. `app.py` runs `ollama serve` if the port is quiet. |
| `ollama launch dsh` | Deepseek harness. Not the chat path. Port 3080 is not bound by the login script. |

`_stop_chat_companions` runs from `finish_shutdown` and from the hologram `atexit` path. It stops listeners on 11434, 8642, and 3080, and processes whose command line is `ollama serve`, `ollama launch dsh`, or the Hermes gateway. `finish_shutdown` still exits if that stop raises. Companions are not started at Windows logon. There is no Startup shortcut. `shutdown and quit` and the other whole-phrase quit lines are kept before any `mode` phrase. They exit only when the sit-up is showing, including after `standby mode`. From another mode they return to the sit-up.
