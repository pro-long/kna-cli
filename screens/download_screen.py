"""
Download screen — live aria2c progress + full download manager.

DownloadScreen     — single active download with pause/resume/cancel controls.
DownloadManagerScreen — lists all sessions started this run; shows downloaded
                        files in a collapsible list (SSH-friendly).
"""

import asyncio
import os
import subprocess
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual import work
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    ProgressBar,
    Label,
    RichLog,
    Collapsible,
    DataTable,
)
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer

from downloader.aria2c import download_with_aria2c
from config import Config


# -----------------------------------------------------------------------
# Global in-memory session registry (shared across all screen instances)
# -----------------------------------------------------------------------

# Each entry: {
#   "name": str,
#   "path": str,
#   "status": "downloading" | "paused" | "complete" | "error" | "cancelled",
#   "percent": float,
#   "speed": str,
#   "eta": str,
#   "process": asyncio.subprocess.Process | None,
# }
_SESSIONS: list[dict] = []


def _register_session(name: str, path: str) -> dict:
    entry = {
        "name": name,
        "path": path,
        "status": "downloading",
        "percent": 0.0,
        "speed": "—",
        "eta": "—",
        "process": None,
    }
    _SESSIONS.append(entry)
    return entry


# -----------------------------------------------------------------------
# Download Screen (single active download)
# -----------------------------------------------------------------------

class DownloadScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("c", "cancel_dl", "Cancel"),
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("o", "list_files", "List Files"),
        Binding("q", "go_back", "Back"),
    ]

    def __init__(
        self,
        torrent: dict,
        magnet_url: str,
        download_path: str,
        config: Config,
    ) -> None:
        super().__init__()
        self.torrent = torrent
        self.magnet_url = magnet_url
        self.download_path = download_path
        self.config = config

        self._process: asyncio.subprocess.Process | None = None
        self._percent: float = 0.0
        self._complete = False
        self._error: str | None = None
        self._launched: bool = False
        self._paused: bool = False

        # Register in global session list
        self._session = _register_session(
            name=torrent.get("title", "Unknown"),
            path=download_path,
        )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="dl-main"):
            yield Static("⬇  Download Manager", id="dl-screen-title")

            with Container(id="dl-card"):
                title = self.torrent.get("title", "Unknown")
                yield Static(f"  📄  {title}", id="dl-torrent-name")
                yield Static(
                    f"  📂  Saving to: {self.download_path}",
                    id="dl-save-path",
                )

                yield Static("", id="dl-status")

                yield ProgressBar(total=100, id="dl-progress", show_eta=False)

                with Horizontal(id="dl-stats"):
                    yield Static("", id="stat-downloaded")
                    yield Static("", id="stat-speed")
                    yield Static("", id="stat-eta")

                yield Static("", id="dl-error")

            # Live aria2c output log
            with Container(id="dl-log-box"):
                yield Static("📋  aria2c Output", id="dl-log-header")
                yield RichLog(id="dl-log", highlight=False, markup=False, max_lines=200)

            # Downloaded files listing (collapsible, SSH-friendly)
            with Collapsible(title="📂  List Downloaded Files", id="dl-files-collapsible", collapsed=True):
                yield Static("", id="dl-files-list")

            with Horizontal(id="dl-buttons"):
                yield Button("⏸  Pause", id="btn-pause", variant="warning")
                yield Button("▶  Resume", id="btn-resume", variant="success")
                yield Button("✗  Cancel", id="btn-cancel", variant="error")
                yield Button("←  Back", id="btn-back", variant="primary")

        yield Footer()

    def on_mount(self) -> None:
        # Resume button hidden until paused
        self.query_one("#btn-resume", Button).display = False
        self._update_status("🔄  Connecting — waiting for peers…")
        self._launch_download()

    # ------------------------------------------------------------------
    # aria2c worker
    # ------------------------------------------------------------------

    @work
    async def _launch_download(self) -> None:
        if self._launched:
            return
        self._launched = True

        try:
            self._process = await download_with_aria2c(
                magnet_url=self.magnet_url,
                download_path=self.download_path,
                aria2c_path=self.config.aria2c_path,
                on_progress=self._on_progress,
                on_complete=self._on_complete,
                on_error=self._on_error,
            )
            self._session["process"] = self._process
            self._update_status("🟢  Downloading…")
        except FileNotFoundError:
            self._launched = False
            self._on_error(
                "aria2c not found!\n"
                "  Install it in Termux with:  pkg install aria2"
            )
        except Exception as exc:
            self._launched = False
            self._on_error(str(exc))

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_progress(self, info: dict) -> None:
        self._percent = float(info.get("percent", 0))
        self._session["percent"] = self._percent
        self._session["speed"] = info.get("speed", "—")
        self._session["eta"] = info.get("eta", "—")
        self._session["status"] = "downloading"
        self.call_later(
            self._refresh_ui,
            info.get("downloaded", "?"),
            info.get("total", "?"),
            info.get("speed", "?"),
            info.get("eta", "?"),
            self._percent,
            info.get("raw", ""),
        )

    def _on_complete(self) -> None:
        self._session["status"] = "complete"
        self._session["percent"] = 100.0
        self.call_later(self._show_complete)

    def _on_error(self, message: str) -> None:
        self._session["status"] = "error"
        self.call_later(self._show_error, message)

    # ------------------------------------------------------------------
    # UI updaters
    # ------------------------------------------------------------------

    def _refresh_ui(
        self,
        downloaded: str,
        total: str,
        speed: str,
        eta: str,
        percent: float,
        raw: str = "",
    ) -> None:
        try:
            bar = self.query_one("#dl-progress", ProgressBar)
            bar.update(progress=percent)

            self.query_one("#stat-downloaded", Static).update(
                f"  {downloaded} / {total}"
            )
            self.query_one("#stat-speed", Static).update(f"  Speed: {speed}")
            self.query_one("#stat-eta", Static).update(f"  ETA: {eta}")
            self._update_status(f"🟢  Downloading…  {int(percent)}%")

            if raw:
                log = self.query_one("#dl-log", RichLog)
                log.write(raw)
        except Exception:
            pass

    def _show_complete(self) -> None:
        try:
            self.query_one("#dl-progress", ProgressBar).update(progress=100)
            self._update_status("✅  Download Complete!")
            self.query_one("#stat-speed", Static).update("")
            self.query_one("#stat-eta", Static).update("")
            self.notify("✅ Download complete!", severity="information")
            # Refresh file list automatically on completion
            self._populate_file_list()
        except Exception:
            pass
        finally:
            try:
                if self._process and self._process.returncode is None:
                    self._process.terminate()
            except Exception:
                pass

    def _show_error(self, message: str) -> None:
        try:
            self._update_status("❌  Download Failed")
            self.query_one("#dl-error", Static).update(f"  ⚠  {message}")
            self.notify(f"Download error: {message}", severity="error")
        except Exception:
            pass

    def _update_status(self, text: str) -> None:
        try:
            self.query_one("#dl-status", Static).update(f"  {text}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Downloaded files list (SSH-friendly collapsible)
    # ------------------------------------------------------------------

    def _populate_file_list(self) -> None:
        """Scan download_path and update the collapsible file list."""
        try:
            dl_files_widget = self.query_one("#dl-files-list", Static)
            root = Path(self.download_path)
            if not root.exists():
                dl_files_widget.update("  📂  Folder not found.")
                return

            all_files = sorted(root.rglob("*"))
            file_entries = [f for f in all_files if f.is_file()]

            if not file_entries:
                dl_files_widget.update("  (no files yet)")
                return

            lines: list[str] = []
            for i, f in enumerate(file_entries):
                is_last = i == len(file_entries) - 1
                prefix = "  └─ " if is_last else "  ├─ "
                try:
                    size_bytes = f.stat().st_size
                    size_str = _fmt_size(size_bytes)
                except OSError:
                    size_str = "?"
                rel = f.relative_to(root)
                lines.append(f"{prefix}{rel}   ({size_str})")

            dl_files_widget.update("\n".join(lines))
        except Exception as exc:
            try:
                self.query_one("#dl-files-list", Static).update(f"  Error: {exc}")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "btn-pause":  self.action_toggle_pause,
            "btn-resume": self.action_toggle_pause,
            "btn-cancel": self.action_cancel_dl,
            "btn-back":   self.action_go_back,
        }
        h = handlers.get(event.button.id)
        if h:
            h()

    def on_collapsible_expanded(self, event: Collapsible.Expanded) -> None:
        if event.collapsible.id == "dl-files-collapsible":
            self._populate_file_list()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_toggle_pause(self) -> None:
        if not self._process or self._process.returncode is not None:
            return

        if not self._paused:
            # Pause: send SIGSTOP
            try:
                self._process.send_signal(__import__("signal").SIGSTOP)
            except Exception:
                pass
            self._paused = True
            self._session["status"] = "paused"
            self._update_status("⏸  Paused")
            self.query_one("#btn-pause", Button).display = False
            self.query_one("#btn-resume", Button).display = True
        else:
            # Resume: send SIGCONT
            try:
                self._process.send_signal(__import__("signal").SIGCONT)
            except Exception:
                pass
            self._paused = False
            self._session["status"] = "downloading"
            self._update_status("🟢  Resumed…")
            self.query_one("#btn-pause", Button).display = True
            self.query_one("#btn-resume", Button).display = False

    def action_cancel_dl(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
        self._session["status"] = "cancelled"
        self._update_status("⛔  Download Cancelled")
        self.app.pop_screen()

    def action_list_files(self) -> None:
        """Toggle the file list collapsible and refresh its contents."""
        coll = self.query_one("#dl-files-collapsible", Collapsible)
        if coll.collapsed:
            coll.collapsed = False
            self._populate_file_list()
        else:
            coll.collapsed = True


# -----------------------------------------------------------------------
# Helper
# -----------------------------------------------------------------------

def _fmt_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


# -----------------------------------------------------------------------
# Download Manager Screen — lists all sessions + downloaded files
# -----------------------------------------------------------------------

class DownloadManagerScreen(Screen):
    """
    Shows all downloads started in this session (active, paused, done).
    Selecting a row shows that session's downloaded files in a collapsible list.
    """

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("q", "go_back", "Back"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="mgr-main"):
            yield Static("⬇  Downloads", id="mgr-title")

            # Session table
            yield DataTable(id="mgr-table", show_cursor=True)

            # Per-session file listing (collapsible)
            with Collapsible(
                title="📂  Files in selected download",
                id="mgr-files-collapsible",
                collapsed=True,
            ):
                yield Static("", id="mgr-files-list")

            # Info if no sessions
            yield Static(
                f"  Default path: {self.config.download_path}\n"
                f"  Press [R] to refresh  |  Select a row to browse its files.",
                id="mgr-info",
            )

            with Horizontal(id="mgr-buttons"):
                yield Button("🗑  Delete selected", id="btn-delete", variant="error")
                yield Button("←  Back", id="btn-back", variant="primary")

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#mgr-table", DataTable)
        table.add_columns("Name", "Status", "%", "Speed", "ETA", "Path")
        self._refresh_table()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        table = self.query_one("#mgr-table", DataTable)
        table.clear()

        if not _SESSIONS:
            # Show downloaded files from the download folder when no active sessions
            self._show_folder_files(self.config.download_path)
            return

        for idx, s in enumerate(_SESSIONS):
            status_icon = {
                "downloading": "🟢",
                "paused":      "⏸",
                "complete":    "✅",
                "error":       "❌",
                "cancelled":   "⛔",
            }.get(s["status"], "?")

            table.add_row(
                s["name"][:40],
                f"{status_icon} {s['status']}",
                f"{s['percent']:.0f}%",
                s.get("speed", "—"),
                s.get("eta", "—"),
                s["path"],
                key=str(idx),
            )

    def _show_folder_files(self, path: str) -> None:
        """List files under *path* in the collapsible (SSH-friendly)."""
        widget = self.query_one("#mgr-files-list", Static)
        coll   = self.query_one("#mgr-files-collapsible", Collapsible)

        root = Path(path)
        if not root.exists():
            widget.update(f"  📂  {path}\n  (folder does not exist yet)")
            coll.collapsed = False
            return

        all_files = sorted(root.rglob("*"))
        file_entries = [f for f in all_files if f.is_file()]

        if not file_entries:
            widget.update(f"  📂  {path}\n  (empty — no files downloaded yet)")
            coll.collapsed = False
            return

        lines = [f"  📂  {path}"]
        for i, f in enumerate(file_entries):
            is_last = i == len(file_entries) - 1
            prefix = "  └─ " if is_last else "  ├─ "
            try:
                size_str = _fmt_size(f.stat().st_size)
            except OSError:
                size_str = "?"
            rel = f.relative_to(root)
            lines.append(f"{prefix}{rel}   ({size_str})")

        widget.update("\n".join(lines))
        coll.collapsed = False
        coll.title = f"📂  Files in {root.name}"

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        idx = int(event.row_key.value)
        if 0 <= idx < len(_SESSIONS):
            session = _SESSIONS[idx]
            self._show_folder_files(session["path"])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-delete":
            self._delete_selected()
        elif event.button.id == "btn-back":
            self.action_go_back()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self._refresh_table()
        self.notify("Refreshed", severity="information", timeout=2)

    def _delete_selected(self) -> None:
        table = self.query_one("#mgr-table", DataTable)
        row_key = table.cursor_row
        if row_key is None:
            return
        idx = int(table.get_row_at(row_key)[0] if False else row_key)
        # row_key is the integer cursor index, not the key string
        # Use the key stored during add_row
        try:
            keys = [str(i) for i in range(len(_SESSIONS))]
            sel_key = keys[table.cursor_row]
            sel_idx = int(sel_key)
        except (IndexError, ValueError):
            return

        session = _SESSIONS[sel_idx]

        # Terminate if running
        proc = session.get("process")
        if proc and proc.returncode is None:
            try:
                proc.terminate()
            except Exception:
                pass
        session["status"] = "cancelled"

        self.notify(
            f"Stopped: {session['name'][:40]}",
            severity="warning",
            timeout=3,
        )
        self._refresh_table()
