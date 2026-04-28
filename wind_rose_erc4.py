#!/usr/bin/env python3
"""
Wind Rose - ERC 4.0 Rotor Controller (Azimuth Only)
Supports PstRotator (YO3DMU) and direct SDC (UT4LW) via UDP using GS232B.

Features:
  - Interactive wind-rose compass
  - Preset management (save / load / delete named positions)
  - PstRotator UDP integration
  - Status bar with full command log

Author: IW3SSD
"""

import json
import math
import os
import socket
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "WindRoseERC4"
PRESETS_FILE = CONFIG_DIR / "presets.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# ---------------------------------------------------------------------------
# GS232B Protocol helpers
# ---------------------------------------------------------------------------

CARDINAL_DIRS = [
    ("N", 0), ("NE", 45), ("E", 90), ("SE", 135),
    ("S", 180), ("SW", 225), ("W", 270), ("NW", 315),
]


def gs232b_query_azimuth():
    """Return the GS232B command to query current azimuth."""
    return b"C\r"


def gs232b_move_to(azimuth: int):
    """Return the GS232B command to move to a given azimuth (0-360)."""
    azimuth = int(azimuth) % 360
    return f"M{azimuth:03d}\r".encode()


def gs232b_stop():
    """Return the GS232B command to stop rotation."""
    return b"S\r"


def gs232b_rotate_left():
    """Return the GS232B command to rotate left (CCW)."""
    return b"L\r"


def gs232b_rotate_right():
    """Return the GS232B command to rotate right (CW)."""
    return b"R\r"


def gs232b_parse_azimuth(response: bytes) -> int | None:
    """Parse azimuth from GS232B response.

    Expected formats:
      +0xxx   (e.g. +0123)
      AZ=xxx  (e.g. AZ=123)
      xxx     (plain number)
    Returns degrees 0-359 or None on parse failure.
    """
    text = response.decode("ascii", errors="ignore").strip()
    try:
        if text.startswith("+0"):
            return int(text[2:]) % 360
        if text.upper().startswith("AZ="):
            return int(text[3:]) % 360
        if text.isdigit():
            return int(text) % 360
    except (ValueError, IndexError):
        pass
    return None


# ---------------------------------------------------------------------------
# PstRotator Protocol helpers
# ---------------------------------------------------------------------------

def pst_set_azimuth(azimuth: float) -> bytes:
    """Build PstRotator UDP command to set azimuth."""
    return f"<PST>AZ:{azimuth:.1f}</PST>\r\n".encode()


def pst_parse_position(data: bytes) -> float | None:
    """Parse azimuth from PstRotator broadcast.

    PstRotator sends: AZ:xxx.x EL:yyy.y  or  AZ:xxx.x
    """
    text = data.decode("ascii", errors="ignore").strip()
    for part in text.replace("<PST>", "").replace("</PST>", "").split():
        if part.upper().startswith("AZ:"):
            try:
                return float(part[3:]) % 360
            except ValueError:
                pass
    return None


# ---------------------------------------------------------------------------
# Preset manager
# ---------------------------------------------------------------------------

class PresetManager:
    """Manage named azimuth presets stored in a JSON file."""

    def __init__(self, path: Path = PRESETS_FILE):
        self._path = path
        self._presets: dict[str, int] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._presets = {k: int(v) % 360 for k, v in data.items()}
            except (json.JSONDecodeError, ValueError, OSError):
                self._presets = {}

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._presets, f, indent=2, ensure_ascii=False)

    @property
    def presets(self) -> dict[str, int]:
        return dict(self._presets)

    def add(self, name: str, azimuth: int):
        self._presets[name] = int(azimuth) % 360
        self._save()

    def remove(self, name: str):
        self._presets.pop(name, None)
        self._save()

    def get(self, name: str) -> int | None:
        return self._presets.get(name)


# ---------------------------------------------------------------------------
# Settings manager
# ---------------------------------------------------------------------------

class SettingsManager:
    """Persist connection settings."""

    DEFAULTS = {
        "mode": "pstrotator",
        "host": "127.0.0.1",
        "port_pst": 12000,
        "port_gs232": 12000,
    }

    def __init__(self, path: Path = SETTINGS_FILE):
        self._path = path
        self._data: dict = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key: str):
        return self._data.get(key, self.DEFAULTS.get(key))

    def set(self, key: str, value):
        self._data[key] = value


