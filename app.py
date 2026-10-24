"""
Main KnaCLI Textual App.

Holds the Textual CSS theme (dark hacker terminal aesthetic) and
initialises shared resources (Config, KnabenClient) passed to screens.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding

from config import Config
from api.knaben import KnabenClient
from screens.search_screen import SearchScreen


# -----------------------------------------------------------------------
# Textual CSS — embedded directly (no .tcss file needed)
# -----------------------------------------------------------------------

APP_CSS = """
/* ── Global ─────────────────────────────────────────────── */
Screen {
    background: #0d1117;
    color: #e6edf3;
}

Header {
    background: #161b22;
    color: #58a6ff;
    text-style: bold;
    height: 1;
}

Footer {
    background: #161b22;
    color: #6e7681;
    height: 1;
}

/* ── Search Screen ───────────────────────────────────────── */
#search-main {
    height: 1fr;
    padding: 0;
}

#search-bar {
    height: 3;
    padding: 0 1;
    align: left middle;
    background: #161b22;
    border-bottom: solid #30363d;
}

#search-icon {
    width: 3;
    color: #58a6ff;
    content-align: center middle;
}

#search-input {
    width: 1fr;
    background: #0d1117;
    color: #e6edf3;
    border: solid #30363d;
    padding: 0 1;
}

#search-input:focus {
    border: solid #58a6ff;
}

#btn-search {
    width: 14;
    margin-left: 1;
    background: #238636;
    color: #ffffff;
    border: none;
    text-style: bold;
}

#btn-search:hover {
    background: #2ea043;
}

#filter-bar {
    height: 3;
    padding: 0 1;
    align: left middle;
    background: #0f1117;
    border-bottom: solid #21262d;
}

.filter-label {
    width: auto;
    margin-right: 1;
    color: #6e7681;
    content-align: center middle;
}

Select {
    margin-right: 2;
    background: #161b22;
    color: #e6edf3;
    border: solid #30363d;
    width: 24;
}

Select:focus {
    border: solid #58a6ff;
}

#results-wrap {
    height: 1fr;
    margin: 0 1;
    border: solid #30363d;
}

LoadingIndicator {
    background: #0d1117;
    color: #58a6ff;
    height: 1fr;
}

DataTable {
    background: #0d1117;
    color: #e6edf3;
    height: 1fr;
}

DataTable > .datatable--header {
    background: #161b22;
    color: #58a6ff;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #1f6feb55;
    color: #ffffff;
}

DataTable > .datatable--hover {
    background: #21262d;
}

#status-bar {
    height: 1;
    padding: 0 1;
    color: #6e7681;
    background: #161b22;
}

/* ── Detail Screen ───────────────────────────────────────── */
#detail-scroll {
    background: #0d1117;
    padding: 1 2;
}

#detail-title {
    padding: 1 0;
    color: #58a6ff;
    text-style: bold;
}

.box-header {
    color: #58a6ff;
    text-style: bold;
    padding: 0 0 0 1;
    background: #161b22;
    border-bottom: solid #30363d;
    height: 1;
}

#meta-box, #files-box, #desc-box, #path-box {
    border: solid #30363d;
    margin-bottom: 1;
    background: #0d1117;
}

#meta-content {
    padding: 1 0;
}

#files-content {
    padding: 1 0;
}

#desc-content {
    padding: 1 0;
    color: #8b949e;
}

#path-box {
    padding-bottom: 1;
}

#path-input {
    margin: 1 1;
    background: #161b22;
    color: #e6edf3;
    border: solid #30363d;
}

#path-input:focus {
    border: solid #58a6ff;
}

#detail-actions {
    height: 3;
    padding: 0 0 1 0;
    align: left middle;
}

#btn-dl {
    background: #238636;
    color: #fff;
    border: none;
    text-style: bold;
    margin-right: 1;
}

#btn-dl:hover {
    background: #2ea043;
}

/* Magnet link display box */
#magnet-box {
    border: solid #30363d;
    margin-bottom: 1;
    background: #0d1117;
}

#magnet-content {
    padding: 1;
    color: #8b949e;
    text-style: italic;
}
#btn-url {
    background: #30363d;
    color: #e6edf3;
    border: none;
    margin-right: 1;
}

#btn-url:hover {
    background: #3d444d;
}

