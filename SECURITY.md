# Keamanan

Asmamir memegang kamera, mikrofon, dan tangkapan layar di mesin orang yang menjalankannya. Baca ini sebelum menjalankan, dan lagi sebelum push pertama.

## Mikrofon tetap menyala

Selama `app.py` hidup, mikrofon terus didengar, termasuk saat belum ada jendela. Audio Inggris diproses di mesin ini dengan Vosk. Tidak ada pengiriman audio ke Google. Jangan jalankan di ruangan bersama tanpa orang-orang di situ mengetahuinya.

## Kamera terbuka tanpa jendela

Sebelum bangun, webcam dibuka tanpa jendela supaya jentikan ibu jari ke jari tengah terbaca. Lampu kamera menyala. Itu perilaku yang diharapkan.

## Tangkapan layar dan kendali jendela

Mode anime mengambil seluruh monitor utama lewat `mss` (GDI), lalu menunggu seretan mouse. Kode memanggil `user32` lewat ctypes untuk jendela paling atas, foreground, dan kursor sungguhan. Papan anime membuka Edge atau Chrome layar penuh dengan profil terpisah di `%LOCALAPPDATA%\asmamir\`.

## Mulai otomatis tidak ikut repo

`scripts/start_login.cmd` bisa disambungkan ke Task Scheduler di komputer sendiri. Repo tidak mendaftarkan tugas itu. Siapa pun yang mengkloning menyalakan `app.py` sendiri.

## Rahasia tidak masuk git

`.env` tidak di-commit. Nama, pelafalan, pilihan mikrofon, dan kunci Hermes lokal hanya ada di sana. `%LOCALAPPDATA%\hermes\.env` juga tetap di komputer sendiri. Jangan menempelkan nilai itu ke README, isu, atau riwayat commit.

## Sebelum push pertama

Tinjau daftar berkas. `git status` dan `git ls-files` harus bebas dari `.env`, `venv/`, `models/`, `dataset/`, foto, `*.fbx`, `*.glb`, `*.usdz`, `*.npz`, arsip `*.zip` / `*.rar`, `web/hologram/source/`, `web/hologram/textures/`, `web/airbus/`, `web/deagle/`, gambar debug `_dbg_` dan `_try_`, serta log. Satu berkas besar yang lolos sudah cukup untuk mengedarkan aset yang lisensinya tidak mengizinkan edar ulang.

Aset Mixamo dan model pihak ketiga tidak boleh di-commit. Setiap orang mengunduh miliknya sendiri.