# ---------------------------------------------------------------------------
# UDP Client for SDC / GS232B direct
# ---------------------------------------------------------------------------

class UDPRotorClient:
    """Sends / receives GS232B commands to SDC via UDP."""

    def __init__(self, host: str = "127.0.0.1", port: int = 12000,
                 on_command=None):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._on_command = on_command

    def connect(self):
        with self._lock:
            if self._sock:
                self._sock.close()
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(2.0)

    def disconnect(self):
        with self._lock:
            if self._sock:
                self._sock.close()
                self._sock = None

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def _log(self, direction: str, data: bytes):
        if self._on_command:
            text = data.decode("ascii", errors="replace").strip()
            self._on_command(direction, text)

    def send_command(self, cmd: bytes) -> bytes | None:
        with self._lock:
            if not self._sock:
                return None
            try:
                self._log("TX", cmd)
                self._sock.sendto(cmd, (self.host, self.port))
                data, _ = self._sock.recvfrom(256)
                self._log("RX", data)
                return data
            except (socket.timeout, OSError):
                return None

    def send_command_no_reply(self, cmd: bytes):
        with self._lock:
            if not self._sock:
                return
            try:
                self._log("TX", cmd)
                self._sock.sendto(cmd, (self.host, self.port))
            except OSError:
                pass

    def query_azimuth(self) -> int | None:
        resp = self.send_command(gs232b_query_azimuth())
        if resp is not None:
            return gs232b_parse_azimuth(resp)
        return None

    def move_to(self, azimuth: int):
        self.send_command_no_reply(gs232b_move_to(azimuth))

    def stop(self):
        self.send_command_no_reply(gs232b_stop())

    def rotate_left(self):
        self.send_command_no_reply(gs232b_rotate_left())

    def rotate_right(self):
        self.send_command_no_reply(gs232b_rotate_right())


# ---------------------------------------------------------------------------
# PstRotator UDP Client
# ---------------------------------------------------------------------------

class PstRotatorClient:
    """Communicate with PstRotator via its UDP interface."""

    def __init__(self, host: str = "127.0.0.1", port: int = 12000,
                 on_command=None):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._on_command = on_command

    def connect(self):
        with self._lock:
            if self._sock:
                self._sock.close()
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.settimeout(2.0)

    def disconnect(self):
        with self._lock:
            if self._sock:
                self._sock.close()
                self._sock = None

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def _log(self, direction: str, data: bytes):
        if self._on_command:
            text = data.decode("ascii", errors="replace").strip()
            self._on_command(direction, text)

    def send_raw(self, data: bytes) -> bytes | None:
        with self._lock:
            if not self._sock:
                return None
            try:
                self._log("TX", data)
                self._sock.sendto(data, (self.host, self.port))
                resp, _ = self._sock.recvfrom(512)
                self._log("RX", resp)
                return resp
            except (socket.timeout, OSError):
                return None

    def send_no_reply(self, data: bytes):
        with self._lock:
            if not self._sock:
                return
            try:
                self._log("TX", data)
                self._sock.sendto(data, (self.host, self.port))
            except OSError:
                pass

    def query_azimuth(self) -> float | None:
        resp = self.send_raw(b"<PST>AZ?</PST>\r\n")
        if resp is not None:
            az = pst_parse_position(resp)
            if az is not None:
                return az
        # Fallback: try GS232B C command
        resp = self.send_raw(gs232b_query_azimuth())
        if resp is not None:
            val = gs232b_parse_azimuth(resp)
            if val is not None:
                return float(val)
            az = pst_parse_position(resp)
            if az is not None:
                return az
        return None

    def move_to(self, azimuth: int):
        self.send_no_reply(pst_set_azimuth(float(azimuth)))

    def stop(self):
        self.send_no_reply(b"<PST>STOP</PST>\r\n")

    def rotate_left(self):
        self.send_no_reply(gs232b_rotate_left())

    def rotate_right(self):
        self.send_no_reply(gs232b_rotate_right())


# ---------------------------------------------------------------------------
# Wind Rose Canvas
# ---------------------------------------------------------------------------

