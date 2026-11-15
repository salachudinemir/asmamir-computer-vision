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
| Optional logon script | `scripts/start_login.cmd`, `scripts/start_login.ps1`, `scripts/start_dsh.ps1` |
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

Selection phrases are whole transcripts: `anime`, `stipple`, `stipple anime`, `stippled anime`, `stipple art`, or only `art`.

After the drag, the still is held. `Anime camera` is an OpenCV window. It is created on the window thread and only while the photo is waiting or `record snap` is in progress. `cv2` calls from the voice thread are not used to close it, because that froze the window. When the fill starts, the window thread hides and destroys it and then only pumps messages until the freeze ends.

Fill triggers:

- Sound: 30 ms peak envelope at 16 kHz compared with `snap-*.wav` resampled from 44100 Hz. Threshold 0.82. The score is printed.
- Motion: thumb-to-middle distance like `snap-1.motion` (open near 1.3, then one step to about 0.86). A series that is already closed at the first sample does not match. The score is printed on each frame that sees a hand.
- Voice: whole phrase `start`, `capture`, `start capture`, or `take screenshot`.

`web/anime_board.html` reveals dots from the center for 10 seconds (`REVEAL_MS = 10000`). A resize after start does not clear the ink. The finished plate is held.

`restart anime` sets a flag that the window thread handles: close the board and the camera, clear the old selection, and open a new drag. `standby`, `stop anime`, and `stop stipple art` close the p5 browser by window title (`Anime stipple`, including the Edge InPrivate suffix) and by the `anime-p5-profile` command line, then request the sit-up.

## Record snap

`record snap` and `records snap` are kept before chat, even if another grammar rewrites the open text. The camera window opens at once. Audio is captured on the listener. The wav and the mp4 are written on the window thread, one piece at a time, so the window keeps answering. Slots are `snap-1` through `snap-5`. A marker `models/snaps/next.txt` advances the overwrite after all five wavs exist. The log line is `Replaced snap-N.`

## Quit and standby grammar

Quit phrases are whole transcripts and exit only when standby is the only mode (sit-up visible, no vision mode, no anime page, no dance). Otherwise they return to standby.

Standby is recognized from the open transcript when every word is `standby`, or the words are only `stand` `by` repeated. A grammar rewrite that adds other words is discarded. The phrase is not sent to Hermes or Ollama.

## Companions

| Process | Role |
| --- | --- |
| Hermes `127.0.0.1:8642` | First chat and look endpoint. Not started by `app.py`. |
| Ollama `127.0.0.1:11434` | Second chat and look endpoint. `app.py` runs `ollama serve` if the port is quiet. |
| `ollama launch dsh` | Deepseek harness. Not the chat path. Port 3080 is not bound by the login script. |

`_stop_chat_companions` runs from `finish_shutdown` and from the hologram `atexit` path. It stops listeners on 11434, 8642, and 3080, and processes whose command line is `ollama serve`, `ollama launch dsh`, or the Hermes gateway.

The login script’s real order is Hermes health, then `start_dsh.ps1`, then one `app.py` if none is running. The repository does not install the scheduled task.
