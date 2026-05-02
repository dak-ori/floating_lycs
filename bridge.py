"""
Apple Music (Microsoft Store) → Lyrs 브릿지
=============================================
Windows SMTC API로 Apple Music 재생 정보를 읽어
Lyrs의 tuna-obs 서버(127.0.0.1:1608)로 전송합니다.

설치:
    pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Storage.Streams

실행:
    python apple_music_lyrs_bridge.py
"""

import asyncio
import json
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
except ImportError:
    print("=" * 50)
    print("winrt 패키지가 설치되어 있지 않습니다.")
    print("아래 명령어로 설치해주세요:")
    print()
    print("    pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Storage.Streams")
    print("=" * 50)
    sys.exit(1)

# ── 설정 ─────────────────────────────────────────
LYRS_URL = "http://127.0.0.1:1608"
POLL_INTERVAL_PLAYING = 0.2   # 재생 중 — 가사 동기화에 필요한 빈도
POLL_INTERVAL_PAUSED  = 1.0   # 일시정지 / 정지 / 미발견 — CPU 절약
APPLE_MUSIC_APP_IDS = [
    "AppleInc.AppleMusic",
    "Apple.AppleMusic",
]
# ─────────────────────────────────────────────────


def _post_to_lyrs_sync(body: bytes) -> bool:
    """블로킹 HTTP POST — run_in_executor에서만 호출."""
    req = urllib.request.Request(
        LYRS_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False


async def post_to_lyrs(data: dict) -> bool:
    body = json.dumps(data).encode("utf-8")
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _post_to_lyrs_sync, body)


def parse_artist(raw_artist: str) -> str:
    """Apple Music SMTC는 artist 필드에 '아티스트 — 앨범' 형식으로 넣어줌."""
    return raw_artist.split(" — ")[0].strip()


def _make_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


def _fetch_itunes_cover_sync(title: str, artist: str) -> str | None:
    """블로킹 iTunes Search API 호출 — run_in_executor에서만 호출."""
    try:
        query = urllib.parse.quote(f"{artist} {title}")
        url = f"https://itunes.apple.com/search?term={query}&media=music&entity=song&limit=5"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3, context=_make_ssl_context()) as resp:
            data = json.loads(resp.read())
        results = data.get("results", [])
        if not results:
            return None
        artwork = results[0].get("artworkUrl100", "")
        return artwork.replace("100x100bb", "600x600bb") if artwork else None
    except Exception:
        return None


