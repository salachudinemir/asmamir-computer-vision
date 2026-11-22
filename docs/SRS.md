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
4. The whole phrase `dance mode` cycles those three clips. `twerk`, `rumba`, and `salsa` do not start a mode.
5. The whole phrase `stop dance`, or a transcript that is only `standby`, `stand by` (either one repeated), or `standby mode`, returns to the sit-up.
6. The FBX files are not in git. Each operator supplies them.

## 4. Anime

1. The whole phrase `anime mode` opens selection. A bare `anime`, or a longer sentence, does not.
2. The operator drags a rectangle on the captured screen. The still photo holds. The heart does not start on mouse release or on the pose already in frame.
3. The window titled `Anime camera` is shown only while that photo is waiting, or while `record snap` is recording. The window thread paints it. The voice thread does not destroy OpenCV windows.
4. The moment the 10 second fill starts, that window is hidden and destroyed. It stays closed through the freeze. It opens again only for a new waiting photo or a new recording.
5. The fill starts if the short sound matches a saved wav under `models/snaps/` with score at least 0.82. The score is logged.
6. The fill starts if the live thumb-to-middle series matches the saved motion: open near 1.3, then one step close to about 0.86, as in `snap-1.motion`. The score is logged. A finger that is already closed when it enters the frame does not match.
7. The fill starts if the whole transcript is `start`, `capture`, `start capture`, or `take screenshot`.
8. The heart grows from the center for 10 seconds. Resize during the fill does not clear the dots. After 10 seconds the color picture freezes.
9. The whole phrase `restart anime` or `restart anime mode` closes the held picture and the Anime camera, then opens image selection again. It does not exit and does not stop at the sit-up.
10. The whole phrase `standby`, `standby mode`, `stop anime`, `stop stipple`, `stop stipple art`, `stop art`, or `berhenti anime` closes the held picture, the Anime camera, and any Edge window whose title contains `Anime stipple`, including after the heart has finished, then shows the Arissa sit-up. The app keeps running.

## 5. Record snap

1. The whole phrase `record snap` or `records snap` arms a recording. It is not sent to Hermes or Ollama.
2. The Anime camera opens immediately and stays up until the wav and the clip are saved, or until a few seconds pass with no snap. The window thread keeps painting. The files are written between frames.
3. Files are `models/snaps/snap-N.wav` and `snap-N.mp4`, gitignored, slots 1 through 5. When all five wavs exist, the next recording overwrites from snap-1 and the log names the number replaced.

## 6. YouTube finger cursor

1. The whole phrase `youtube mode` opens the site and arms the index-finger cursor immediately. Arming does not wait for a window title that already contains YouTube. `open youtube` and a bare `youtube` do not.
2. The sit-up hologram window is hidden and left off the desktop. It is not returned to fullscreen on each frame, so it does not hide the mouse.
3. YouTube stays in front. The index finger moves the Windows cursor. A pinch clicks. Two fingers scroll. The Windows cursor is shown again after each frame.
4. Closing the YouTube window disarms that cursor and brings the sit-up figure back, unless the operator armed the cursor with `mouse mode` and has not said `stop mouse` or `stop kursor`. `standby` and `standby mode` also return to the sit-up.

## 7. Quit

From standby only, including after `standby mode`, the whole phrase `shutdown`, `shut down`, `shutdown and quit`, `shut down and quit`, `quit`, `exit`, `goodbye`, or `good bye` exits the process and stops the companion processes in section 1. A mode phrase does not replace one of these. If stopping a companion fails, the process still exits.

From any other mode, including anime, dance, and asleep, the same phrase returns to the sit-up and leaves `app.py` running. A second saying from standby quits.

A longer sentence that merely contains those words does not quit. A stale stipple flag does not count as another mode once the sit-up is showing.

## 8. Hand bloom

1. The whole phrase `hand bloom mode` turns the mode on. `hand bloom`, `hand blossom`, and a longer sentence do not. It does not open anime.
2. Flowers are drawn on the camera frame the assistant already captures. A second webcam is not opened.
3. The pinch distance between the thumb tip and the index tip grows a stem from each fingertip on the camera frame already captured. A wider pinch raises the grow value. A closer pinch raises the bloom value. When the stem has grown, a red rose is drawn at the tip. The frame shows Grow and Bloom.
4. Entering the mode leaves anime, dance, YouTube, canvas, and the sit-up hologram so they do not cover the camera. The camera window stays up while the mode is on.
5. `standby` and `standby mode` leave hand bloom and show the sit-up again. The app keeps running.
6. Shutdown and goodbye still quit only from standby.

## 9. Standalone animation folder

