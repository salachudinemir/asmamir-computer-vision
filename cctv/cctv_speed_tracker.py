import csv
import math
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

# Paksa transport RTSP via TCP untuk menghindari masalah SETUP/UDP pada beberapa stream
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2
import numpy as np
import torch
from ultralytics import YOLO  # type: ignore[import-not-found]

BASE_DIR = Path(__file__).resolve().parent
candidate_mp4 = BASE_DIR / "sample_traffic.mp4"
candidate_double = BASE_DIR / "sample_traffic.mp4.mp4"

if candidate_mp4.exists():
    VIDEO_IN = str(candidate_mp4)
elif candidate_double.exists():
    VIDEO_IN = str(candidate_double)
else:
    VIDEO_IN = str(candidate_mp4)

VIDEO_OUT = str(BASE_DIR / "output_speed.mp4")
LOG_CSV = str(BASE_DIR / "speed_log.csv")

# Pengaturan auto-reconnect, live preview & output
MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_DELAY_SEC = 2.0
SHOW_LIVE_WINDOW = True
PREVIEW_MAX_WIDTH = 1280
SHOW_BEV_POLYGONS = False
SAVE_OUTPUT_VIDEO = True
DETECT_EVERY_N_FRAMES = 3

# Pengaturan model & GPU inferensi (weights live under repo models/, gitignored)
MODEL_PATH = str(BASE_DIR.parent / "models" / "yolov8m.pt")
IMGSZ = 512
CONF_THRES = 0.25
IOU_THRES = 0.50

VEHICLE_CLASSES = {
    0: "Otoped/Person",
    1: "Bicycle",
    2: "Car",
    3: "Motorcycle",
    5: "Bus",
    7: "Truck",
}

# Kalibrasi lebar jalan & perspektif untuk sample_traffic.mp4 (1920x1080)
LANE_WIDTH_M = 3.50
NUM_LANES_LEFT = 3
NUM_LANES_RIGHT = 2
ROAD_WIDTH_L_M = LANE_WIDTH_M * NUM_LANES_LEFT   # 10.5 m
ROAD_WIDTH_R_M = LANE_WIDTH_M * NUM_LANES_RIGHT  # 7.0 m

BEV_SCALE = 18
VISIBLE_LENGTH_M = 45

SRC_ROAD_L = np.array([
    [825, 415],    # far-left
    [970, 415],    # far-right
    [1280, 1079],  # near-right
    [560, 1079],   # near-left
], dtype=np.float32)

SRC_ROAD_R = np.array([
    [1045, 360],   # far-left
    [1165, 360],   # far-right
    [1460, 740],   # near-right
    [1230, 740],   # near-left
], dtype=np.float32)

MIN_TRACK_FRAMES = 10
STEP_FRAMES = 5
HISTORY_LEN = 25
MAX_DELTA_KPH_PER_FRAME = 12.0
MAX_PLAUSIBLE_KPH = 160
MIN_PLAUSIBLE_KPH = 2

SPEED_GREEN = 60
SPEED_YELLOW = 100


def to_numpy_array(data: Any, dtype: Any = None) -> np.ndarray:
    """Konversi tensor PyTorch atau array/list menjadi np.ndarray secara aman."""
    if hasattr(data, "detach"):
        data = data.detach()
    if hasattr(data, "cpu"):
        data = data.cpu()
    if hasattr(data, "numpy"):
        data = data.numpy()
    arr = np.asarray(data)
    return arr.astype(dtype) if dtype is not None else arr


def build_bev_transform(src_pts: np.ndarray, road_width_m: float, visible_len_m: float, scale: float):
    """Return (H, H_inv, bev_w, bev_h) for a perspective -> bird's-eye warp."""
    bev_w = int(road_width_m * scale)
    bev_h = int(visible_len_m * scale)
    dst = np.array([
        [0, 0],
        [bev_w, 0],
        [bev_w, bev_h],
        [0, bev_h],
    ], dtype=np.float32)
    cv2_any: Any = cv2
    H = cv2_any.getPerspectiveTransform(src_pts, dst)
    H_inv = cv2_any.getPerspectiveTransform(dst, src_pts)
    return H, H_inv, bev_w, bev_h


def to_bev(H: np.ndarray, pt: tuple[float, float]) -> tuple[float, float]:
    """Transform a single (x, y) image point to bird's-eye coordinates."""
    p = np.array([[[pt[0], pt[1]]]], dtype=np.float32)
    cv2_any: Any = cv2
    t = cv2_any.perspectiveTransform(p, H)
    return float(t[0][0][0]), float(t[0][0][1])


