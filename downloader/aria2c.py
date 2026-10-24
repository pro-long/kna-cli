"""
aria2c integration for KnaCLI.

Starts aria2c as a background subprocess, streams its stdout,
parses the progress lines, and fires callbacks.
"""

import asyncio
import os
import re
from typing import Callable, Optional

# Matches aria2c's console progress line, e.g.:
# [#abc123 16MiB/6.07GiB(2%) CN:1 DL:4.1MiB ETA:25m19s]
_PROGRESS_RE = re.compile(
    r"\[#\S+\s+"
    r"(?P<downloaded>[\d.]+\S+)"
    r"/"
    r"(?P<total>[\d.]+\S+)"
    r"\((?P<percent>\d+)%\)"
    r".*?"
    r"DL:(?P<speed>[\d.]+\S+)"
    r"(?:.*?ETA:(?P<eta>\S+))?",
)


async def download_with_aria2c(
    magnet_url: str,
    download_path: str,
    aria2c_path: str = "aria2c",
    on_progress: Optional[Callable[[dict], None]] = None,
    on_complete: Optional[Callable[[], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> asyncio.subprocess.Process:
    """
    Launch aria2c and start downloading.

    Returns the asyncio Process object (so callers can terminate it).
    Progress is reported via callbacks fired from a background task.
    """
    os.makedirs(download_path, exist_ok=True)

    cmd = [
        aria2c_path,
        "--dir", download_path,
        "--summary-interval=1",    # progress line every 1s (valid aria2c option)
        # --bt-enable-lpd omitted: LPD uses multicast which Android blocks → error 28
        "--enable-dht=true",
        "--enable-peer-exchange=true",
        "--bt-max-peers=50",
        "--seed-time=0",           # stop seeding after download
        "--check-certificate=false",
        magnet_url,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,  # keep separate so error text is readable
    )

    # Read aria2c output in a background task
    asyncio.create_task(
        _stream_output(process, on_progress, on_complete, on_error)
    )

    return process


async def _stream_output(
    process: asyncio.subprocess.Process,
    on_progress: Optional[Callable],
    on_complete: Optional[Callable],
    on_error: Optional[Callable],
) -> None:
    """Read aria2c stdout/stderr line by line and parse progress."""
    _error_lines: list[str] = []

    async def _drain_stderr() -> None:
        """Collect stderr lines in the background for error reporting."""
        async for raw in process.stderr:
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                _error_lines.append(text)

    stderr_task = asyncio.create_task(_drain_stderr())

    try:
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            # Progress line
            match = _PROGRESS_RE.search(line)
            if match and on_progress:
                on_progress(
                    {
                        "downloaded": match.group("downloaded"),
                        "total": match.group("total"),
                        "percent": int(match.group("percent")),
                        "speed": match.group("speed"),
                        "eta": match.group("eta") or "?",
                        "raw": line,
                    }
                )
                continue

            # Completion signals
            if on_complete and (
                "Download complete" in line
                or "NOTICE] Download Results" in line
                or "will be closed" in line
            ):
                on_complete()

        # Wait for process and stderr drain to finish
        await process.wait()
        await stderr_task

        if process.returncode == 0:
            if on_complete:
                on_complete()
        elif process.returncode is not None and process.returncode != 0:
            if on_error:
                # Show actual aria2c error text when available
                detail = "\n".join(_error_lines[-5:]) if _error_lines else ""
                msg = f"aria2c exited with code {process.returncode}"
                if detail:
                    msg += f":\n{detail}"
                on_error(msg)

    except Exception as exc:
        await stderr_task
        if on_error:
            on_error(str(exc))
