"""
Entry point.
- asyncio bridge loop runs in a dedicated daemon thread (pystray compat)
- pystray tray icon runs on the main thread
"""

import asyncio
import logging
import threading
import time

import pystray
from PIL import Image, ImageDraw

from lyrs_poster import post_track
from smtc_reader import read_track_info

log = logging.getLogger(__name__)

POLL_INTERVAL = 1.0  # seconds


def _make_tray_icon() -> Image.Image:
    """Simple 64×64 solid icon (music note look)."""
    img = Image.new("RGBA", (64, 64), (30, 30, 30, 255))
    draw = ImageDraw.Draw(img)
    # stem
    draw.rectangle([34, 16, 40, 44], fill=(255, 255, 255, 255))
    # flag
    draw.polygon([(40, 16), (56, 22), (56, 32), (40, 26)], fill=(255, 255, 255, 255))
    # note head
    draw.ellipse([22, 38, 42, 52], fill=(255, 255, 255, 255))
    return img


class Bridge:
    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_info: dict | None = None

    # ------------------------------------------------------------------
    # asyncio bridge loop (runs in a background thread)
    # ------------------------------------------------------------------

    def _changed(self, new: dict) -> bool:
        if self._last_info is None:
            return True
        return (
            new["title"] != self._last_info["title"]
            or new["artists"] != self._last_info["artists"]
            or new["status"] != self._last_info["status"]
        )

    async def _bridge_loop(self):
        log.info("Bridge loop started")
        while self._running:
            try:
                info = await read_track_info()
                if info is not None and self._changed(info):
                    self._last_info = info
                    post_track(info)
                elif info is not None:
                    # Always post progress even if title/status didn't change
                    post_track(info)
            except Exception as e:
                log.debug("bridge_loop iteration error: %s", e)
            await asyncio.sleep(POLL_INTERVAL)
        log.info("Bridge loop stopped")

    def _thread_target(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._bridge_loop())
        finally:
            self._loop.close()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._thread_target, daemon=True)
        self._thread.start()
        log.info("Bridge thread started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Bridge thread stopped")


# ------------------------------------------------------------------
# pystray tray icon (main thread)
# ------------------------------------------------------------------

def _build_menu(bridge: Bridge, icon: pystray.Icon):
    def on_quit(icon, item):
        bridge.stop()
        icon.stop()

    return pystray.Menu(
        pystray.MenuItem("Apple Music → Lyrs Bridge", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    bridge = Bridge()
    bridge.start()

    icon_image = _make_tray_icon()
    icon = pystray.Icon(
        name="apple_music_bridge",
        icon=icon_image,
        title="Apple Music → Lyrs",
    )
    icon.menu = _build_menu(bridge, icon)

    log.info("Tray icon starting (main thread)")
    try:
        icon.run()  # blocks until Quit is chosen
    except KeyboardInterrupt:
        bridge.stop()
        icon.stop()


if __name__ == "__main__":
    main()
