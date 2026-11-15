# Security

Asmamir uses the camera, the microphone, and screen capture on the machine where it runs. Read this before you run it, and again before the first push.

## The microphone stays on

While `app.py` is running, the microphone is listened to continuously, including when no window is visible. English audio is processed on this machine with Vosk. It is not sent to Google. Do not run it in a shared room unless the people there know.

## The camera opens with no window

Before wake, the webcam opens with no window so a thumb-to-middle snap can be read. The camera light comes on. That is expected.

## Screen capture and window control

Anime mode captures the primary monitor through `mss` (GDI), then waits for a mouse drag. The code calls `user32` through ctypes for topmost windows, foreground, and the real cursor. The anime board opens Edge or Chrome fullscreen with a separate profile under `%LOCALAPPDATA%\asmamir\`.

## Autostart is not part of the repository

You can attach `scripts/start_login.cmd` to Task Scheduler on your own computer. This repository does not register that task. Anyone who clones the project starts `app.py` themselves.

## Secrets do not go into git

`.env` is not committed. Names, pronunciation, the microphone choice, and a local Hermes key belong only there. `%LOCALAPPDATA%\hermes\.env` also stays on the computer. Do not paste those values into the README, an issue, or a commit.

## Before the first push

Review the file list. `git status` and `git ls-files` must not contain `.env`, `venv/`, `models/`, `dataset/`, photos, `*.fbx`, `*.glb`, `*.usdz`, `*.npz`, `*.zip` or `*.rar` archives, `web/hologram/source/`, `web/hologram/textures/`, `web/airbus/`, `web/deagle/`, `_dbg_` and `_try_` debug images, or logs. One large file is enough to redistribute an asset whose license does not allow it.

Do not commit Mixamo assets or other third-party models. Each person downloads their own.