#btn-back {
    background: #6e4000;
    color: #fff;
    border: none;
}

#btn-back:hover {
    background: #9a5a00;
}

/* ── Download Screen ─────────────────────────────────────── */
#dl-main {
    padding: 1 2;
    background: #0d1117;
}

#dl-screen-title {
    color: #58a6ff;
    text-style: bold;
    padding: 0 0 1 0;
}

#dl-card {
    border: solid #30363d;
    padding: 1;
    background: #161b22;
    margin-bottom: 1;
}

#dl-torrent-name {
    color: #e6edf3;
    text-style: bold;
    margin-bottom: 1;
}

#dl-save-path {
    color: #6e7681;
    margin-bottom: 1;
}

#dl-status {
    color: #58a6ff;
    margin-bottom: 1;
}

#dl-progress {
    margin-bottom: 1;
}

#dl-stats {
    height: 1;
    margin-bottom: 1;
}

#dl-stats Static {
    color: #6e7681;
}

#dl-error {
    color: #f85149;
}

/* Live aria2c output log */
#dl-log-box {
    border: solid #30363d;
    margin-bottom: 1;
    height: 8;
}

#dl-log-header {
    color: #58a6ff;
    text-style: bold;
    padding: 0 0 0 1;
    background: #161b22;
    border-bottom: solid #30363d;
    height: 1;
}

#dl-log {
    background: #0d1117;
    color: #6e7681;
    height: 1fr;
    padding: 0 1;
}

#dl-buttons {
    height: 3;
    align: left middle;
    margin-top: 1;
}

#btn-cancel {
    background: #da3633;
    color: #fff;
    border: none;
    margin-right: 1;
}

#btn-pause {
    background: #9e6a03;
    color: #fff;
    border: none;
    margin-right: 1;
}

#btn-pause:hover {
    background: #bb8009;
}

#btn-resume {
    background: #238636;
    color: #fff;
    border: none;
    margin-right: 1;
}

#btn-resume:hover {
    background: #2ea043;
}

/* Collapsible file listings */
#dl-files-collapsible {
    margin-top: 1;
    border: solid #30363d;
    background: #0d1117;
}

#dl-files-list {
    padding: 1;
    color: #e6edf3;
}

/* ── Download Manager Screen ─────────────────────────────── */
#mgr-main {
    padding: 1 2;
    background: #0d1117;
    height: 1fr;
}

#mgr-title {
    color: #58a6ff;
    text-style: bold;
    padding: 0 0 1 0;
}

#mgr-table {
    height: auto;
    max-height: 14;
    border: solid #30363d;
    background: #0d1117;
    margin-bottom: 1;
}

#mgr-files-collapsible {
    border: solid #30363d;
    background: #0d1117;
    margin-bottom: 1;
}

#mgr-files-list {
    padding: 1;
    color: #e6edf3;
}

#mgr-info {
    color: #6e7681;
    padding: 0 0 1 0;
}

#mgr-buttons {
    height: 3;
    align: left middle;
}

#btn-delete {
    background: #da3633;
    color: #fff;
    border: none;
    margin-right: 1;
}

#btn-delete:hover {
    background: #f85149;
}

/* ── Collapsible (global) ─────────────────────────────────── */
Collapsible {
    background: #0d1117;
    border: solid #30363d;
    margin-bottom: 1;
}

Collapsible > CollapsibleTitle {
    background: #161b22;
    color: #58a6ff;
    padding: 0 1;
}

Collapsible > CollapsibleTitle:hover {
    background: #21262d;
}

/* files-box collapsible inside detail screen */
#files-box Collapsible {
    border: none;
    margin: 0;
}

#files-summary {
    padding: 0 1;
    color: #8b949e;
}
"""


# -----------------------------------------------------------------------
# App
# -----------------------------------------------------------------------

class KnaCLI(App):
    """
    🧲 KnaCLI — Torrent Search & Download CLI
    Powered by Knaben API v2  |  Downloads via aria2c
    """

    TITLE = "🧲  KnaCLI"
    SUB_TITLE = "Knaben Torrent Search"
    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = Config()
        self.api_client = KnabenClient()

    def on_mount(self) -> None:
        self.push_screen(SearchScreen(self.config, self.api_client))

    async def on_unmount(self) -> None:
        await self.api_client.close()