1. `animation/` is a separate package meant to be shared. `app.py` does not import it. No voice phrase starts these scripts. Hand bloom is the assistant mode in section 8, not a file in this folder.
2. From the project folder, either form works: `python .\animation\<file>.py` or `python -m animation.<name>` with a dotted module name. A comma or a Windows relative path after `-m` (for example `python -m .\animation\string_art.py`) is not a module name.
3. `animation/koi_fish.py` SHALL remain a standalone pygame script (not imported by `app.py`). It SHALL render `RealisticKoi` (full body/fins/barbels/soft 3D shadow, 32-segment follow-the-leader spine) on `create_pond_bed` (depth gradient + stones) with `draw_water_surface` (caustics + swaying lily/lotus). Left-click (button 1) SHALL spawn ripples, drop `FeedPellet` grains, and call `attract_to`; pellets SHALL be removed on koi contact or when life expires. Right-click (button 3) SHALL spawn a wider second ripple and SHALL NOT feed. Esc SHALL quit. Requires `pygame`.
3. `ascii_reveal` requires `--image` and `--out`. `--seconds` defaults to 9. It writes an mp4: a green trail, then the source pixels. Generated mp4 files are not part of the repository.
4. The other scripts open their own window: `aqua_mandala`, `botanical_lily`, `butterfly_curve`, `clover_art`, `cosmic_bloom`, `flower`, `make_a_wish`, `math_plate`, `neon_thread_heart`, `radar_scanner`, `rose_art`, `spiderman_particles`, `stippling_art`, and `string_art`.
5. Closing a turtle window while `aqua_mandala`, `butterfly_curve`, `flower`, `math_plate`, `neon_thread_heart`, or `string_art` is drawing ends the script quietly.

## 10. Companions

The operator starts the assistant by running `python app.py` or `python -m app.py`. Windows logon does not start it. This repository does not register a Startup shortcut or a login task.

1. If Hermes health at `http://127.0.0.1:8642/health` is down and the local `Hermes_Gateway.vbs` launcher exists, `app.py` starts that launcher.
2. If nothing is listening on port 3080, `app.py` runs `scripts/start_dsh.cmd`, which starts `ollama launch dsh` only when that process is not already running.
3. If port 11434 is quiet, `app.py` starts `ollama serve`.
4. On process exit the app stops listeners on 11434, 8642, and 3080, and stops `ollama serve`, `ollama launch dsh`, and the Hermes gateway.

## 11. CCTV speed tracker

`cctv/cctv_speed_tracker.py` is a standalone script. `app.py` does not import it. No voice phrase starts it.

### 11.1 Purpose and scope

Detect objects, track them with ByteTrack, and estimate speed via a Bird's-Eye View (BEV) homography on local traffic video or a network stream. Annotated video and a CSV speed log are optional outputs.

### 11.2 Operational environment

- OS: Windows 11 (PowerShell and a Python venv).
- Hardware: NVIDIA CUDA GPU (tested on NVIDIA GeForce RTX 3070 Laptop GPU).
- Software: Python 3.12 (venv), PyTorch with CUDA, ultralytics (YOLO), opencv-python (`cv2`), numpy.

### 11.3 Architecture

1. **GPU check (`main()`).** Requires `torch.cuda.is_available()`. Raises `RuntimeError` if CUDA is missing. Resolves `VIDEO_IN` from `sample_traffic.mp4` or `sample_traffic.mp4.mp4` beside the script; sets `VIDEO_OUT` and `LOG_CSV` under the same folder.
2. **Open and reconnect (`open_stream_with_retry()`).** Opens with `cv2.VideoCapture`, up to `MAX_RECONNECT_ATTEMPTS = 10` with `RECONNECT_DELAY_SEC = 2.0`, and RTSP over TCP (`OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp`). On mid-run disconnect, reconnects and clears `bev_history`, `speed_smooth`, `last_kph`, and `last_detections`.
3. **Detect and track.** `YOLO(MODEL_PATH).track(..., persist=True, tracker="bytetrack.yaml", device=0, half=True)` every `DETECT_EVERY_N_FRAMES = 3` frames at `IMGSZ = 512`. Classes: `0` Otoped/Person, `1` Bicycle, `2` Car, `3` Motorcycle, `5` Bus, `7` Truck.
4. **BEV speed.** Foot point `(cx, bottom_y)` must lie in `SRC_ROAD_L` or `SRC_ROAD_R`. Project with `HL` / `HR`. Distance over `STEP_FRAMES = 5` becomes km/h using `dt = 1.0 / fps`. Keep values in `(MIN_PLAUSIBLE_KPH, MAX_PLAUSIBLE_KPH)` = (2, 160), clamp step changes with `MAX_DELTA_KPH_PER_FRAME = 12.0`, smooth with `HISTORY_LEN = 25`.
5. **Display and export.** Color by speed thresholds `SPEED_GREEN = 60` and `SPEED_YELLOW = 100`; show km/h after `MIN_TRACK_FRAMES = 10`; optional ROI polygons; write `output_speed.mp4` when `SAVE_OUTPUT_VIDEO = True`; live preview capped at `PREVIEW_MAX_WIDTH = 1280` when `SHOW_LIVE_WINDOW = True`; write `speed_log.csv` at the end.

