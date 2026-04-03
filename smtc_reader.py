"""
SMTC (System Media Transport Controls) reader.
Finds the Apple Music session via get_sessions() iteration and extracts
current track info + thumbnail.
"""

import asyncio
import base64
import logging

import winrt.windows.media.control as wmc
import winrt.windows.storage.streams as wss

log = logging.getLogger(__name__)

APPLE_MUSIC_APP_ID = "AppleInc.AppleMusicWin_nzyj5cx40ttqa!App"
THUMBNAIL_BUF_SIZE = 5 * 1024 * 1024  # 5 MB

PlaybackStatus = wmc.GlobalSystemMediaTransportControlsSessionPlaybackStatus

_STATUS_MAP = {
    PlaybackStatus.PLAYING: "playing",
    PlaybackStatus.PAUSED: "paused",
    PlaybackStatus.STOPPED: "stopped",
}


async def _get_apple_music_session(
    manager: wmc.GlobalSystemMediaTransportControlsSessionManager,
):
    """Return the Apple Music session or None if not found."""
    sessions = manager.get_sessions()
    for session in sessions:
        if session.source_app_user_model_id == APPLE_MUSIC_APP_ID:
            return session
    return None


async def _extract_thumbnail(stream_ref) -> str:
    """
    Follow the spec extraction order exactly:
    IRandomAccessStreamReference
    → open_read_async()
    → Buffer(5MB)
    → read_async(buf, buf.capacity, InputStreamOptions.READ_AHEAD)
    → DataReader.from_buffer(buf)
    → bytearray(buf.length)
    → reader.read_bytes(img_bytes)
    → base64.b64encode(img_bytes)
    → "data:image/png;base64,{b64}"
    """
    try:
        stream = await stream_ref.open_read_async()
        buf = wss.Buffer(THUMBNAIL_BUF_SIZE)
        buf = await stream.read_async(buf, buf.capacity, wss.InputStreamOptions.READ_AHEAD)
        reader = wss.DataReader.from_buffer(buf)
        img_bytes = bytearray(buf.length)
        reader.read_bytes(img_bytes)
        b64 = base64.b64encode(img_bytes).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        log.debug("thumbnail extraction failed: %s", e)
        return ""


async def read_track_info() -> dict | None:
    """
    Return a dict with track info, or None if Apple Music is not running
    or no media is available.

    Dict keys: title, artists, status, progress (ms), duration (ms), cover
    """
    try:
        manager = await wmc.GlobalSystemMediaTransportControlsSessionManager.request_async()
        session = await _get_apple_music_session(manager)
        if session is None:
            return None

        props = await session.try_get_media_properties_async()
        if props is None:
            return None

        playback = session.get_playback_info()
        timeline = session.get_timeline_properties()

        raw_status = playback.playback_status if playback else None
        status = _STATUS_MAP.get(raw_status, "stopped")

        position = timeline.position if timeline else None
        end_time = timeline.end_time if timeline else None
        progress_ms = int(position.total_seconds() * 1000) if position else 0
        duration_ms = int(end_time.total_seconds() * 1000) if end_time else 0

        cover = ""
        if props.thumbnail:
            cover = await _extract_thumbnail(props.thumbnail)

        return {
            "title": props.title or "",
            "artists": props.artist or "",
            "status": status,
            "progress": progress_ms,
            "duration": duration_ms,
            "cover": cover,
        }

    except Exception as e:
        log.debug("read_track_info error: %s", e)
        return None


# ---------------------------------------------------------------------------
# Quick terminal test — run:  python smtc_reader.py
# Make sure Apple Music is open and playing before running.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import time

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    async def _poll_loop(iterations: int = 5, interval: float = 1.0):
        print(f"Polling SMTC every {interval}s  (×{iterations})\n")
        for i in range(1, iterations + 1):
            info = await read_track_info()
            if info is None:
                print(f"[{i}/{iterations}] Apple Music not found — waiting...")
            else:
                cover_preview = (
                    info["cover"][:60] + "…" if info["cover"] else "(none)"
                )
                print(
                    f"[{i}/{iterations}] "
                    f"{info['status'].upper():7s}  "
                    f"\"{info['title']}\"  by  {info['artists']}\n"
                    f"          progress={info['progress']}ms / {info['duration']}ms\n"
                    f"          cover={cover_preview}"
                )
            if i < iterations:
                time.sleep(interval)
        print("\nDone.")

    try:
        asyncio.run(_poll_loop())
    except KeyboardInterrupt:
        sys.exit(0)
