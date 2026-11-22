"""Verify tools/ketik.mp3 (mechanical click) used by click_sound."""
from click_sound import MP3_PATH, prepare

path = prepare()
print(f"{path} siap (mechanic click; expected {MP3_PATH.resolve()})")