class WindRoseCanvas(tk.Canvas):
    """Draws a compass rose and shows rotor azimuth."""

    BG = "#1a1a2e"
    RING_COLOR = "#16213e"
    TICK_COLOR = "#e2e2e2"
    LABEL_COLOR = "#eee"
    NEEDLE_COLOR = "#e94560"
    TARGET_COLOR = "#0f3460"
    CARDINAL_COLOR = "#e94560"
    INTERCARDINAL_COLOR = "#f5a623"

    def __init__(self, master, size=420, **kw):
        super().__init__(master, width=size, height=size,
                         bg=self.BG, highlightthickness=0, **kw)
        self.size = size
        self.cx = size / 2
        self.cy = size / 2
        self.radius = size / 2 - 30
        self.current_az: float = 0.0
        self.target_az: float | None = None
        self._on_click_cb = None
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def set_click_callback(self, cb):
        self._on_click_cb = cb

    def _on_click(self, event):
        dx = event.x - self.cx
        dy = event.y - self.cy
        dist = math.hypot(dx, dy)
        if dist > self.radius + 15:
            return
        angle_rad = math.atan2(dx, -dy)
        angle_deg = math.degrees(angle_rad) % 360
        if self._on_click_cb:
            self._on_click_cb(round(angle_deg))

    def update_azimuth(self, az: float, target: float | None = None):
        self.current_az = az
        self.target_az = target
        self._draw()

    def _draw(self):
        self.delete("all")
        cx, cy, r = self.cx, self.cy, self.radius

        # Outer ring
        self.create_oval(cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8,
                         outline=self.RING_COLOR, width=4)
        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                         outline=self.TICK_COLOR, width=2)

        # Degree ticks
        for deg in range(0, 360, 5):
            rad = math.radians(deg - 90)
            is_major = deg % 30 == 0
            is_cardinal = deg % 90 == 0
            inner = r - (18 if is_cardinal else 12 if is_major else 6)
            x1 = cx + inner * math.cos(rad + math.pi / 2)
            y1 = cy + inner * math.sin(rad + math.pi / 2)
            x2 = cx + r * math.cos(rad + math.pi / 2)
            y2 = cy + r * math.sin(rad + math.pi / 2)
            w = 2 if is_major else 1
            self.create_line(x1, y1, x2, y2, fill=self.TICK_COLOR, width=w)

        # Degree numbers every 30 degrees
        for deg in range(0, 360, 30):
            rad = math.radians(deg)
            nr = r - 28
            x = cx + nr * math.sin(rad)
            y = cy - nr * math.cos(rad)
            self.create_text(x, y, text=str(deg), fill=self.TICK_COLOR,
                             font=("Helvetica", 8))

        # Cardinal & intercardinal labels
        for name, deg in CARDINAL_DIRS:
            rad = math.radians(deg)
            lr = r + 18
            x = cx + lr * math.sin(rad)
            y = cy - lr * math.cos(rad)
            is_card = deg % 90 == 0
            color = self.CARDINAL_COLOR if is_card else self.INTERCARDINAL_COLOR
            font_size = 14 if is_card else 10
            self.create_text(x, y, text=name, fill=color,
                             font=("Helvetica", font_size, "bold"))

        # Target line (dashed)
        if self.target_az is not None:
            t_rad = math.radians(self.target_az)
            tx = cx + (r - 20) * math.sin(t_rad)
            ty = cy - (r - 20) * math.cos(t_rad)
            self.create_line(cx, cy, tx, ty, fill=self.TARGET_COLOR,
                             width=3, dash=(6, 4))
            self.create_oval(tx - 5, ty - 5, tx + 5, ty + 5,
                             fill=self.TARGET_COLOR, outline="")

        # Current azimuth needle
        az_rad = math.radians(self.current_az)
        nx = cx + (r - 20) * math.sin(az_rad)
        ny = cy - (r - 20) * math.cos(az_rad)
        self.create_line(cx, cy, nx, ny, fill=self.NEEDLE_COLOR,
                         width=3, arrow=tk.LAST, arrowshape=(12, 15, 5))

        # Center dot
        self.create_oval(cx - 6, cy - 6, cx + 6, cy + 6,
                         fill=self.NEEDLE_COLOR, outline="")

        # Azimuth readout
        self.create_text(cx, cy + r + 22,
                         text=f"AZ: {self.current_az:.0f}\u00b0",
                         fill=self.LABEL_COLOR,
                         font=("Helvetica", 16, "bold"))


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class WindRoseApp(tk.Tk):
    """Main window: wind rose + controls + presets + command log."""

    MAX_LOG_LINES = 200

    def __init__(self):
        super().__init__()
        self.title("Wind Rose \u2014 ERC 4.0 / PstRotator Controller")
        self.configure(bg="#0f0f23")
        self.resizable(False, False)

        self.settings = SettingsManager()
        self.preset_mgr = PresetManager()
        self.client: UDPRotorClient | PstRotatorClient | None = None
        self.current_az: float = 0.0
        self.target_az: float | None = None
        self._polling = False
        self._poll_thread: threading.Thread | None = None
        self._cmd_log: list[str] = []

        self._build_ui()
        self._restore_settings()
        self._update_status("Disconnesso")

    # ---- UI construction ---------------------------------------------------

    def _build_ui(self):
        top = tk.Frame(self, bg="#0f0f23")
        top.pack(padx=10, pady=(10, 0), fill=tk.BOTH)

        # Left: compass
        left = tk.Frame(top, bg="#0f0f23")
        left.pack(side=tk.LEFT, padx=(0, 10))

        self.compass = WindRoseCanvas(left, size=420)
        self.compass.pack()
        self.compass.set_click_callback(self._on_compass_click)

        # Right: controls
        right = tk.Frame(top, bg="#0f0f23")
        right.pack(side=tk.LEFT, fill=tk.Y)

        self._build_connection_frame(right)
        self._build_direction_frame(right)
        self._build_manual_frame(right)
        self._build_action_frame(right)
        self._build_preset_frame(right)

        # Command log (bottom area)
        log_frame = tk.LabelFrame(self, text="Log Comandi",
                                  bg="#0f0f23", fg="#eee",
                                  font=("Helvetica", 10, "bold"))
        log_frame.pack(fill=tk.X, padx=10, pady=(6, 0))

        self.cmd_log_text = tk.Text(log_frame, height=5, bg="#0d0d1a",
                                    fg="#00ff88", font=("Consolas", 9),
                                    state=tk.DISABLED, wrap=tk.WORD,
                                    borderwidth=0, highlightthickness=0)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL,
                                   command=self.cmd_log_text.yview)
        self.cmd_log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.cmd_log_text.pack(fill=tk.X, padx=4, pady=4)

        # Status bar
        self.status_var = tk.StringVar(value="Disconnesso")
        status_bar = tk.Label(self, textvariable=self.status_var,
                              bg="#16213e", fg="#aaa", anchor=tk.W,
                              font=("Helvetica", 9), padx=8, pady=4)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))

    def _build_connection_frame(self, parent):
        f = tk.LabelFrame(parent, text="Connessione",
                          bg="#0f0f23", fg="#eee",
                          font=("Helvetica", 10, "bold"))
        f.pack(fill=tk.X, pady=(0, 8))

        # Mode selector
        row_mode = tk.Frame(f, bg="#0f0f23")
        row_mode.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(row_mode, text="Modo:", bg="#0f0f23", fg="#ccc",
                 width=6, anchor=tk.W).pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="pstrotator")
        modes = [("PstRotator", "pstrotator"), ("GS232B/SDC", "gs232b")]
        for text, val in modes:
            tk.Radiobutton(row_mode, text=text, variable=self.mode_var,
                           value=val, bg="#0f0f23", fg="#ccc",
                           selectcolor="#16213e",
                           activebackground="#0f0f23",
                           activeforeground="#fff").pack(side=tk.LEFT, padx=2)

        # Host
        row1 = tk.Frame(f, bg="#0f0f23")
        row1.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(row1, text="Host:", bg="#0f0f23", fg="#ccc",
                 width=6, anchor=tk.W).pack(side=tk.LEFT)
        self.host_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(row1, textvariable=self.host_var, width=16).pack(side=tk.LEFT)

        # Port
        row2 = tk.Frame(f, bg="#0f0f23")
        row2.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(row2, text="Porta:", bg="#0f0f23", fg="#ccc",
                 width=6, anchor=tk.W).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="12000")
        tk.Entry(row2, textvariable=self.port_var, width=16).pack(side=tk.LEFT)

        # Connect button
        row3 = tk.Frame(f, bg="#0f0f23")
        row3.pack(fill=tk.X, padx=6, pady=(4, 6))
        self.btn_connect = tk.Button(row3, text="Connetti",
                                     command=self._toggle_connection,
                                     bg="#0f3460", fg="white",
                                     activebackground="#1a5276",
                                     width=12)
        self.btn_connect.pack(side=tk.LEFT, padx=(0, 4))

    def _build_direction_frame(self, parent):
        f = tk.LabelFrame(parent, text="Rosa dei Venti",
                          bg="#0f0f23", fg="#eee",
                          font=("Helvetica", 10, "bold"))
        f.pack(fill=tk.X, pady=(0, 8))

        grid = tk.Frame(f, bg="#0f0f23")
        grid.pack(padx=6, pady=6)

        positions = {
            "NW": (0, 0), "N": (0, 1), "NE": (0, 2),
            "W": (1, 0), "E": (1, 2),
            "SW": (2, 0), "S": (2, 1), "SE": (2, 2),
        }
        dir_angles = dict(CARDINAL_DIRS)

        for name, (r, c) in positions.items():
            angle = dir_angles[name]
            btn = tk.Button(grid, text=name, width=4,
                            bg="#16213e", fg="white",
                            activebackground="#1a5276",
                            font=("Helvetica", 10, "bold"),
                            command=lambda a=angle: self._go_to(a))
            btn.grid(row=r, column=c, padx=3, pady=3)

        btn_stop = tk.Button(grid, text="STOP", width=4,
                             bg="#e94560", fg="white",
                             activebackground="#c0392b",
                             font=("Helvetica", 10, "bold"),
                             command=self._stop_rotor)
        btn_stop.grid(row=1, column=1, padx=3, pady=3)

    def _build_manual_frame(self, parent):
        f = tk.LabelFrame(parent, text="Azimut Manuale",
                          bg="#0f0f23", fg="#eee",
                          font=("Helvetica", 10, "bold"))
        f.pack(fill=tk.X, pady=(0, 8))

        row = tk.Frame(f, bg="#0f0f23")
        row.pack(fill=tk.X, padx=6, pady=6)

        self.manual_az_var = tk.StringVar(value="0")
        tk.Entry(row, textvariable=self.manual_az_var, width=6,
                 font=("Helvetica", 12)).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(row, text="\u00b0", bg="#0f0f23", fg="#ccc",
                 font=("Helvetica", 12)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(row, text="VAI", command=self._go_manual,
                  bg="#0f3460", fg="white",
                  activebackground="#1a5276",
                  font=("Helvetica", 10, "bold"),
                  width=6).pack(side=tk.LEFT)

    def _build_action_frame(self, parent):
        f = tk.LabelFrame(parent, text="Rotazione Manuale",
                          bg="#0f0f23", fg="#eee",
                          font=("Helvetica", 10, "bold"))
        f.pack(fill=tk.X, pady=(0, 8))

        row = tk.Frame(f, bg="#0f0f23")
        row.pack(padx=6, pady=6)

        tk.Button(row, text="\u25c0 CCW", command=self._rotate_ccw,
                  bg="#16213e", fg="white",
                  activebackground="#1a5276",
                  font=("Helvetica", 10),
                  width=8).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(row, text="CW \u25b6", command=self._rotate_cw,
                  bg="#16213e", fg="white",
                  activebackground="#1a5276",
                  font=("Helvetica", 10),
                  width=8).pack(side=tk.LEFT)

    # ---- Preset UI ---------------------------------------------------------

    def _build_preset_frame(self, parent):
        f = tk.LabelFrame(parent, text="Preset (UTP)",
                          bg="#0f0f23", fg="#eee",
                          font=("Helvetica", 10, "bold"))
        f.pack(fill=tk.X, pady=(0, 8))

        # Listbox with presets
        list_frame = tk.Frame(f, bg="#0f0f23")
        list_frame.pack(fill=tk.X, padx=6, pady=(4, 2))

        self.preset_listbox = tk.Listbox(list_frame, height=5,
                                         bg="#0d0d1a", fg="#ccc",
                                         selectbackground="#0f3460",
                                         selectforeground="white",
                                         font=("Helvetica", 9),
                                         borderwidth=1,
                                         highlightthickness=0)
        self.preset_listbox.pack(fill=tk.X, side=tk.LEFT, expand=True)

        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                               command=self.preset_listbox.yview)
        self.preset_listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Add preset row
        add_row = tk.Frame(f, bg="#0f0f23")
        add_row.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(add_row, text="Nome:", bg="#0f0f23", fg="#ccc",
                 font=("Helvetica", 9)).pack(side=tk.LEFT)
        self.preset_name_var = tk.StringVar()
        tk.Entry(add_row, textvariable=self.preset_name_var, width=10,
                 font=("Helvetica", 9)).pack(side=tk.LEFT, padx=2)
        tk.Label(add_row, text="Az:", bg="#0f0f23", fg="#ccc",
                 font=("Helvetica", 9)).pack(side=tk.LEFT)
        self.preset_az_var = tk.StringVar(value="0")
        tk.Entry(add_row, textvariable=self.preset_az_var, width=5,
                 font=("Helvetica", 9)).pack(side=tk.LEFT, padx=2)

        # Buttons row
        btn_row = tk.Frame(f, bg="#0f0f23")
        btn_row.pack(fill=tk.X, padx=6, pady=(2, 6))

        tk.Button(btn_row, text="Salva", command=self._preset_save,
                  bg="#0f3460", fg="white", activebackground="#1a5276",
                  font=("Helvetica", 9), width=6).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="Vai", command=self._preset_go,
                  bg="#0f3460", fg="white", activebackground="#1a5276",
                  font=("Helvetica", 9), width=6).pack(side=tk.LEFT, padx=1)
        tk.Button(btn_row, text="Elimina", command=self._preset_delete,
                  bg="#e94560", fg="white", activebackground="#c0392b",
                  font=("Helvetica", 9), width=6).pack(side=tk.LEFT, padx=1)

        self._refresh_preset_list()

    def _refresh_preset_list(self):
        self.preset_listbox.delete(0, tk.END)
        for name, az in sorted(self.preset_mgr.presets.items()):
            self.preset_listbox.insert(tk.END, f"{name}  \u2192  {az}\u00b0")

    def _preset_save(self):
        name = self.preset_name_var.get().strip()
        if not name:
            messagebox.showwarning("Preset", "Inserire un nome per il preset")
            return
        try:
            az = int(self.preset_az_var.get().strip())
        except ValueError:
            messagebox.showerror("Preset", "Azimut non valido")
            return
        if not 0 <= az <= 360:
            messagebox.showerror("Preset", "Azimut tra 0 e 360")
            return
        self.preset_mgr.add(name, az)
        self._refresh_preset_list()
        self._log_command("SYS", f"Preset '{name}' salvato a {az}\u00b0")

    def _preset_delete(self):
        sel = self.preset_listbox.curselection()
        if not sel:
            messagebox.showinfo("Preset", "Selezionare un preset da eliminare")
            return
        text = self.preset_listbox.get(sel[0])
        name = text.split("\u2192")[0].strip()
        self.preset_mgr.remove(name)
        self._refresh_preset_list()
        self._log_command("SYS", f"Preset '{name}' eliminato")

    def _preset_go(self):
        sel = self.preset_listbox.curselection()
        if not sel:
            messagebox.showinfo("Preset", "Selezionare un preset")
            return
        text = self.preset_listbox.get(sel[0])
        name = text.split("\u2192")[0].strip()
        az = self.preset_mgr.get(name)
        if az is not None:
            self._go_to(az)

    # ---- Settings persistence ----------------------------------------------

    def _restore_settings(self):
        self.mode_var.set(self.settings.get("mode"))
        self.host_var.set(self.settings.get("host"))
        mode = self.mode_var.get()
        if mode == "pstrotator":
            self.port_var.set(str(self.settings.get("port_pst")))
        else:
            self.port_var.set(str(self.settings.get("port_gs232")))

    def _persist_settings(self):
        mode = self.mode_var.get()
        self.settings.set("mode", mode)
        self.settings.set("host", self.host_var.get().strip())
        port_key = "port_pst" if mode == "pstrotator" else "port_gs232"
        try:
            self.settings.set(port_key, int(self.port_var.get().strip()))
        except ValueError:
            pass
        self.settings.save()

    # ---- Command log -------------------------------------------------------

    def _log_command(self, direction: str, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {direction}: {text}"
        self._cmd_log.append(line)
        if len(self._cmd_log) > self.MAX_LOG_LINES:
            self._cmd_log = self._cmd_log[-self.MAX_LOG_LINES:]
        self.after(0, self._append_log_line, line)

    def _append_log_line(self, line: str):
        self.cmd_log_text.configure(state=tk.NORMAL)
        self.cmd_log_text.insert(tk.END, line + "\n")
        self.cmd_log_text.see(tk.END)
        self.cmd_log_text.configure(state=tk.DISABLED)
        # Also update status bar with last command
        self.status_var.set(line)

    def _on_protocol_command(self, direction: str, text: str):
        """Callback invoked by the client for every TX/RX."""
        self._log_command(direction, text)

    # ---- Connection --------------------------------------------------------

    def _toggle_connection(self):
        if self.client and self.client.connected:
            self._stop_polling()
            self.client.disconnect()
            self.client = None
            self.btn_connect.config(text="Connetti", bg="#0f3460")
            self._update_status("Disconnesso")
            self._persist_settings()
        else:
            host = self.host_var.get().strip()
            try:
                port = int(self.port_var.get().strip())
            except ValueError:
                messagebox.showerror("Errore", "Porta non valida")
                return
            mode = self.mode_var.get()
            if mode == "pstrotator":
                self.client = PstRotatorClient(host, port,
                                               on_command=self._on_protocol_command)
            else:
                self.client = UDPRotorClient(host, port,
                                             on_command=self._on_protocol_command)
            self.client.connect()
            self.btn_connect.config(text="Disconnetti", bg="#e94560")
            self._update_status(
                f"Connesso [{mode.upper()}] a {host}:{port}")
            self._log_command("SYS",
                              f"Connessione {mode.upper()} a {host}:{port}")
            self._persist_settings()
            self._start_polling()

    # ---- Polling -----------------------------------------------------------

    def _start_polling(self):
        self._stop_event = threading.Event()
        self._poll_thread = threading.Thread(target=self._poll_loop,
                                             args=(self._stop_event,),
                                             daemon=True)
        self._polling = True
        self._poll_thread.start()

    def _stop_polling(self):
        self._polling = False
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
        if hasattr(self, "_poll_thread") and self._poll_thread \
                and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=3.0)

    def _poll_loop(self, stop_event: threading.Event):
        while not stop_event.is_set():
            if self.client and self.client.connected:
                az = self.client.query_azimuth()
                if az is not None:
                    self.current_az = float(az)
                    self.after(0, self._refresh_display)
            stop_event.wait(1.0)

    def _refresh_display(self):
        self.compass.update_azimuth(self.current_az, self.target_az)

    # ---- Commands ----------------------------------------------------------

    def _on_compass_click(self, angle: int):
        self._go_to(angle)

    def _go_to(self, azimuth: int):
        azimuth = int(azimuth) % 360
        self.target_az = float(azimuth)
        self.compass.update_azimuth(self.current_az, self.target_az)
        if self.client and self.client.connected:
            self.client.move_to(azimuth)
            self._update_status(f"Vai a {azimuth}\u00b0")
        else:
            self._update_status(f"Target {azimuth}\u00b0 (non connesso)")

    def _go_manual(self):
        try:
            az = int(self.manual_az_var.get().strip())
        except ValueError:
            messagebox.showerror("Errore",
                                 "Inserire un valore numerico 0-360")
            return
        if not 0 <= az <= 360:
            messagebox.showerror("Errore",
                                 "Il valore deve essere tra 0 e 360")
            return
        self._go_to(az)

    def _stop_rotor(self):
        self.target_az = None
        self.compass.update_azimuth(self.current_az, self.target_az)
        if self.client and self.client.connected:
            self.client.stop()
        self._update_status("STOP")

    def _rotate_ccw(self):
        if self.client and self.client.connected:
            self.client.rotate_left()
            self._update_status("Rotazione CCW")
        else:
            self._update_status("Non connesso")

    def _rotate_cw(self):
        if self.client and self.client.connected:
            self.client.rotate_right()
            self._update_status("Rotazione CW")
        else:
            self._update_status("Non connesso")

    # ---- Helpers -----------------------------------------------------------

    def _update_status(self, msg: str):
        self.status_var.set(msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = WindRoseApp()
    app.mainloop()
