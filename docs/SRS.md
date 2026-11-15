# Software requirements

**Product:** Asmamir Computer Vision AI Assistant (`asmamir_comvi`)  
**Window title:** `Asmamir Computer Vision AI Assistant`  
**Spoken name:** Asmamir

This document records the behavior implemented in `app.py` and the modules it calls. Folder names in the repository are relative. Personal checkout paths are not part of the product.

## 1. Process

1. One `python -m app.py` (or `python app.py`) owns the camera, the microphone, and the OpenCV windows.
2. After launch there is no window until wake.
3. English recognition is local Vosk. A whole-phrase command is the entire transcript, not a longer sentence that merely contains the words.
4. Chat tries Hermes `POST` at `http://127.0.0.1:8642` first, then Ollama at `http://127.0.0.1:11434`. The Deepseek harness is not on that path.
5. On process exit the app stops Ollama (`ollama serve` and port 11434), Hermes (port 8642 and the gateway process), and `ollama launch dsh` (and port 3080 if something is listening). They are not left running after `app.py` exits.

## 2. Wake

1. One thumb-to-middle snap wakes the assistant.
2. The whole phrase `asmamir` wakes the assistant.
3. One clap does not wake the assistant.

## 3. Standby hologram

1. The figure is Mixamo Arissa, drawn smaller, face toward the camera.
2. The sit-up clip plays once, then holds.
3. A pinch plus the other index orbits the figure.
4. The whole phrase `twerk` plays `web/hologram/asmamir_dancing_twerk.fbx`.
5. The whole phrase `rumba` plays `web/hologram/asmamir_rumba_dancing.fbx`.
6. The whole phrase `salsa` plays `web/hologram/asmamir_salsa_dancing.fbx`.
7. The whole phrase `dance` cycles those three clips.
8. The whole phrase `stop dance`, or a transcript that is only `standby` or only `stand by` (either one repeated), returns to the sit-up.
9. The FBX files are not in git. Each operator supplies them.

## 4. Anime

1. The whole phrase `anime`, `stipple`, `stipple anime`, `stippled anime`, `stipple art`, or a transcript that is only `art` opens selection. A longer sentence does not.
2. The operator drags a rectangle on the captured screen. The still photo holds. The heart does not start on mouse release or on the pose already in frame.
3. The window titled `Anime camera` is shown only while that photo is waiting, or while `record snap` is recording. The window thread paints it. The voice thread does not destroy OpenCV windows.
4. The moment the 10 second fill starts, that window is hidden and destroyed. It stays closed through the freeze. It opens again only for a new waiting photo or a new recording.
5. The fill starts if the short sound matches a saved wav under `models/snaps/` with score at least 0.82. The score is logged.
6. The fill starts if the live thumb-to-middle series matches the saved motion: open near 1.3, then one step close to about 0.86, as in `snap-1.motion`. The score is logged. A finger that is already closed when it enters the frame does not match.
7. The fill starts if the whole transcript is `start`, `capture`, `start capture`, or `take screenshot`.
8. The heart grows from the center for 10 seconds. Resize during the fill does not clear the dots. After 10 seconds the color picture freezes.
9. The whole phrase `restart anime` closes the animation window and the Anime camera, then opens image selection again. It does not exit and does not stop at the sit-up.
10. The whole phrase `standby` (repeated still counts), `stop anime`, or `stop stipple art` closes the animation, the Anime camera, and any Edge window whose title contains `Anime stipple`, then returns to the sit-up. The app keeps running.

## 5. Record snap

1. The whole phrase `record snap` or `records snap` arms a recording. It is not sent to Hermes or Ollama.
2. The Anime camera opens immediately and stays up until the wav and the clip are saved, or until a few seconds pass with no snap. The window thread keeps painting. The files are written between frames.
3. Files are `models/snaps/snap-N.wav` and `snap-N.mp4`, gitignored, slots 1 through 5. When all five wavs exist, the next recording overwrites from snap-1 and the log names the number replaced.

## 6. YouTube finger cursor

1. The whole phrase `open youtube` opens the site and arms the index-finger cursor immediately. Arming does not wait for a window title that already contains YouTube.
2. The sit-up hologram window is hidden and left off the desktop. It is not returned to fullscreen on each frame, so it does not hide the mouse.
3. YouTube stays in front. The index finger moves the Windows cursor. A pinch clicks. Two fingers scroll. The Windows cursor is shown again after each frame.
4. Closing the YouTube window disarms that cursor and brings the sit-up figure back, unless the operator armed the cursor by voice (`mouse` or `kursor`) and has not said `stop mouse` or `stop kursor`.

## 7. Quit

From standby only, the whole phrase `shutdown`, `shut down`, `shutdown and quit`, `shut down and quit`, `quit`, `exit`, `goodbye`, or `good bye` exits the process and stops the companion processes in section 1.

From any other mode, including anime, dance, and asleep, the same phrase returns to the sit-up and leaves `app.py` running. A second saying from standby quits.

A longer sentence that merely contains those words does not quit.

## 8. Standalone animation folder

1. `animation/` is a separate package. `app.py` does not import it and no voice phrase starts it.
2. From the project folder, the dotted module form is `python -m animation.ascii_reveal`, `python -m animation.cosmic_bloom`, `python -m animation.neon_thread_heart`, and `python -m animation.aqua_mandala`.
3. `ascii_reveal` reads `--image` and writes an mp4. `--out` chooses the path. `--seconds` defaults to 9. The file is a cell reveal: a green trail, then the source pixels. Generated mp4 files are not part of the repository.
4. `cosmic_bloom` and `neon_thread_heart` open their own windows and block until the window closes. `aqua_mandala` does the same with an explicit turtle import.

## 9. Login script

`scripts/start_login.cmd` is not registered by this repository.

If an operator runs it:

1. If `http://127.0.0.1:8642/health` is down and `%LOCALAPPDATA%\hermes\gateway-service\Hermes_Gateway.vbs` exists, the script starts that launcher.
2. `scripts/start_dsh.ps1` runs `ollama launch dsh -y` only when that process is not already running. It does not bind port 3080.
3. If `app.py` is not already running, the script starts one hidden `app.py`.

`app.py` itself starts `ollama serve` when port 11434 is quiet. It only probes Hermes. It does not start the gateway.
