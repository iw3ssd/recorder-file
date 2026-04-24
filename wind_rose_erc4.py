#!/usr/bin/env python3
"""
Wind Rose - ERC 4.0 Rotor Controller (Azimuth Only)
Integrates with SDC (UT4LW) via UDP using GS232B protocol.

Author: IW3SSD
"""

import math
import socket
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

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
# UDP Client for SDC integration
# ---------------------------------------------------------------------------

class UDPRotorClient:
    """Sends / receives GS232B commands to SDC via UDP."""

    def __init__(self, host: str = "127.0.0.1", port: int = 12000):
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

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

    def send_command(self, cmd: bytes) -> bytes | None:
        with self._lock:
            if not self._sock:
                return None
            try:
                self._sock.sendto(cmd, (self.host, self.port))
                data, _ = self._sock.recvfrom(256)
                return data
            except (socket.timeout, OSError):
                return None

    def send_command_no_reply(self, cmd: bytes):
        with self._lock:
            if not self._sock:
                return
            try:
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
            # Target arrowhead
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
        self.create_text(cx, cy + r + 22, text=f"AZ: {self.current_az:.0f}\u00b0",
                         fill=self.LABEL_COLOR,
                         font=("Helvetica", 16, "bold"))


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class WindRoseApp(tk.Tk):
    """Main window: wind rose + controls + UDP config."""

    def __init__(self):
        super().__init__()
        self.title("Wind Rose \u2014 ERC 4.0 Azimuth Controller (GS232B/UDP)")
        self.configure(bg="#0f0f23")
        self.resizable(False, False)

        self.client = UDPRotorClient()
        self.current_az: float = 0.0
        self.target_az: float | None = None
        self._polling = False
        self._poll_thread: threading.Thread | None = None

        self._build_ui()
        self._update_status("Disconnected")

    # ---- UI construction ---------------------------------------------------

    def _build_ui(self):
        main = tk.Frame(self, bg="#0f0f23")
        main.pack(padx=10, pady=10)

        # Left: compass
        left = tk.Frame(main, bg="#0f0f23")
        left.pack(side=tk.LEFT, padx=(0, 10))

        self.compass = WindRoseCanvas(left, size=420)
        self.compass.pack()
        self.compass.set_click_callback(self._on_compass_click)

        # Right: controls
        right = tk.Frame(main, bg="#0f0f23")
        right.pack(side=tk.LEFT, fill=tk.Y)

        self._build_connection_frame(right)
        self._build_direction_frame(right)
        self._build_manual_frame(right)
        self._build_action_frame(right)

        # Status bar
        self.status_var = tk.StringVar(value="Disconnected")
        status_bar = tk.Label(self, textvariable=self.status_var,
                              bg="#16213e", fg="#aaa", anchor=tk.W,
                              font=("Helvetica", 9), padx=8, pady=4)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_connection_frame(self, parent):
        f = tk.LabelFrame(parent, text="Connessione UDP (SDC)",
                          bg="#0f0f23", fg="#eee",
                          font=("Helvetica", 10, "bold"))
        f.pack(fill=tk.X, pady=(0, 8))

        row1 = tk.Frame(f, bg="#0f0f23")
        row1.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(row1, text="Host:", bg="#0f0f23", fg="#ccc",
                 width=6, anchor=tk.W).pack(side=tk.LEFT)
        self.host_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(row1, textvariable=self.host_var, width=16).pack(side=tk.LEFT)

        row2 = tk.Frame(f, bg="#0f0f23")
        row2.pack(fill=tk.X, padx=6, pady=2)
        tk.Label(row2, text="Porta:", bg="#0f0f23", fg="#ccc",
                 width=6, anchor=tk.W).pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="12000")
        tk.Entry(row2, textvariable=self.port_var, width=16).pack(side=tk.LEFT)

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

        # Center STOP button
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

    # ---- Connection --------------------------------------------------------

    def _toggle_connection(self):
        if self.client.connected:
            self._stop_polling()
            self.client.disconnect()
            self.btn_connect.config(text="Connetti", bg="#0f3460")
            self._update_status("Disconnesso")
        else:
            host = self.host_var.get().strip()
            try:
                port = int(self.port_var.get().strip())
            except ValueError:
                messagebox.showerror("Errore", "Porta non valida")
                return
            self.client.host = host
            self.client.port = port
            self.client.connect()
            self.btn_connect.config(text="Disconnetti", bg="#e94560")
            self._update_status(f"Connesso a {host}:{port}")
            self._start_polling()

    # ---- Polling -----------------------------------------------------------

    def _start_polling(self):
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_loop,
                                             daemon=True)
        self._poll_thread.start()

    def _stop_polling(self):
        self._polling = False

    def _poll_loop(self):
        while self._polling:
            az = self.client.query_azimuth()
            if az is not None:
                self.current_az = float(az)
                self.after(0, self._refresh_display)
            time.sleep(1.0)

    def _refresh_display(self):
        self.compass.update_azimuth(self.current_az, self.target_az)

    # ---- Commands ----------------------------------------------------------

    def _on_compass_click(self, angle: int):
        self._go_to(angle)

    def _go_to(self, azimuth: int):
        azimuth = int(azimuth) % 360
        self.target_az = float(azimuth)
        self.compass.update_azimuth(self.current_az, self.target_az)
        if self.client.connected:
            self.client.move_to(azimuth)
            self._update_status(f"Vai a {azimuth}\u00b0")
        else:
            self._update_status(f"Target {azimuth}\u00b0 (non connesso)")

    def _go_manual(self):
        try:
            az = int(self.manual_az_var.get().strip())
        except ValueError:
            messagebox.showerror("Errore", "Inserire un valore numerico 0-360")
            return
        if not 0 <= az <= 360:
            messagebox.showerror("Errore", "Il valore deve essere tra 0 e 360")
            return
        self._go_to(az)

    def _stop_rotor(self):
        self.target_az = None
        self.compass.update_azimuth(self.current_az, self.target_az)
        if self.client.connected:
            self.client.stop()
        self._update_status("STOP")

    def _rotate_ccw(self):
        if self.client.connected:
            self.client.rotate_left()
            self._update_status("Rotazione CCW")
        else:
            self._update_status("Non connesso")

    def _rotate_cw(self):
        if self.client.connected:
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
