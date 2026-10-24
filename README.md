# 🧲 KnaCLI — Torrent Search & Download CLI

A fully interactive terminal UI (TUI) torrent searcher and downloader for **Android Termux**.
Powered by the [Knaben API v2](https://api.knaben.org) and [aria2c](https://aria2.github.io/).

---

## Features

| Feature | Details |
|---|---|
| 🔍 Search | Keyword search via Knaben API v2 |
| 🗂 Filters | Category, Tracker, Sort order |
| 📄 Details | Full torrent info + file listing |
| 📁 File list | Fetched from torrent caches using infohash |
| ⬇️ Download | Direct via aria2c with live progress bar |
| 🧲 Magnet | Copy to clipboard via termux-clipboard-set |
| ⚠️ Virus Risk | Knaben virus-detection score displayed |
| 📄 Pagination | Navigate multi-page results |

---

## Installation (Termux)

```bash
# 1. Copy project to Termux home
cp -r knacli ~/knacli
cd ~/knacli

# 2. Allow storage access (first time only)
termux-setup-storage

# 3. Run the install script
bash install_termux.sh

# 4. Launch!
python main.py
```

Or install manually:
```bash
pkg update && pkg install python aria2
pip install textual httpx rich
python main.py
```

---

## Keybindings

| Key | Action |
|---|---|
| `/` | Focus search bar |
| `↑` / `↓` | Navigate results |
| `Enter` | Open torrent details |
| `D` | Download selected (goes to detail → download) |
| `M` | Copy magnet link to clipboard |
| `W` | Open download manager screen |
| `N` / `P` | Next / Previous page |
| `ESC` | Go back / close panel |
| `Q` | Quit |
| `?` | Show help in status bar |

---

## Project Structure

```
knacli/
├── main.py                   # Entry point
├── app.py                    # Textual App + CSS theme
├── config.py                 # Config (~/.config/knacli/config.json)
├── requirements.txt          # Python deps
├── install_termux.sh         # One-click Termux setup
├── api/
│   ├── knaben.py             # Knaben API v2 async client
│   └── torrent_parser.py     # .torrent fetcher + bencode parser
├── screens/
│   ├── search_screen.py      # Main search + results screen
│   ├── detail_screen.py      # Torrent detail + file list screen
│   └── download_screen.py    # Download progress screen
└── downloader/
    └── aria2c.py             # aria2c subprocess integration
```

---

## Config

Auto-created at `~/.config/knacli/config.json` on first run:

```json
{
  "download_path": "/storage/emulated/0/Downloads/torrent_downloads",
  "default_sort": "seeders",
  "default_results": 50,
  "aria2c_path": "aria2c"
}
```

Edit this file to change defaults, or edit the download path directly in the Detail screen before downloading.

---

## Notes

- **Legal use only** — use for open-source software, Creative Commons content, public domain media, etc.
- `link` field from Knaben is often `null`; the app uses `magnetUrl` exclusively.
- File listing is fetched from `itorrents.org` → `torcache.net` → `btcache.me` (best-effort).
- If file listing is unavailable, you can still download — aria2c will reveal files as it downloads.
- `termux-clipboard-set` and `termux-open-url` require the **Termux:API** app installed from F-Droid.
