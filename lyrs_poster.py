"""
HTTP poster for the tuna-obs protocol consumed by Lyrs.
POST http://localhost:1608/  with a JSON body.
"""

import logging

import requests

log = logging.getLogger(__name__)

LYRS_URL = "http://localhost:1608/"
POST_TIMEOUT = 2  # seconds


def post_track(info: dict) -> bool:
    """
    Send track info to Lyrs (tuna-obs format).
    Returns True on success, False on any failure (failure is non-fatal).

    Expected keys in info:
        title, artists, status, progress (ms), duration (ms), cover
    """
    payload = {
        "cover": info.get("cover", ""),
        "title": info.get("title", ""),
        "artists": info.get("artists", ""),
        "status": info.get("status", "stopped"),
        "progress": info.get("progress", 0),
        "duration": info.get("duration", 0),
    }
    try:
        resp = requests.post(LYRS_URL, json=payload, timeout=POST_TIMEOUT)
        resp.raise_for_status()
        log.debug("POST OK  %s", payload.get("title"))
        return True
    except requests.exceptions.ConnectionError:
        log.debug("Lyrs not reachable (connection refused) — skipping")
    except requests.exceptions.Timeout:
        log.debug("Lyrs POST timed out — skipping")
    except Exception as e:
        log.debug("Lyrs POST failed: %s", e)
    return False
