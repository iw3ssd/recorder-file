#!/usr/bin/env python3
"""
Contest Online ScoreBoard Viewer
Visualizza i contest a cui un nominativo sta partecipando su contestonlinescore.com

Autore: Devin per IW3SSD
"""
from __future__ import annotations

import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Errore: librerie mancanti. Installa con:")
    print("  pip install requests beautifulsoup4")
    input("Premi Invio per chiudere...")
    sys.exit(1)

BASE_URL = "https://contestonlinescore.com"
SCOREBOARD_URL = f"{BASE_URL}/scoreboard/"
ARCHIVE_URL = f"{BASE_URL}/archive/"

DEFAULT_CALLSIGN = "IW3SSD"
REQUEST_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Scraping helpers
# ---------------------------------------------------------------------------

def fetch_page(url: str, params: dict | None = None) -> str | None:
    """GET a page and return its text, or None on error."""
    try:
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.text
    except requests.RequestException:
        return None


def parse_contest_list(html: str) -> list[dict]:
    """Return [{id, name, status}, ...] from the <select> dropdown."""
    contests = []
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", {"name": "contest_id"})
    if not select:
        return contests
    for opt in select.find_all("option"):
        cid = opt.get("value", "").strip()
        if not cid:
            continue
        raw = opt.get_text(strip=True)
        # Format: "Closed: CQMM DX" or "Coming: ..." or "On air: ..."
        status = ""
        name = raw
        for prefix in ("Closed:", "Coming:", "On air:"):
            if raw.startswith(prefix):
                status = prefix.rstrip(":")
                name = raw[len(prefix):].strip()
                break
        contests.append({"id": cid, "name": name, "status": status})
    return contests


def parse_contest_header(html: str) -> str:
    """Extract contest title + date from the header line."""
    soup = BeautifulSoup(html, "html.parser")
    title_div = soup.find("div", class_="title4")
    if title_div:
        a_tag = title_div.find("a")
        if a_tag:
            return a_tag.get_text(strip=True)
    return ""


def search_callsign_in_scoreboard(html: str, callsign: str) -> list[dict]:
    """
    Search for *callsign* in a scoreboard page.
    Returns list of dicts with keys: rank, call, score, qso, unique, club, category.
    """
    results = []
    call_upper = callsign.upper()
    soup = BeautifulSoup(html, "html.parser")

    # Find all category headers and their following rows
    board = soup.find("board")
    if not board:
        board = soup  # fallback

    current_category = ""
    for tr in board.find_all("tr"):
        # Category header rows have class "title5"
        if "title5" in tr.get("class", []):
            tds = tr.find_all("td")
            if tds:
                current_category = tds[0].get_text(strip=True)
            continue

        # Data rows have class "tbl1" or "tbl2"
        classes = tr.get("class", [])
        if "tbl1" not in classes and "tbl2" not in classes:
            continue

        # Look for callsign link
        a_tag = tr.find("a", href=lambda h: h and "/tools/rate/" in h)
        if not a_tag:
            continue

        call_text = a_tag.get_text(strip=True)
        # Match callsign (may include ops in parens, e.g. "IT9/DK6XZ (E77XZ)")
        if call_upper not in call_text.upper():
            continue

        tds = tr.find_all("td")
        rank = tds[0].get_text(strip=True) if len(tds) > 0 else ""
        score = tds[2].get_text(strip=True) if len(tds) > 2 else ""
        qso = tds[3].get_text(strip=True) if len(tds) > 3 else ""
        unique = tds[4].get_text(strip=True) if len(tds) > 4 else ""
        club = ""
        # Club is usually in one of the later tds
        for td in tds[5:]:
            txt = td.get_text(strip=True)
            if txt and len(txt) > 3 and not txt.startswith("N+") and txt not in ("DX", "WL", "N3", "SD", "SD+"):
                club = txt
                break

        results.append({
            "rank": rank,
            "call": call_text,
            "score": score,
            "qso": qso,
            "unique": unique,
            "club": club,
            "category": current_category,
        })

    return results


