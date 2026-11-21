"""Generate tools/ketik.wav (mechanical click) next to this script."""
from click_sound import WAV_PATH, ensure_wav

path = ensure_wav(WAV_PATH)
print(f"{path} dibuat (mechanic click)")
