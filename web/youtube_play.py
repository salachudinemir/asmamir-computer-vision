"""Voice "play <title>" / "putar <judul>" opens YouTube and starts the first result.

Watch URL when the search page names a video id. Otherwise the results URL
with the video filter (&sp). Never types into WeChat or any other app.
"""

import re
import time
import urllib.parse
import urllib.request
import webbrowser

# YouTube "Type: Video" search filter (base64 protobuf), URL-encoded.
_SP_VIDEOS = "EgIQAQ%3D%3D"
_VIDEO_ID = re.compile(r'"videoId"\s*:\s*"([0-9A-Za-z_-]{11})"')
_WATCH = re.compile(r"watch\?v=([0-9A-Za-z_-]{11})")
_VERBS = {"play", "putar", "mainkan"}
_FILLER = {"the", "a", "an", "song", "video", "lagu", "judul", "on", "di"}
_BLOCK = {"kirim", "ketik", "send", "type", "typing", "typed", "whatsapp", "pesan", "message"}
_LAST = 0.0
_COOLDOWN = 1.6


def _clean(command):
    text = command.replace("-", " ").replace(".", " ").lower()
    return " ".join(text.split()).strip()


def _mentions_whatsapp(words):
    compact = "".join(words)
    if "whatsapp" in compact:
        return True
    return any(words[i] == "whats" and words[i + 1] == "app" for i in range(len(words) - 1))


def title_from(command):
    """Song or video title after play / putar / mainkan. None if this is not that phrase."""
    words = _clean(command).split()
    if not words or words[0] not in _VERBS:
        return None
    if len(words) > 16:
        return None
    if _mentions_whatsapp(words) or any(word in _BLOCK for word in words):
        return None
    rest = words[1:]
    while rest and rest[0] in _FILLER:
        rest = rest[1:]
    if not rest or len(rest) > 12:
        return None
    return " ".join(rest)


def wants(command):
    return title_from(command) is not None


def results_url(title):
    query = urllib.parse.quote_plus(title)
    return f"https://www.youtube.com/results?search_query={query}&sp={_SP_VIDEOS}"


def watch_url(video_id):
    return f"https://www.youtube.com/watch?v={video_id}"


def _fetch(url, timeout=6):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(1_500_000)
    return raw.decode("utf-8", "ignore")


def resolve_url(title, fetch=None):
    """Watch URL from the search HTML, else the results URL that carries &sp."""
    results = results_url(title)
    loader = _fetch if fetch is None else fetch
    try:
        html = loader(results) or ""
    except Exception as exc:
        print(f"YouTube search fetch failed ({exc}). Opening results.")
        return results
    match = _VIDEO_ID.search(html) or _WATCH.search(html)
    if not match:
        return results
    return watch_url(match.group(1))


def open_title(command, opener=None, fetch=None):
    """Open the first result in the browser. True if a tab was requested.

    Does not focus WeChat and does not type.
    """
    global _LAST
    title = title_from(command)
    if not title:
        return False
    now = time.monotonic()
    if now - _LAST < _COOLDOWN:
        print("YouTube play: cooldown, skipped.")
        return True
    url = resolve_url(title, fetch=fetch)
    launch = webbrowser.open if opener is None else opener
    ok = bool(launch(url, new=2))
    if ok:
        _LAST = now
        print(f"YouTube play: {url}")
    else:
        print("YouTube play: browser did not open.")
    return ok
