#!/usr/bin/env python3
"""
KnaCLI - Torrent Search & Download CLI for Android Termux
Powered by Knaben API v2 (https://api.knaben.org)

Usage:
    python main.py

Keybindings:
    /         Focus search bar
    Up/Down   Navigate results
    ENTER     Open torrent detail
    D         Download selected torrent
    M         Copy magnet link
    W         Open download manager
    N / P     Next / Previous page
    ESC       Go back
    Q         Quit
"""

from app import KnaCLI


if __name__ == "__main__":
    app = KnaCLI()
    app.run()