### 11.4 Configuration defaults

| Parameter | Default | Notes |
| --- | --- | --- |
| `MODEL_PATH` | `"yolov8m.pt"` | YOLOv8 weights (`yolov8s.pt` or `yolov8m.pt`). |
| `IMGSZ` | `512` | Inference input size. |
| `CONF_THRES` / `IOU_THRES` | `0.25` / `0.50` | Confidence and NMS IoU. |
| `DETECT_EVERY_N_FRAMES` | `3` | Detection/tracking stride. |
| `VEHICLE_CLASSES` | `{0, 1, 2, 3, 5, 7}` | COCO class IDs → display labels. |
| `LANE_WIDTH_M` | `3.50` | Lane width for calibration (m). |
| `NUM_LANES_LEFT` / `NUM_LANES_RIGHT` | `3` / `2` | → `ROAD_WIDTH_L_M = 10.5`, `ROAD_WIDTH_R_M = 7.0`. |
| `SRC_ROAD_L`, `SRC_ROAD_R` | 4×2 float32 arrays | Left/right road ROI polygons (sample 1920×1080). |
| `BEV_SCALE` / `VISIBLE_LENGTH_M` | `18` / `45` | px per metre and BEV length (m). |
| `MIN_TRACK_FRAMES` | `10` | Frames before km/h is shown. |
| `STEP_FRAMES` / `HISTORY_LEN` | `5` / `25` | Displacement sample and smoothing window. |
| `MAX_DELTA_KPH_PER_FRAME` | `12.0` | Max km/h change per update. |
| `MIN_PLAUSIBLE_KPH` / `MAX_PLAUSIBLE_KPH` | `2` / `160` | Valid speed range. |
| `SPEED_GREEN` / `SPEED_YELLOW` | `60` / `100` | Display color thresholds (km/h). |
| `MAX_RECONNECT_ATTEMPTS` / `RECONNECT_DELAY_SEC` | `10` / `2.0` | Stream open/retry. |
| `SHOW_LIVE_WINDOW` / `PREVIEW_MAX_WIDTH` | `True` / `1280` | Preview and max width. |
| `SHOW_BEV_POLYGONS` / `SAVE_OUTPUT_VIDEO` | `False` / `True` | ROI overlay and `output_speed.mp4`. |

### 11.5 Functional requirements

| ID | Requirement | Specification |
| --- | --- | --- |
| FR-01 | Load video source and auto-reconnect | Read a local file (fallback `sample_traffic.mp4` / `sample_traffic.mp4.mp4`) or RTSP/HLS with retry up to `MAX_RECONNECT_ATTEMPTS`. |
| FR-02 | Multi-object detect and track | Persistent ByteTrack for classes 0, 1, 2, 3, 5, 7. |
| FR-03 | Road ROI filter | Validate foot point `(cx, y2)` inside `SRC_ROAD_L` / `SRC_ROAD_R` before BEV. |
| FR-04 | Speed estimate and smoothing | km/h from BEV and `src_fps`; filter 2–160; `MAX_DELTA_KPH_PER_FRAME`; average over `HISTORY_LEN`. |
| FR-05 | Visual display and legend | Colors via `SPEED_GREEN` (60) / `SPEED_YELLOW` (100); labels after `MIN_TRACK_FRAMES`; speed bar; legend; optional ROI. |
| FR-06 | Live preview and stop | Resize preview if wider than `PREVIEW_MAX_WIDTH`; clean stop on `q` or KeyboardInterrupt. |
| FR-07 | Export video and CSV log | `output_speed.mp4` when `SAVE_OUTPUT_VIDEO`; `speed_log.csv` columns `track_id`, `class`, `frames_tracked`, `avg_kph`, `max_kph`. |

### 11.6 Non-functional requirements

| ID | Requirement | Specification |
| --- | --- | --- |
| NFR-01 | Performance and GPU | CUDA FP16 (`half=True`) is required; support detection stride and `IMGSZ`. |
| NFR-02 | Time consistency | Use the source `src_fps` (for example 50.0 on the sample clip). |
| NFR-03 | Reliability | `finally` releases capture, writer, and windows; clear history on reconnect. |
| NFR-04 | Configuration | Calibration is centralized (`LANE_WIDTH_M`, `NUM_LANES_*`, `BEV_SCALE`, `VISIBLE_LENGTH_M`, `SRC_ROAD_*`). |

### 11.7 Assumptions and limits

- The road is treated as flat in the homography plane; the CCTV camera is static.
- COCO has no separate otoped class; otoped is represented via `person` (class 0).
- Sample video, annotated mp4, CSV logs, and YOLO `.pt` weights are local artifacts and are not committed.
