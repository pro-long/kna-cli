"""
Torrent file fetcher + bencode parser.

Uses the torrent infohash from the Knaben API response to:
  1. Fetch the .torrent file from public caches
  2. Parse the bencode encoding
  3. Return a structured file listing with sizes
"""

import httpx

# -----------------------------------------------------------------------
# Public torrent cache services — tried in order until one works
# -----------------------------------------------------------------------
CACHE_URLS = [
    "https://itorrents.org/torrent/{hash}.torrent",
    "https://torcache.net/torrent/{hash}.torrent",
    "https://btcache.me/torrent/{hash}",
]

FETCH_HEADERS = {
    "User-Agent": "KnaCLI/1.0 (Termux; Android)",
}


# -----------------------------------------------------------------------
# Bencode parser (pure Python, no dependencies)
# -----------------------------------------------------------------------

def _decode(data: bytes, idx: int = 0):
    """
    Minimal recursive bencode decoder.
    Returns (decoded_value, next_index).
    """
    if idx >= len(data):
        raise ValueError("Unexpected end of bencode data")

    char = chr(data[idx])

    # Dictionary
    if char == "d":
        idx += 1
        result: dict = {}
        while idx < len(data) and chr(data[idx]) != "e":
            key, idx = _decode(data, idx)
            val, idx = _decode(data, idx)
            result[key] = val
        return result, idx + 1  # skip 'e'

    # List
    if char == "l":
        idx += 1
        result_list: list = []
        while idx < len(data) and chr(data[idx]) != "e":
            item, idx = _decode(data, idx)
            result_list.append(item)
        return result_list, idx + 1  # skip 'e'

    # Integer
    if char == "i":
        end = data.index(b"e", idx)
        return int(data[idx + 1 : end]), end + 1

    # Byte-string
    if char.isdigit():
        colon = data.index(b":", idx)
        length = int(data[idx:colon])
        start = colon + 1
        return data[start : start + length], start + length

    raise ValueError(f"Unknown bencode token at index {idx}: {char!r}")


# -----------------------------------------------------------------------
# Torrent info extraction
# -----------------------------------------------------------------------

def _safe_decode(b: bytes) -> str:
    """Decode bytes to string, replacing undecodable chars."""
    if isinstance(b, bytes):
        return b.decode("utf-8", errors="replace")
    return str(b)


def parse_torrent_bytes(content: bytes) -> list[dict]:
    """
    Parse raw .torrent file bytes.

    Returns a list of dicts:
        [{"path": "relative/path/to/file.ext", "size": <bytes>}, ...]
    """
    try:
        torrent, _ = _decode(content)
        info: dict = torrent.get(b"info", {})

        # Multi-file torrent
        files = info.get(b"files")
        if files:
            result = []
            for f in files:
                path_parts = f.get(b"path", [b"unknown"])
                path = "/".join(_safe_decode(p) for p in path_parts)
                result.append(
                    {"path": path, "size": f.get(b"length", 0)}
                )
            return result

        # Single-file torrent
        name = _safe_decode(info.get(b"name", b"unknown"))
        size = info.get(b"length", 0)
        return [{"path": name, "size": size}]

    except Exception:
        return []


# -----------------------------------------------------------------------
# Async fetcher
# -----------------------------------------------------------------------

async def fetch_file_list(info_hash: str) -> list[dict]:
    """
    Try to download .torrent from public caches using the infohash,
    parse it, and return the file listing.

    Returns [] if all caches are unavailable.
    """
    hash_upper = info_hash.upper()

    async with httpx.AsyncClient(
        timeout=10.0,
        headers=FETCH_HEADERS,
        follow_redirects=True,
    ) as client:
        for template in CACHE_URLS:
            url = template.format(hash=hash_upper)
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.content) > 20:
                    files = parse_torrent_bytes(resp.content)
                    if files:
                        return files
            except Exception:
                continue  # try next cache

    return []
