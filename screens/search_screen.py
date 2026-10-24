"""
Search screen — the main landing screen of KnaCLI.

Features:
  - Search bar + filter bar (category, tracker, sort)
  - Async search via Knaben API v2
  - Colour-coded results table (seeders: green/yellow/red)
  - Keyboard-driven navigation
  - Pagination (N / P)
"""

import math
from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual import work, on
from textual.widgets import (
    Header,
    Footer,
    Input,
    DataTable,
    Static,
    Select,
    Button,
    Label,
    LoadingIndicator,
)
from textual.containers import Container, Horizontal, Vertical
from rich.text import Text

from api.knaben import KnabenClient
from config import Config

# -----------------------------------------------------------------------
# Filter options
# -----------------------------------------------------------------------

CATEGORIES: list[tuple[str, str]] = [
    ("All Categories", ""),
    ("Audio", "2000000"),
    ("  ↳ Music", "2001000"),
    ("  ↳ Audiobooks", "2002000"),
    ("Video", "3000000"),
    ("  ↳ Movies", "3001000"),
    ("  ↳ TV Shows", "3002000"),
    ("  ↳ Other Video", "3003000"),
    ("Software", "4000000"),
    ("  ↳ Windows", "4001000"),
    ("  ↳ macOS", "4002000"),
    ("  ↳ Linux/Unix", "4004000"),
    ("  ↳ Android", "4005000"),
    ("Games", "5000000"),
    ("  ↳ PC Games", "5001000"),
    ("  ↳ Android Games", "5004000"),
    ("eBooks", "7000000"),
]

SORT_OPTIONS: list[tuple[str, str]] = [
    ("Seeders ↓", "seeders"),
    ("Peers ↓", "peers"),
    ("Date ↓", "date"),
    ("Grabs ↓", "grabs"),
]

TRACKERS: list[tuple[str, str]] = [
    ("All Trackers", ""),
    ("The Pirate Bay", "thepiratebay"),
    ("1337x", "1337x"),
    ("Nyaa.si", "nyaasi"),
    ("Rutracker", "rutracker"),
]


# -----------------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------------

def fmt_size(b: int) -> str:
    """Convert bytes to human-readable string."""
    if not b:
        return "  —  "
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def fmt_seeders(n: int) -> Text:
    """Colour-code seeder count: green ≥50, yellow ≥10, red <10."""
    t = Text(str(n), justify="right")
    if n >= 50:
        t.stylize("bold green")
    elif n >= 10:
        t.stylize("bold yellow")
    else:
        t.stylize("bold red")
    return t


def truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# -----------------------------------------------------------------------
# Screen
# -----------------------------------------------------------------------