def is_point_in_polygon(poly: np.ndarray, pt: tuple[float, float]) -> bool:
    """Cek apakah titik (x, y) berada di dalam atau pada garis poligon."""
    cv2_any: Any = cv2
    contour = poly.astype(np.float32).reshape((-1, 1, 2))
    return float(cv2_any.pointPolygonTest(contour, (float(pt[0]), float(pt[1])), False)) >= 0.0


def bev_dist_to_metres(dx_px: float, dy_px: float, scale: float) -> float:
    return math.hypot(dx_px, dy_px) / scale


def speed_color(kph: float) -> tuple[int, int, int]:
    if kph < SPEED_GREEN:
        return (0, 220, 0)     # green
    elif kph < SPEED_YELLOW:
        return (0, 180, 255)   # yellow-orange
    else:
        return (0, 50, 255)    # red


def draw_label(
    frame: np.ndarray,
    text: str,
    pos: tuple[float, float],
    color: tuple[int, int, int],
    font_scale: float = 0.6,
    thickness: int = 2,
) -> None:
    """Draw a filled-background label on the frame."""
    x, y = int(pos[0]), int(pos[1])
    (tw, th), baseline = cv2.getTextSize(
        text, cv2.FONT_HERSHEY_DUPLEX, font_scale, thickness
    )
    pad = 4
    cv2.rectangle(
        frame,
        (x - pad, y - th - pad),
        (x + tw + pad, y + baseline + pad),
        (20, 20, 20),
        -1,
    )
    cv2.putText(
        frame,
        text,
        (x, y),
        cv2.FONT_HERSHEY_DUPLEX,
        font_scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def draw_bev_guides(frame: np.ndarray) -> None:
    """Gambar garis poligon kalibrasi jalan agar mudah dicek secara visual."""
    pts_l = SRC_ROAD_L.astype(np.int32).reshape((-1, 1, 2))
    pts_r = SRC_ROAD_R.astype(np.int32).reshape((-1, 1, 2))
    cv2.polylines(frame, [pts_l], isClosed=True, color=(255, 200, 0), thickness=2)
    cv2.polylines(frame, [pts_r], isClosed=True, color=(255, 120, 255), thickness=2)


def open_stream_with_retry(source_url: str, max_attempts: int = 10, delay_sec: float = 2.0):
    """Membuka video/stream dengan percobaan ulang otomatis jika gagal."""
    attempt = 0
    while attempt < max_attempts:
        cap = cv2.VideoCapture(source_url)
        if cap.isOpened():
            ret, test_frame = cap.read()
            if ret and test_frame is not None:
                return cap, test_frame
            cap.release()

        attempt += 1
        print(
            f"[Reconnect] Gagal membuka stream (percobaan {attempt}/{max_attempts}). "
            f"Menunggu {delay_sec} detik..."
        )
        time.sleep(delay_sec)

    return None, None


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA GPU tidak terdeteksi oleh PyTorch di venv ini! "
            "Install PyTorch versi CUDA terlebih dahulu sebelum menjalankan mode GPU."
        )

    cap, first_frame = open_stream_with_retry(
        VIDEO_IN,
        max_attempts=MAX_RECONNECT_ATTEMPTS,
        delay_sec=RECONNECT_DELAY_SEC,
    )
    if cap is None or first_frame is None:
        if cap is not None:
            cap.release()
        raise ConnectionError(
            f"Tidak dapat terhubung ke stream '{VIDEO_IN}' setelah {MAX_RECONNECT_ATTEMPTS} percobaan."
        )

    raw_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    fps = raw_fps if 1.0 <= raw_fps <= 120.0 else 25.0
    height, width = first_frame.shape[:2]
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    is_live_stream = total <= 0
    gpu_name = torch.cuda.get_device_name(0)

    print(
        f"Stream aktif: {width}x{height} @ {fps:.1f} fps | "
        f"Mode: {'Live Stream' if is_live_stream else f'{total} frames'} | "
        f"Device: GPU [{gpu_name}] (FP16) | imgsz={IMGSZ} | stride={DETECT_EVERY_N_FRAMES}"
    )

    out = None
    if SAVE_OUTPUT_VIDEO:
        cv2_any: Any = cv2
        fourcc = cv2_any.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(VIDEO_OUT, fourcc, fps, (width, height))

    HL, _, _, _ = build_bev_transform(
        SRC_ROAD_L, ROAD_WIDTH_L_M, VISIBLE_LENGTH_M, BEV_SCALE
    )
    HR, _, _, _ = build_bev_transform(
        SRC_ROAD_R, ROAD_WIDTH_R_M, VISIBLE_LENGTH_M, BEV_SCALE
    )

    model = YOLO(MODEL_PATH)
    print(f"Model loaded: {MODEL_PATH}")

    bev_history: defaultdict[int, deque[tuple[float, float, int]]] = defaultdict(
        lambda: deque(maxlen=HISTORY_LEN)
    )
    speed_smooth: defaultdict[int, deque[float]] = defaultdict(
        lambda: deque(maxlen=HISTORY_LEN)
    )
    last_kph: dict[int, float] = {}
    track_frames: defaultdict[int, int] = defaultdict(int)
    track_class: dict[int, str] = {}
    track_max_kph: defaultdict[int, float] = defaultdict(float)
    track_kph_sum: defaultdict[int, float] = defaultdict(float)
    track_kph_cnt: defaultdict[int, int] = defaultdict(int)

    last_detections: list[tuple[np.ndarray, int, int, float | None]] = []

    frame_idx = 0
    dt = 1.0 / fps
    pending_frame: np.ndarray | None = first_frame
    proc_start = time.perf_counter()

    print("Processing frames... Tekan 'q' pada jendela preview untuk berhenti.")
    try:
        while True:
            if pending_frame is not None:
                ret, frame = True, pending_frame
                pending_frame = None
            else:
                ret, frame = cap.read()

            if not ret or frame is None:
                print("\n[Warning] Stream terputus atau frame kosong. Mencoba auto-reconnect...")
                if cap is not None:
                    cap.release()
                cap, pending_frame = open_stream_with_retry(
                    VIDEO_IN,
                    max_attempts=MAX_RECONNECT_ATTEMPTS,
                    delay_sec=RECONNECT_DELAY_SEC,
                )
                if cap is None or pending_frame is None:
                    if cap is not None:
                        cap.release()
                    print("[Error] Auto-reconnect gagal. Menghentikan pemrosesan.")
                    break

                bev_history.clear()
                speed_smooth.clear()
                last_kph.clear()
                last_detections.clear()
                print("[Info] Berhasil tersambung kembali ke stream.")
                continue

            frame_idx += 1
            if frame_idx % 30 == 0:
                elapsed = max(time.perf_counter() - proc_start, 1e-6)
                proc_fps = frame_idx / elapsed
                if not is_live_stream and total > 0:
                    pct = frame_idx / total * 100
                    print(f"  {frame_idx}/{total} frames ({pct:.0f}%) | {proc_fps:.1f} proc fps")
                else:
                    print(f"  Processed {frame_idx} frames ({proc_fps:.1f} proc fps)...")

            run_detect = ((frame_idx - 1) % max(1, DETECT_EVERY_N_FRAMES) == 0)
            if run_detect:
                results = model.track(
                    frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    classes=list(VEHICLE_CLASSES.keys()),
                    imgsz=IMGSZ,
                    conf=CONF_THRES,
                    iou=IOU_THRES,
                    device=0,
                    half=True,
                    verbose=False,
                )

                results_list = list(results)
                res0 = results_list[0] if results_list else None
                current_detections: list[tuple[np.ndarray, int, int, float | None]] = []

                if res0 is not None and res0.boxes is not None and res0.boxes.id is not None:
                    boxes = to_numpy_array(res0.boxes.xyxy)
                    ids = to_numpy_array(res0.boxes.id, dtype=int)
                    cls = to_numpy_array(res0.boxes.cls, dtype=int)

                    for box, tid, cls_id in zip(boxes, ids, cls):
                        tid = int(tid)
                        cls_id = int(cls_id)
                        cls_name = VEHICLE_CLASSES.get(cls_id, "Vehicle")
                        track_class[tid] = cls_name
                        track_frames[tid] += 1

                        x1, y1, x2, y2 = box
                        cx = float((x1 + x2) / 2.0)
                        bottom_y = float(y2)
                        foot_pt = (cx, bottom_y)

                        in_left = is_point_in_polygon(SRC_ROAD_L, foot_pt)
                        in_right = is_point_in_polygon(SRC_ROAD_R, foot_pt)

                        kph: float | None = last_kph.get(tid)
                        if in_left or in_right:
                            H_use = HL if in_left else HR
                            scale_use = float(BEV_SCALE)

                            bx, by = to_bev(H_use, foot_pt)
                            bev_history[tid].append((bx, by, frame_idx))

                            hist = bev_history[tid]
                            if len(hist) >= 2:
                                ref_idx = max(0, len(hist) - 1 - STEP_FRAMES)
                                bx0, by0, f10 = hist[ref_idx]
                                bx1, by1, f11 = hist[-1]
                                n_frames = f11 - f10
                                if n_frames > 0:
                                    dist_m = bev_dist_to_metres(bx1 - bx0, by1 - by0, scale_use)
                                    elapsed_s = n_frames * dt
                                    raw_kph = (dist_m / elapsed_s) * 3.6

                                    if MIN_PLAUSIBLE_KPH < raw_kph < MAX_PLAUSIBLE_KPH:
                                        prev = last_kph.get(tid)
                                        if prev is not None:
                                            diff = raw_kph - prev
                                            if abs(diff) > MAX_DELTA_KPH_PER_FRAME:
                                                raw_kph = prev + math.copysign(MAX_DELTA_KPH_PER_FRAME, diff)

                                        speed_smooth[tid].append(raw_kph)
                                        kph = float(np.mean(speed_smooth[tid]))
                                        last_kph[tid] = kph
                                        track_kph_sum[tid] += kph
                                        track_kph_cnt[tid] += 1
                                        track_max_kph[tid] = max(track_max_kph[tid], kph)

                        current_detections.append((np.asarray(box), tid, cls_id, kph))

                last_detections = current_detections

            for box, tid, cls_id, kph in last_detections:
                x1, y1, x2, y2 = box
                cls_name = track_class.get(tid, VEHICLE_CLASSES.get(cls_id, "Vehicle"))
                show_speed = (kph is not None and track_frames[tid] >= MIN_TRACK_FRAMES)
                color = speed_color(kph) if (show_speed and kph is not None) else (180, 180, 180)

                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)

                if show_speed and kph is not None:
                    label = f"{cls_name} ({kph:.0f} km/h)"
                else:
                    label = cls_name

                draw_label(frame, label, (float(x1), float(y1) - 6.0), color)

                if show_speed and kph is not None:
                    bar_max = float(SPEED_YELLOW)
                    bar_frac = min(kph / bar_max, 1.0)
                    bar_len = int((x2 - x1) * bar_frac)
                    bar_y = int(y2) + 4
                    cv2.rectangle(
                        frame,
                        (int(x1), bar_y),
                        (int(x1) + bar_len, bar_y + 5),
                        color,
                        -1,
                    )

            if SHOW_BEV_POLYGONS:
                draw_bev_guides(frame)

            for i, (label, colour) in enumerate([
                ("< 60 km/h", (0, 220, 0)),
                ("60-100 km/h", (0, 200, 255)),
                ("> 100 km/h", (0, 50, 255)),
            ]):
                y_leg = height - 80 + i * 26
                cv2.rectangle(frame, (12, y_leg - 14), (32, y_leg + 4), colour, -1)
                cv2.putText(
                    frame,
                    label,
                    (40, y_leg),
                    cv2.FONT_HERSHEY_DUPLEX,
                    0.55,
                    (230, 230, 230),
                    1,
                    cv2.LINE_AA,
                )

            if out is not None:
                out.write(frame)

            if SHOW_LIVE_WINDOW:
                if width > PREVIEW_MAX_WIDTH:
                    scale_ratio = PREVIEW_MAX_WIDTH / float(width)
                    preview_h = int(height * scale_ratio)
                    preview_frame = cv2.resize(frame, (PREVIEW_MAX_WIDTH, preview_h))
                else:
                    preview_frame = frame

                cv2.imshow("YOLOv8 CCTV Speed Tracker", preview_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("\nDihentikan oleh pengguna (tombol 'q').")
                    break
    except KeyboardInterrupt:
        print("\nDihentikan oleh pengguna (Ctrl+C).")
    finally:
        if cap is not None:
            cap.release()
        if out is not None:
            out.release()
        if SHOW_LIVE_WINDOW:
            cv2.destroyAllWindows()

    if SAVE_OUTPUT_VIDEO:
        print(f"Done! Output saved = {VIDEO_OUT}")

    with open(LOG_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["track_id", "class", "frames_tracked", "avg_kph", "max_kph"])
        for tid in sorted(track_frames):
            if track_kph_cnt[tid] == 0:
                continue
            avg_kph = track_kph_sum[tid] / track_kph_cnt[tid]
            writer.writerow([
                tid,
                track_class.get(tid, "Unknown"),
                track_frames[tid],
                round(avg_kph, 1),
                round(track_max_kph[tid], 1),
            ])
    print(f"Speed log saved = {LOG_CSV}")


if __name__ == "__main__":
    main()