async def fetch_itunes_cover(title: str, artist: str) -> str | None:
    """iTunes Search API로 앨범 커버 URL을 가져옵니다."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch_itunes_cover_sync, title, artist)


def find_apple_music_session(sessions):
    all_sessions = sessions.get_sessions()
    for session in all_sessions:
        app_id = session.source_app_user_model_id or ""
        for known_id in APPLE_MUSIC_APP_IDS:
            if known_id.lower() in app_id.lower():
                return session
        if "apple" in app_id.lower():
            return session
    return None


PLAYBACK_STATUS_MAP = {
    PlaybackStatus.CLOSED: "idle",
    PlaybackStatus.OPENED: "idle",
    PlaybackStatus.CHANGING: "paused",
    PlaybackStatus.STOPPED: "idle",
    PlaybackStatus.PLAYING: "playing",
    PlaybackStatus.PAUSED: "paused",
}


async def get_current_state(session) -> dict:
    try:
        props = await session.try_get_media_properties_async()
        timeline = session.get_timeline_properties()
        playback = session.get_playback_info()
    except Exception:
        return {"data": {"status": "idle"}}

    raw_status = playback.playback_status if playback else None
    status = PLAYBACK_STATUS_MAP.get(raw_status, "idle")

    if status == "idle":
        return {"data": {"status": "idle"}}

    try:
        progress_ms = int(timeline.position.total_seconds() * 1000)
        duration_ms = int(timeline.end_time.total_seconds() * 1000)
    except Exception:
        progress_ms = 0
        duration_ms = 0

    title = props.title or ""
    artist = parse_artist(props.artist or "")   # "아티스트 — 앨범" → "아티스트"

    return {
        "data": {
            "status": status,
            "title": title,
            "artists": [artist] if artist else [],
            "progress": progress_ms,
            "duration": duration_ms,
            "cover_url": "",
        }
    }


async def main():
    print("🎵 Apple Music → Lyrs 브릿지")
    print(f"   Lyrs 서버: {LYRS_URL}")
    print("   종료: Ctrl+C\n")

    last_title = None
    last_cover_url = None
    smtc_anchor_ms = 0
    smtc_anchor_time = time.monotonic()
    not_found_printed = False
    last_sent_key = None    # (status, title, cover_url) — 중복 POST 방지
    sessions = None         # MediaManager 캐시 — 매 틱 재생성 방지

    while True:
        poll_interval = POLL_INTERVAL_PAUSED
        try:
            # MediaManager는 WinRT 싱글턴 — 오류 시에만 재요청
            if sessions is None:
                sessions = await MediaManager.request_async()

            session = find_apple_music_session(sessions)

            if session is None:
                if not not_found_printed:
                    print("⏹  Apple Music 세션을 찾을 수 없습니다. Apple Music이 실행 중인지 확인하세요.")
                    not_found_printed = True
                await post_to_lyrs({"data": {"status": "idle"}})
                await asyncio.sleep(poll_interval)
                continue

            not_found_printed = False
            state = await get_current_state(session)
            current_status = state["data"].get("status", "idle")
            current_title = state["data"].get("title")
            current_artist = state["data"].get("artists", [""])[0]

            # SMTC position은 실시간이 아니라 스냅샷 → 내부 시계로 보간
            if current_status == "playing" and "progress" in state["data"]:
                raw_ms = state["data"]["progress"]
                now = time.monotonic()
                elapsed_ms = int((now - smtc_anchor_time) * 1000)
                interpolated_ms = smtc_anchor_ms + elapsed_ms
                if abs(raw_ms - interpolated_ms) > 2000:
                    # 2초 이상 차이 → 사용자가 탐색했거나 새 곡 → 앵커 리셋
                    smtc_anchor_ms = raw_ms
                    smtc_anchor_time = now
                    state["data"]["progress"] = raw_ms
                else:
                    state["data"]["progress"] = interpolated_ms
            else:
                # 일시정지/정지 중엔 SMTC 값 그대로 쓰고 앵커 동기화
                smtc_anchor_ms = state["data"].get("progress", smtc_anchor_ms)
                smtc_anchor_time = time.monotonic()

            # 곡이 바뀌었을 때만 iTunes에서 커버를 새로 가져옴
            if current_title != last_title:
                last_cover_url = await fetch_itunes_cover(current_title, current_artist)
                last_title = current_title
                icon = "▶" if current_status == "playing" else "⏸" if current_status == "paused" else "⏹"
                cover_ok = "🖼" if last_cover_url else "❌"
                print(f"{icon}  {current_title}  [{current_artist}]  커버:{cover_ok}")

            state["data"]["cover_url"] = last_cover_url or ""

            # 재생 중: 항상 POST (가사 위치 추적에 필요)
            # 정지 / 일시정지: 상태가 바뀔 때만 POST
            sent_key = (current_status, current_title, last_cover_url)
            if current_status == "playing" or sent_key != last_sent_key:
                await post_to_lyrs(state)
                last_sent_key = sent_key

            poll_interval = POLL_INTERVAL_PLAYING if current_status == "playing" else POLL_INTERVAL_PAUSED

        except Exception as e:
            print(f"⚠ 오류: {e}")
            sessions = None  # WinRT 핸들 오류 시 재취득

        await asyncio.sleep(poll_interval)


def _make_icon():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, 63, 63], fill=(250, 60, 60, 255))
    draw.rectangle([27, 16, 32, 40], fill=(255, 255, 255, 255))
    draw.polygon([(32, 16), (48, 21), (48, 30), (32, 25)], fill=(255, 255, 255, 255))
    draw.ellipse([18, 34, 34, 46], fill=(255, 255, 255, 255))
    return img


def _run_bridge():
    asyncio.run(main())


if __name__ == "__main__":
    try:
        import pystray

        icon = pystray.Icon(
            "apple_music_lyrs",
            _make_icon(),
            "Apple Music → Lyrs",
            menu=pystray.Menu(
                pystray.MenuItem("Apple Music → Lyrs", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("종료", lambda icon, _: icon.stop()),
            ),
        )

        t = threading.Thread(target=_run_bridge, daemon=True)
        t.start()
        icon.run()

    except ImportError:
        # pystray/Pillow 없으면 콘솔 모드로 fallback
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n종료했습니다.")
