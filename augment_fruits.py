"""Buat salinan augmentasi ringan dari foto di dataset/.

Foto asli tetap di dataset/<kelas>/.
Hasil ditulis ke dataset_aug/<kelas>/<nama>_aug_N.jpg.

    venv\\Scripts\\python augment_fruits.py
"""

import cv2
import albumentations as A
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "dataset"
DST = ROOT / "dataset_aug"
SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VARIANTS = 3

transform = A.Compose(
    [
        A.Rotate(limit=15, border_mode=cv2.BORDER_REFLECT_101, p=0.8),
        A.RandomBrightnessContrast(brightness_limit=0.15, contrast_limit=0.15, p=0.8),
        A.GaussNoise(std_range=(0.02, 0.06), p=0.3),
        A.GaussianBlur(blur_limit=(3, 5), p=0.2),
    ]
)


def main():
    if not SRC.exists():
        raise SystemExit(f"Folder sumber tidak ada: {SRC}")

    written = 0
    classes = sorted(path for path in SRC.iterdir() if path.is_dir())
    if not classes:
        raise SystemExit(f"Tidak ada subfolder kelas di {SRC}")

    for folder in classes:
        photos = [path for path in folder.iterdir() if path.suffix.lower() in SUFFIXES]
        if not photos:
            print(f"Lewati {folder.name}: tidak ada gambar.")
            continue
        out = DST / folder.name
        out.mkdir(parents=True, exist_ok=True)
        class_written = 0
        for photo in photos:
            bgr = cv2.imread(str(photo))
            if bgr is None:
                print(f"Lewati file yang tidak terbaca: {photo}")
                continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            for index in range(VARIANTS):
                augmented = transform(image=rgb)["image"]
                dest = out / f"{photo.stem}_aug_{index + 1}.jpg"
                ok = cv2.imwrite(str(dest), cv2.cvtColor(augmented, cv2.COLOR_RGB2BGR))
                if not ok:
                    print(f"Gagal menulis: {dest}")
                    continue
                written += 1
                class_written += 1
        print(f"{folder.name}: {len(photos)} file, {class_written} gambar tertulis di {out}")

    print(f"Selesai. {written} gambar ada di {DST}")
    print("Salin isi dataset_aug ke dataset jika ingin ikut dilatih oleh train_fruits.py.")


if __name__ == "__main__":
    main()