def fetch_archive_contests() -> list[dict]:
    """Return list of archived contest entries [{name, date, url}, ...]."""
    html = fetch_page(ARCHIVE_URL)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "contest_id" in href and "archive" in href:
            entries.append({
                "name": a_tag.get_text(strip=True),
                "url": urljoin(BASE_URL, href),
            })
    return entries


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class ContestViewerApp:
    """Main application window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Contest Online ScoreBoard — Viewer")
        self.root.geometry("950x620")
        self.root.configure(bg="#1e1e2e")
        self.root.minsize(800, 500)

        self._build_ui()
        self._searching = False

    # ---- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#1e1e2e")
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4",
                         font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#1e1e2e", foreground="#89b4fa",
                         font=("Segoe UI", 14, "bold"))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("Treeview", background="#313244", foreground="#cdd6f4",
                         fieldbackground="#313244", font=("Segoe UI", 10),
                         rowheight=26)
        style.configure("Treeview.Heading", background="#45475a",
                         foreground="#cdd6f4", font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#585b70")])

        # --- Top frame: callsign entry ---
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=12, pady=(10, 4))

        ttk.Label(top, text="Contest Online ScoreBoard — Viewer",
                  style="Title.TLabel").pack(side=tk.LEFT)

        self.btn_search = ttk.Button(top, text="Cerca", command=self._on_search)
        self.btn_search.pack(side=tk.RIGHT, padx=(6, 0))

        self.entry_call = ttk.Entry(top, width=14, font=("Segoe UI", 12))
        self.entry_call.insert(0, DEFAULT_CALLSIGN)
        self.entry_call.pack(side=tk.RIGHT)
        self.entry_call.bind("<Return>", lambda _: self._on_search())

        ttk.Label(top, text="Nominativo:").pack(side=tk.RIGHT, padx=(0, 4))

        # --- Status bar ---
        self.status_var = tk.StringVar(value="Pronto")
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                               font=("Segoe UI", 9), anchor=tk.W)
        status_bar.pack(fill=tk.X, padx=12, pady=(0, 2))

        # --- Progress bar ---
        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill=tk.X, padx=12, pady=(0, 4))

        # --- Results treeview ---
        cols = ("contest", "status", "category", "rank", "score", "qso", "unique", "club")
        col_headings = {
            "contest": "Contest",
            "status": "Stato",
            "category": "Categoria",
            "rank": "#",
            "score": "Punteggio",
            "qso": "QSO",
            "unique": "Unici",
            "club": "Club",
        }
        col_widths = {
            "contest": 200,
            "status": 70,
            "category": 180,
            "rank": 40,
            "score": 90,
            "qso": 60,
            "unique": 60,
            "club": 180,
        }

        tree_frame = ttk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                 selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=col_headings[c])
            self.tree.column(c, width=col_widths[c], minwidth=30)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Bottom info ---
        bottom = ttk.Frame(self.root)
        bottom.pack(fill=tk.X, padx=12, pady=(0, 8))
        self.lbl_info = ttk.Label(bottom, text="",
                                  font=("Segoe UI", 9, "italic"))
        self.lbl_info.pack(side=tk.LEFT)

        self.btn_open = ttk.Button(bottom, text="Apri nel browser",
                                   command=self._open_in_browser, state=tk.DISABLED)
        self.btn_open.pack(side=tk.RIGHT)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self._contest_urls = {}  # iid -> URL

    # ---- Actions -----------------------------------------------------------

    def _on_search(self) -> None:
        if self._searching:
            return
        callsign = self.entry_call.get().strip().upper()
        if not callsign:
            messagebox.showwarning("Attenzione", "Inserire un nominativo!")
            return
        self.entry_call.delete(0, tk.END)
        self.entry_call.insert(0, callsign)
        self._clear_results()
        self._searching = True
        self.btn_search.configure(state=tk.DISABLED)
        self.status_var.set(f"Ricerca di {callsign} in corso...")
        threading.Thread(target=self._search_worker, args=(callsign,),
                         daemon=True).start()

    def _search_worker(self, callsign: str) -> None:
        """Background thread: scrape each contest for callsign."""
        # 1. Fetch main page to get contest list
        html = fetch_page(SCOREBOARD_URL)
        if not html:
            self.root.after(0, self._search_done,
                            f"Errore: impossibile raggiungere {SCOREBOARD_URL}")
            return

        contests = parse_contest_list(html)
        if not contests:
            self.root.after(0, self._search_done,
                            "Nessun contest trovato sulla pagina.")
            return

        total = len(contests)
        found = 0
        self.root.after(0, lambda: self.progress.configure(maximum=total, value=0))

        for idx, c in enumerate(contests, 1):
            self.root.after(0, lambda i=idx, n=c["name"]:
                            self._update_progress(i, total, n))

            # Skip "Coming" contests — no data yet
            if c["status"] == "Coming":
                continue

            page_html = fetch_page(SCOREBOARD_URL, params={"contest_id": c["id"]})
            if not page_html:
                continue

            hits = search_callsign_in_scoreboard(page_html, callsign)
            for hit in hits:
                found += 1
                url = f"{SCOREBOARD_URL}?contest_id={c['id']}"
                self.root.after(0, self._add_result, c, hit, url)

        msg = (f"Ricerca completata: {callsign} trovato in {found} "
               f"{'contest' if found != 1 else 'contest'} "
               f"(analizzati {total} contest)")
        self.root.after(0, self._search_done, msg)

    def _update_progress(self, current: int, total: int, name: str) -> None:
        self.progress["value"] = current
        self.status_var.set(f"Analisi {current}/{total}: {name}")

    def _search_done(self, msg: str) -> None:
        self._searching = False
        self.btn_search.configure(state=tk.NORMAL)
        self.status_var.set(msg)
        self.progress["value"] = 0

    def _add_result(self, contest: dict, hit: dict, url: str) -> None:
        iid = self.tree.insert("", tk.END, values=(
            contest["name"],
            contest["status"],
            hit["category"],
            hit["rank"],
            hit["score"],
            hit["qso"],
            hit["unique"],
            hit["club"],
        ))
        self._contest_urls[iid] = url

    def _clear_results(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._contest_urls.clear()
        self.lbl_info.configure(text="")
        self.btn_open.configure(state=tk.DISABLED)

    def _on_select(self, _event: object) -> None:
        sel = self.tree.selection()
        if sel:
            self.btn_open.configure(state=tk.NORMAL)
            vals = self.tree.item(sel[0], "values")
            self.lbl_info.configure(
                text=f"{vals[0]} — {vals[2]} — Posizione {vals[3]}")
        else:
            self.btn_open.configure(state=tk.DISABLED)
            self.lbl_info.configure(text="")

    def _open_in_browser(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        url = self._contest_urls.get(sel[0], "")
        if url:
            import webbrowser
            webbrowser.open(url)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    root = tk.Tk()
    ContestViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
