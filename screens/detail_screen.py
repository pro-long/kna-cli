"""
Detail screen — full torrent information + async file listing.

Shows:
  • All Knaben API metadata fields
  • File tree (fetched first via libtorrent metadata exchange, then HTTP cache)
  • Description (HTML stripped)
  • Editable download path
  • Action buttons: Download / Copy Magnet / Open URL / Back
"""

import datetime
import re
import subprocess

from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual import work
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    Input,
    Label,
    LoadingIndicator,
    Collapsible,
)
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from rich.text import Text

from api.torrent_parser import fetch_file_list
from downloader.libtorrent_meta import fetch_meta_from_magnet
from config import Config


# -----------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------

def fmt_size(b: int) -> str:
    if not b:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def fmt_date(s: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return s or "—"


def fmt_ago(s: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        secs = (now - dt).total_seconds()
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{int(secs/60)}m ago"
        if secs < 86400:
            return f"{int(secs/3600)}h ago"
        return f"{int(secs/86400)}d ago"
    except Exception:
        return "—"


def strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def file_icon(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "mkv": "🎬", "mp4": "🎬", "avi": "🎬", "mov": "🎬", "wmv": "🎬",
        "mp3": "🎵", "flac": "🎵", "aac": "🎵", "wav": "🎵", "ogg": "🎵",
        "iso": "💿", "img": "💿",
        "zip": "📦", "rar": "📦", "7z": "📦", "tar": "📦", "gz": "📦",
        "pdf": "📕", "epub": "📕", "mobi": "📕", "azw3": "📕",
        "exe": "⚙️",  "apk": "📱", "deb": "⚙️",  "rpm": "⚙️",
        "nfo": "📄", "txt": "📄", "md": "📄",
        "srt": "💬", "sub": "💬", "ass": "💬",
        "jpg": "🖼️",  "png": "🖼️",  "jpeg": "🖼️",
    }.get(ext, "📄")


# -----------------------------------------------------------------------
# Screen
# -----------------------------------------------------------------------

class DetailScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("d", "start_download", "Download"),
        Binding("m", "copy_magnet", "Copy Magnet"),
        Binding("o", "open_url", "Open URL"),
        Binding("q", "go_back", "Back"),
    ]

    def __init__(self, torrent: dict, config: Config) -> None:
        super().__init__()
        self.torrent = torrent
        self.config = config

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with ScrollableContainer(id="detail-scroll"):

            # Title
            yield Static(self._render_title(), id="detail-title")

            # Metadata
            with Container(id="meta-box"):
                yield Static("ℹ  Torrent Info", classes="box-header")
                yield Static(self._render_meta(), id="meta-content")

            # File list (collapsible)
            with Container(id="files-box"):
                yield Static("📁  Files in this Torrent", classes="box-header")
                yield LoadingIndicator(id="files-spinner")
                # Collapsible is populated after metadata fetch
                yield Static("", id="files-summary")
                with Collapsible(title="Show files", id="files-collapsible", collapsed=True):
                    yield Static("", id="files-content")

            # Description
            with Container(id="desc-box"):
                yield Static("📝  Description", classes="box-header")
                yield Static(self._render_desc(), id="desc-content")

            # Download path input
            with Container(id="path-box"):
                yield Static("📂  Download Path  (editable)", classes="box-header")
                yield Input(
                    value=self.config.download_path,
                    id="path-input",
                    placeholder="Enter download directory…",
                )

            # Magnet link display
            with Container(id="magnet-box"):
                yield Static("🧲  Magnet Link", classes="box-header")
                magnet = self.torrent.get("magnetUrl", "—")
                yield Static(magnet, id="magnet-content")

            # Action buttons
            with Horizontal(id="detail-actions"):
                yield Button("⬇  Download", id="btn-dl", variant="success")
                yield Button("🌐  Open URL", id="btn-url")
                yield Button("←  Back", id="btn-back", variant="warning")

        yield Footer()

    def on_mount(self) -> None:
        # Hide collapsible until we have files
        self.query_one("#files-collapsible", Collapsible).display = False
        # Kick off async file-list fetch
        self._fetch_files()

    # ------------------------------------------------------------------
    # Async file-list loader
    # ------------------------------------------------------------------

    @work
    async def _fetch_files(self) -> None:
        spinner = self.query_one("#files-spinner", LoadingIndicator)
        summary = self.query_one("#files-summary", Static)
        content = self.query_one("#files-content", Static)
        collapsible = self.query_one("#files-collapsible", Collapsible)

        magnet = self.torrent.get("magnetUrl", "")
        info_hash = self.torrent.get("hash", "")

        files: list[dict] = []

        # ── Step 1: try libtorrent metadata exchange (best source) ──
        if magnet:
            summary.update("  ⏳  Fetching metadata from swarm…")
            try:
                files = await fetch_meta_from_magnet(magnet, timeout=25.0)
            except Exception:
                files = []

        # ── Step 2: fall back to HTTP torrent cache ──
        if not files and info_hash:
            summary.update("  ⏳  Trying torrent cache…")
            try:
                files = await fetch_file_list(info_hash)
            except Exception:
                files = []

        spinner.display = False

        if not files:
            summary.update(
                "  ⚠  File list unavailable — aria2c will display files as it downloads."
            )
            collapsible.display = False
            return

        # Build the summary line
        total = sum(f.get("size", 0) for f in files)
        summary.update(
            f"  {len(files)} file(s)  ·  Total: {fmt_size(total)}"
        )

        # Build collapsible content
        content.update(self._render_files(files))
        collapsible.display = True

    # ------------------------------------------------------------------
    # Renderers
    # ------------------------------------------------------------------

    def _render_title(self) -> Text:
        title = self.torrent.get("title", "Unknown Torrent")
        t = Text()
        t.append("  📄  ", style="cyan bold")
        t.append(title, style="bold bright_white")
        return t

    def _render_meta(self) -> Text:
        trnt = self.torrent
        t = Text()

        def row(label: str, value: str, val_style: str = "bright_white") -> None:
            t.append(f"  {label:<16}", style="dim cyan")
            t.append(f"  {value}\n", style=val_style)

        row("Size", fmt_size(trnt.get("bytes", 0)))

        # Seeders with colour
        s = trnt.get("seeders", 0)
        ls = trnt.get("liveSeeders", 0)
        s_col = "bold green" if s >= 50 else "bold yellow" if s >= 10 else "bold red"
        t.append(f"  {'Seeders':<16}", style="dim cyan")
        t.append(f"  {s}", style=s_col)
        t.append(f"   (Live: {ls})\n", style="dim")

        p = trnt.get("peers", 0)
        lp = trnt.get("livePeers", 0)
        t.append(f"  {'Peers':<16}", style="dim cyan")
        t.append(f"  {p}", style="bright_white")
        t.append(f"   (Live: {lp})\n", style="dim")

        row("Grabs", f"{trnt.get('grabs', 0):,}")
        row("Added", fmt_date(trnt.get("date", "")))
        row("Last Seen", fmt_ago(trnt.get("lastSeen", "")))
        row("Category", trnt.get("category", "—"))
        row("Tracker", trnt.get("tracker", "—"))

        hash_val = trnt.get("hash", "—")
        row("Infohash", hash_val[:40] + ("…" if len(hash_val) > 40 else ""))

        # Virus detection badge
        vd = trnt.get("virusDetection")
        if vd is not None:
            pct = vd * 100
            label = "⚠  Virus Risk"
            if pct < 20:
                t.append(f"  {label:<16}", style="dim cyan")
                t.append(f"  {pct:.1f}%  [LOW]\n", style="green")
            elif pct < 50:
                t.append(f"  {label:<16}", style="dim cyan")
                t.append(f"  ⚠  {pct:.1f}%  [MODERATE]\n", style="yellow")
            else:
                t.append(f"  {label:<16}", style="dim cyan")
                t.append(f"  🚨 {pct:.1f}%  [HIGH — BE CAREFUL]\n", style="bold red")

        return t

    def _render_files(self, files: list[dict]) -> Text:
        t = Text()
        t.append("  " + "─" * 62 + "\n", style="dim")

        for i, f in enumerate(files):
            is_last = i == len(files) - 1
            prefix = "  └─ " if is_last else "  ├─ "
            path = f.get("path", "unknown")
            size = fmt_size(f.get("size", 0))
            icon = file_icon(path)

            t.append(prefix, style="dim")
            t.append(f"{icon} ", style="")
            t.append(path, style="bright_white")
            t.append(f"   {size}\n", style="dim cyan")

        return t

    def _render_desc(self) -> str:
        raw = self.torrent.get("description") or ""
        clean = strip_html(raw)
        return f"  {clean}" if clean else "  No description provided."

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {
            "btn-dl":   self.action_start_download,
            "btn-url":  self.action_open_url,
            "btn-back": self.action_go_back,
        }
        handler = handlers.get(event.button.id)
        if handler:
            handler()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_start_download(self) -> None:
        magnet = self.torrent.get("magnetUrl", "")
        if not magnet:
            self.notify("No magnet link available for this torrent!", severity="error")
            return

        path_input = self.query_one("#path-input", Input)
        dl_path = path_input.value.strip() or self.config.download_path

        from screens.download_screen import DownloadScreen
        self.app.push_screen(
            DownloadScreen(
                torrent=self.torrent,
                magnet_url=magnet,
                download_path=dl_path,
                config=self.config,
            )
        )

    def action_copy_magnet(self) -> None:
        magnet = self.torrent.get("magnetUrl", "")
        if not magnet:
            self.notify("No magnet link available!", severity="error")
            return
        try:
            subprocess.run(
                ["termux-clipboard-set", magnet],
                check=True, capture_output=True, timeout=3,
            )
            self.notify("✅ Magnet link copied to clipboard!", severity="information")
        except Exception:
            self.notify(f"Magnet (truncated): {magnet[:60]}…", severity="information")

    def action_open_url(self) -> None:
        url = self.torrent.get("details", "")
        if not url:
            self.notify("No details URL available.", severity="warning")
            return
        try:
            subprocess.run(["termux-open-url", url], check=True, timeout=3)
            self.notify("Opening in browser…", severity="information")
        except Exception:
            self.notify(f"URL: {url}", severity="information")
