"""Build a fruit gallery from folders of your own photos.

Put at least 20 photos in each class folder, taken near the webcam:

    dataset/durian/photo1.jpg
    dataset/apple/photo1.jpg
    dataset/other/desk.jpg

The folder name is the name Asmamir will speak. Then run:

    venv\\Scripts\\python train_fruits.py
"""

import cv2
import mediapipe as mp
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "dataset"
EMBEDDER_MODEL = ROOT / "models" / "mobilenet_v3_small.tflite"
GALLERY = ROOT / "models" / "fruit_gallery.npz"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def embedder():
    options = mp.tasks.vision.ImageEmbedderOptions(
        base_options=mp.tasks.BaseOptions(model_asset_buffer=EMBEDDER_MODEL.read_bytes()),
        l2_normalize=True,
        quantize=False,
    )
    return mp.tasks.vision.ImageEmbedder.create_from_options(options)


def embed_file(model, path):
    bgr = cv2.imread(str(path))
    if bgr is None:
        return None
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = model.embed(image)
    return np.asarray(result.embeddings[0].embedding, dtype=np.float32)


def main():
    if not EMBEDDER_MODEL.exists():
        raise SystemExit(f"Missing embedder model: {EMBEDDER_MODEL}")
    if not DATASET.exists():
        raise SystemExit(f"Create {DATASET} and add one folder per fruit.")

    classes = {}
    for folder in sorted(path for path in DATASET.iterdir() if path.is_dir()):
        photos = [path for path in folder.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES]
        if photos:
            classes[folder.name.lower()] = photos
    if not classes:
        raise SystemExit("No photos found. Add images under dataset/<fruit-name>/")

    model = embedder()
    names = []
    vectors = []
    for name, photos in classes.items():
        encoded = []
        for photo in photos:
            vector = embed_file(model, photo)
            if vector is not None:
                encoded.append(vector)
        if not encoded:
            print(f"Skipped {name}: no readable images.")
            continue
        for vector in encoded:
            names.append(name)
            vectors.append(vector.astype(np.float32))
        print(f"{name}: {len(encoded)} photos")

    if not names:
        raise SystemExit("Nothing to save.")
    np.savez(GALLERY, names=np.array(names), vectors=np.stack(vectors))
    print(f"Saved {GALLERY}")
    print("Restart app.py and press f. Asmamir uses these names in fruit mode.")


if __name__ == "__main__":
    main()
