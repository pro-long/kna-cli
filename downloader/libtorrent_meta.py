"""
libtorrent_meta.py — fetch torrent file list from a magnet link.

Uses libtorrent in *upload_mode* (metadata-only) so we never touch
actual piece data.  Falls back gracefully when libtorrent is not
installed (returns an empty list).
"""

import asyncio
import time
from typing import Optional


async def fetch_meta_from_magnet(
    magnet: str,
    timeout: float = 30.0,
    listen_port: int = 6882,
) -> list[dict]:
    """
    Fetch file list from a magnet link using libtorrent metadata exchange.

    Returns a list of dicts: [{"path": "...", "size": <bytes>}, ...]
    Returns [] if libtorrent is unavailable or metadata fetch times out.
    """
    try:
        import libtorrent as lt  # type: ignore
    except ImportError:
        return []

    loop = asyncio.get_event_loop()

    def _blocking_fetch() -> list[dict]:
        ses = lt.session({"listen_interfaces": f"0.0.0.0:{listen_port}"})
        params = lt.parse_magnet_uri(magnet)
        params.save_path = "/tmp"
        params.flags |= lt.torrent_flags.upload_mode  # metadata-only, no data download

        handle = ses.add_torrent(params)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for alert in ses.pop_alerts():
                if isinstance(alert, lt.metadata_failed_alert):
                    ses.remove_torrent(handle)
                    return []
            if handle.status().has_metadata:
                break
            time.sleep(0.25)
        else:
            ses.remove_torrent(handle)
            return []

        info = handle.torrent_file()
        if info is None:
            ses.remove_torrent(handle)
            return []

        storage = info.files()
        result: list[dict] = []
        for i in range(storage.num_files()):
            result.append(
                {
                    "path": storage.file_path(i),
                    "size": storage.file_size(i),
                }
            )

        ses.remove_torrent(handle)
        return result

    # Run the blocking libtorrent call in a thread-pool so the Textual
    # event loop stays responsive.
    try:
        files = await loop.run_in_executor(None, _blocking_fetch)
        return files
    except Exception:
        return []