class SearchScreen(Screen):
    BINDINGS = [
        Binding("q", "quit_app", "Quit", priority=True),
        Binding("/", "focus_search", "Search"),
        Binding("enter", "open_detail", "Details"),
        Binding("d", "open_detail", "Download"),
        Binding("m", "copy_magnet", "Magnet"),
        Binding("w", "show_downloads", "Downloads"),
        Binding("n", "next_page", "Next"),
        Binding("p", "prev_page", "Prev"),
        Binding("?", "show_help", "Help"),
    ]

    def __init__(self, config: Config, api: KnabenClient) -> None:
        super().__init__()
        self.config = config
        self.api = api
        self._results: list[dict] = []
        self._total: int = 0
        self._page: int = 0
        self._page_size: int = config.default_results
        self._last_query: str = ""

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="search-main"):

            # — Search bar ——————————————————————————————————————————————
            with Horizontal(id="search-bar"):
                yield Label("🔍", id="search-icon")
                yield Input(
                    placeholder="Search torrents…  (e.g. ubuntu, arch linux, lotr)",
                    id="search-input",
                )
                yield Button("Search", id="btn-search", variant="primary")

            # — Filter bar —————————————————————————————————————————————
            with Horizontal(id="filter-bar"):
                yield Label("Category", classes="filter-label")
                yield Select(
                    [(lbl, val) for lbl, val in CATEGORIES],
                    id="cat-select",
                    allow_blank=False,
                )
                yield Label("Tracker", classes="filter-label")
                yield Select(
                    [(lbl, val) for lbl, val in TRACKERS],
                    id="tracker-select",
                    allow_blank=False,
                )
                yield Label("Sort by", classes="filter-label")
                yield Select(
                    [(lbl, val) for lbl, val in SORT_OPTIONS],
                    id="sort-select",
                    allow_blank=False,
                )

            # — Results area ———————————————————————————————————————————
            with Container(id="results-wrap"):
                yield LoadingIndicator(id="spinner")
                yield DataTable(
                    id="results-table",
                    cursor_type="row",
                    zebra_stripes=True,
                )

            # — Status bar —————————————————————————————————————————————
            yield Static(
                "  Ready — type a query above and press Enter  ·  [?] Help  ·  [Q] Quit",
                id="status-bar",
            )

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.add_columns("#", "Title", "Size", "Seeds", "Peers", "Tracker", "Category")

        self.query_one("#spinner", LoadingIndicator).display = False
        self.query_one("#search-input", Input).focus()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self._start_search()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-search":
            self._start_search()

    def on_data_table_row_selected(self, _: DataTable.RowSelected) -> None:
        self.action_open_detail()

    # ------------------------------------------------------------------
    # Search logic
    # ------------------------------------------------------------------

    def _start_search(self) -> None:
        query = self.query_one("#search-input", Input).value.strip()
        if not query:
            self._set_status("⚠  Please enter a search term")
            return
        self._last_query = query
        self._page = 0
        self._run_search(query)

    @work(exclusive=True)
    async def _run_search(self, query: str) -> None:
        self._set_loading(True)
        self._set_status(f"  Searching for '{query} '…")

        # Read filter values
        cat_val = self.query_one("#cat-select", Select).value
        trk_val = self.query_one("#tracker-select", Select).value
        srt_val = self.query_one("#sort-select", Select).value

        category = "" if cat_val == Select.BLANK else str(cat_val)
        tracker  = "" if trk_val == Select.BLANK else str(trk_val)
        sort     = "seeders" if srt_val == Select.BLANK else str(srt_val)

        try:
            data = await self.api.search(
                query=query,
                category=category,
                tracker=tracker,
                sort=sort,
                direction="desc",
                size=self._page_size,
                offset=self._page * self._page_size,
            )
            self._results = data.get("hits", [])
            total_obj = data.get("total", {})
            self._total = (
                total_obj.get("value", len(self._results))
                if isinstance(total_obj, dict)
                else len(self._results)
            )
            self._populate_table()
        except Exception as exc:
            self._set_status(f"  ❌  Search failed: {exc}")
        finally:
            self._set_loading(False)

    def _populate_table(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear()

        if not self._results:
            self._set_status("  No results found — try different keywords or filters")
            return

        base = self._page * self._page_size
        for idx, t in enumerate(self._results):
            table.add_row(
                Text(str(base + idx + 1), justify="right"),
                Text(truncate(t.get("title", "Unknown"), 48)),
                Text(fmt_size(t.get("bytes", 0)), justify="right"),
                fmt_seeders(t.get("seeders", 0)),
                Text(str(t.get("peers", 0)), justify="right"),
                Text(truncate(t.get("tracker", "?"), 14)),
                Text(truncate(t.get("category", "?"), 18)),
                key=str(idx),
            )

        total_pages = max(1, math.ceil(self._total / self._page_size))
        self._set_status(
            f"  Found {self._total:,} results  ·  Page {self._page + 1}/{total_pages}  ·  "
            f"[↑↓] Navigate  [ENTER] Details  [D] Download  [M] Magnet  [N/P] Pages"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_selected(self) -> dict | None:
        table = self.query_one("#results-table", DataTable)
        if not self._results or table.row_count == 0:
            return None
        row_idx = table.cursor_row
        if 0 <= row_idx < len(self._results):
            return self._results[row_idx]
        return None

    def _set_loading(self, active: bool) -> None:
        self.query_one("#spinner", LoadingIndicator).display = active
        self.query_one("#results-table", DataTable).display = not active

    def _set_status(self, msg: str) -> None:
        self.query_one("#status-bar", Static).update(msg)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_open_detail(self) -> None:
        torrent = self._get_selected()
        if torrent:
            from screens.detail_screen import DetailScreen
            self.app.push_screen(DetailScreen(torrent, self.config))
        else:
            self._set_status("  ⚠  No torrent selected — search first and use ↑↓ to pick a row")

    def action_copy_magnet(self) -> None:
        torrent = self._get_selected()
        if not torrent:
            self._set_status("  ⚠  No torrent selected")
            return
        magnet = torrent.get("magnetUrl", "")
        if not magnet:
            self._set_status("  ⚠  No magnet link available for this torrent")
            return
        import subprocess
        try:
            subprocess.run(
                ["termux-clipboard-set", magnet],
                check=True, capture_output=True, timeout=3,
            )
            self._set_status("  ✅  Magnet link copied to clipboard!")
        except Exception:
            # Fallback: show shortened magnet
            self._set_status(f"  🧲  {magnet[:80]}…")

    def action_show_downloads(self) -> None:
        from screens.download_screen import DownloadManagerScreen
        self.app.push_screen(DownloadManagerScreen(self.config))

    def action_next_page(self) -> None:
        if not self._last_query:
            return
        total_pages = max(1, math.ceil(self._total / self._page_size))
        if self._page + 1 < total_pages:
            self._page += 1
            self._run_search(self._last_query)

    def action_prev_page(self) -> None:
        if not self._last_query or self._page == 0:
            return
        self._page -= 1
        self._run_search(self._last_query)

    def action_show_help(self) -> None:
        self._set_status(
            "  [/] Search  [↑↓] Navigate  [ENTER] Details  [D] Download  "
            "[M] Magnet  [N/P] Pages  [W] Downloads  [Q] Quit"
        )

    def action_quit_app(self) -> None:
        self.app.exit()
