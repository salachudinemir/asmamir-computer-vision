# Asmamir Computer Vision

Aplikasi desktop Windows. Satu proses, `app.py`, memakai webcam dan mikrofon di komputer ini. Setelah logon tidak ada jendela. Bangun dengan jentikan ibu jari ke jari tengah, atau dengan suara `asmamir`. Setelah bangun, yang tampil adalah hologram siaga. Perintah suara membuka mode lain. Pengenalan suara Inggris memakai Vosk di mesin lokal.

Kode Python dan HTML di repo ini dilisensikan MIT. Aset pihak ketiga tidak termasuk. Lihat [SECURITY.md](SECURITY.md) sebelum menjalankan atau memublikasikan salinan.

## Yang tidak ada di repo

Setiap orang mengunduh asetnya sendiri. Jangan menambahkan berkas ini ke git:

- Model Vosk, cache Whisper, suara Piper, dan bobot lain di `models/`.
- Clip FBX Mixamo. Lisensi Mixamo pada umumnya tidak mengizinkan mengedarkan ulang file FBX. Nama yang dipakai kode, di `web/hologram/`: `asmamir_situp_to_idle.fbx`, `asmamir_rumba_dancing.fbx`, `asmamir_salsa_dancing.fbx`, `asmamir_dancing_twerk.fbx`.
- Model 3D lain (`*.glb`, `*.usdz`, `*.npz`), tekstur, folder `web/hologram/source/`, `web/airbus/`, dan `web/deagle/`.
- `.env`, `venv/`, `dataset/`, `dataset_aug/`, dan log lokal.

Tanpa clip FBX, bangun tetap bisa, tetapi hologram tidak punya gerak.

## Pemasangan (Windows, Python 3.12)

Lingkungan pengembangan ini memakai Python 3.12. `requirements.txt` adalah hasil `pip freeze` seluruh venv, bukan daftar minimal, dan berisi paket berat yang tidak diimpor aplikasi (termasuk `jax`). Untuk memasang yang benar-benar diimpor kode:

`opencv-python`, `mediapipe`, `numpy`, `SpeechRecognition`, `PyAudio`, `vosk`, `sounddevice`, `comtypes`, `piper-tts`, `faster-whisper`, `sympy`, `rapidocr-onnxruntime`, `pillow`, `mss`, `websockets`, `ufbx`.

```bat
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -U pip
venv\Scripts\python.exe -m pip install opencv-python mediapipe numpy SpeechRecognition PyAudio vosk sounddevice comtypes piper-tts faster-whisper sympy rapidocr-onnxruntime pillow mss websockets ufbx
```

`PyAudio` di Windows sering butuh wheel yang cocok dengan Python 3.12. Bila impor native gagal, pasang Microsoft Visual C++ Redistributable.

`web/p5.min.js` adalah p5.js (LGPL-2.1). Berkas itu boleh ikut repo hanya bersama pemberitahuan lisensinya.

## Model suara

Vosk tidak di-vendor. Unduh `vosk-model-small-en-us-0.15` dari [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models) dan ekstrak sehingga folder ini ada:

`models/vosk-model-small-en-us-0.15`

Di dalamnya ada `am/` dan `graph/`. `app.py` memuat path itu.

Bahasa Indonesia opsional. Suara Piper `id_ID-news_tts-medium.onnx` diletakkan di `models/piper/`. Whisper tiny diunduh `faster-whisper` ke `models/whisper/` pada pemakaian pertama. Keduanya tetap di luar git.

## Hermes dan Ollama (opsional)

Obrolan dan “lihat ini” mencoba Hermes `http://127.0.0.1:8642` lebih dulu, lalu Ollama `http://127.0.0.1:11434`. `app.py` tidak menyalakan gateway Hermes. Bila keduanya mati, aplikasi tetap jalan dan kalimat itu dilewati.

Nama yang diucapkan aplikasi dibaca dari `.env` (berkas ini tidak di-commit):

- `ASMAMIR_USER_FULL_NAME`
- `ASMAMIR_USER_NICKNAME`

Bila kosong, yang dipakai adalah `User` dan `friend`. Pelafalan SAPI opsional lewat `ASMAMIR_SAID_FULL`, `ASMAMIR_SAID_GIVEN`, `ASMAMIR_SAID_FAMILY`, dan `ASMAMIR_SAID_NICK`. Mikrofon bisa diarahkan dengan `ASMAMIR_MIC`.

## Menjalankan

```bat
venv\Scripts\python.exe app.py
```

Task Scheduler opsional dan tidak didaftarkan oleh repo. `scripts/start_login.cmd` bisa dijadikan tugas saat log on, tanpa admin. Skrip memakai folder proyek di atas folder `scripts`, bukan path seseorang. Ia memeriksa Hermes `http://127.0.0.1:8642/health`, menyalakan gateway lokal hanya bila health-nya mati dan peluncurnya ada, lalu `scripts/start_dsh.cmd` (`ollama launch dsh` bila proses itu belum jalan), lalu satu `app.py`. Tidak membuka jendela kamera kedua.

## Perintah

1. **Bangun.** Jentikan ibu jari ke jari tengah, atau ucapan nama Asmamir. Tepukan tidak membangunkan.
2. **Siaga.** Hologram. Sit-up diputar sekali lalu ditahan. Cubit plus telunjuk tangan lain memutar orbit.
3. **Dance.** Ucapan `dance`, atau jentikan yang sama setelah bangun, menggilir rumba, salsa, lalu twerk. `stop dance` atau `standby` memutar sit-up lagi.
4. **Anime.** `anime` atau `stipple` (bukan `anime kamera`). Layar utama diambil, persegi panjang diseret, lalu `web/anime_board.html` menampilkan titik warna. Hati membesar dari tengah ke tepi selama 10 detik, lalu hilang, dan gambar membeku.
5. **Canvas.** Hanya jika seluruh ucapan adalah `canvas`, `draw`, atau `drawing`.
6. **YouTube.** `open youtube` membuka situs. `play …` atau `putar …` membuka hasil pertama.
7. **Fog.** Hanya `fog mirror`.
8. **Shutdown.** `shutdown`, `shut down`, `matikan`, atau tombol `q`.

Proses yang sama juga bisa menghitung jari, membaca halaman, menyalakan filter kamera, Airbus, Desert Eagle, naga, dan kursor tangan.

## Lisensi

Kode yang ditulis untuk proyek ini: MIT. FBX Mixamo, model 3D, tekstur, bobot Vosk, suara Piper, dan bobot Whisper tetap di bawah lisensi masing-masing dan tidak diedarkan dari repo ini.
