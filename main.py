"""
Crypto Scanner – Android App
Blockscout public API (bez klucza, bez Selenium)
Sieci: Ethereum, Arbitrum, Polygon, Base
"""

import re
import csv
import threading
from datetime import datetime, timezone
from os.path import join

import requests
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivymd.uix.snackbar import Snackbar

# ── Networks ──────────────────────────────────────────────────────────────────

NETWORKS = {
    "ETH":  {"name": "Ethereum",  "api": "https://eth.blockscout.com/api/v2",       "symbol": "ETH",   "color": "#627EEA"},
    "ARB":  {"name": "Arbitrum",  "api": "https://arbitrum.blockscout.com/api/v2",  "symbol": "ETH",   "color": "#28A0F0"},
    "POL":  {"name": "Polygon",   "api": "https://polygon.blockscout.com/api/v2",   "symbol": "POL",   "color": "#8247E5"},
    "BASE": {"name": "Base",      "api": "https://base.blockscout.com/api/v2",      "symbol": "ETH",   "color": "#0052FF"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ── Scraper ───────────────────────────────────────────────────────────────────

def wei_to_eth(wei_str: str, decimals: int = 18) -> str:
    try:
        val = int(wei_str) / (10 ** decimals)
        return f"{val:.6f}".rstrip("0").rstrip(".")
    except Exception:
        return "?"


def fmt_time(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts[:16] if ts else "?"


def fetch_transactions(address: str, net_key: str, max_pages: int,
                        on_row, on_status, on_progress, on_done, stop: threading.Event):
    net = NETWORKS[net_key]
    base_url = f"{net['api']}/addresses/{address}/transactions"
    symbol = net["symbol"]
    all_rows = []
    page_params = None
    page = 0

    try:
        on_status("Łączę z API…")
        while True:
            if stop.is_set():
                on_status(f"Zatrzymano – {len(all_rows)} transakcji.")
                break

            params = {"filter": "to | from"}
            if page_params:
                params.update(page_params)

            try:
                resp = requests.get(base_url, params=params, headers=HEADERS, timeout=20)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                on_status(f"Błąd sieci: {e}")
                break

            items = data.get("items", [])
            if not items:
                break

            for tx in items:
                frm  = (tx.get("from") or {}).get("hash", "")
                to   = (tx.get("to")   or {}).get("hash", "")
                fee  = wei_to_eth((tx.get("fee") or {}).get("value", "0"))
                val  = wei_to_eth(tx.get("value", "0"))
                ts   = fmt_time(tx.get("timestamp", ""))
                meth = tx.get("method") or tx.get("type", "transfer")
                status = "OK" if tx.get("status") == "ok" else tx.get("status", "?")

                row = {
                    "Hash":    tx.get("hash", ""),
                    "Metoda":  meth,
                    "Blok":    str(tx.get("block", "")),
                    "Data":    ts,
                    "Od":      frm,
                    "Do":      to,
                    "Wartość": f"{val} {symbol}",
                    "Opłata":  f"{fee} {symbol}",
                    "Status":  status,
                }
                all_rows.append(row)
                on_row(row)

            page += 1
            on_progress(page, len(all_rows))
            on_status(f"Pobrano {len(all_rows)} transakcji…")

            page_params = data.get("next_page_params")
            if not page_params:
                break
            if max_pages > 0 and page >= max_pages:
                break

    except Exception as e:
        on_status(f"Błąd: {e}")
    finally:
        on_done(all_rows)


# ── KV Layout ─────────────────────────────────────────────────────────────────

KV = """
<TxCard>:
    orientation: "vertical"
    padding: dp(14), dp(10)
    spacing: dp(4)
    size_hint_y: None
    height: dp(90)
    md_bg_color: app.card_color
    radius: [dp(10)]
    ripple_behavior: True
    on_release: app.show_detail(self.tx_data)

    MDBoxLayout:
        spacing: dp(8)
        size_hint_y: None
        height: dp(22)

        MDLabel:
            id: method_lbl
            text: root.method
            font_style: "Caption"
            bold: True
            theme_text_color: "Custom"
            text_color: app.accent_color
            size_hint_x: None
            width: dp(100)

        MDLabel:
            text: root.date
            font_style: "Caption"
            theme_text_color: "Custom"
            text_color: app.sub_color
            halign: "right"

    MDLabel:
        text: root.hash_short
        font_style: "Caption"
        font_name: "RobotoMono"
        theme_text_color: "Custom"
        text_color: app.sub_color

    MDBoxLayout:
        spacing: dp(8)
        size_hint_y: None
        height: dp(22)

        MDLabel:
            text: root.value
            font_style: "Body2"
            bold: True
            theme_text_color: "Custom"
            text_color: app.text_color

        MDLabel:
            text: root.status
            font_style: "Caption"
            theme_text_color: "Custom"
            text_color: app.status_color(root.status)
            halign: "right"


MDScreen:
    name: "main"
    md_bg_color: app.bg_color

    MDBoxLayout:
        orientation: "vertical"

        # ── Top bar ──────────────────────────────────────────────────────────
        MDTopAppBar:
            id: top_bar
            title: "Crypto Scanner"
            md_bg_color: app.surface_color
            specific_text_color: app.text_color
            right_action_items: [["export", lambda x: app.export_csv()]]

        # ── Input panel ──────────────────────────────────────────────────────
        MDCard:
            orientation: "vertical"
            padding: dp(12), dp(8)
            spacing: dp(8)
            size_hint_y: None
            height: dp(180)
            md_bg_color: app.surface_color
            radius: [0]
            elevation: 2

            # Network chips
            MDBoxLayout:
                spacing: dp(6)
                size_hint_y: None
                height: dp(36)
                id: chip_row

            # Address field
            MDTextField:
                id: addr_field
                hint_text: "Adres portfela (0x…)"
                mode: "rectangle"
                hint_text_color_normal: app.sub_color
                text_color_normal: app.text_color
                line_color_normal: app.border_color
                line_color_focus: app.accent_color
                font_name: "RobotoMono"
                on_text_validate: app.start_fetch()

            # Controls row
            MDBoxLayout:
                spacing: dp(8)
                size_hint_y: None
                height: dp(42)

                MDRaisedButton:
                    id: btn_fetch
                    text: "▶  Pobierz"
                    md_bg_color: app.green_color
                    on_release: app.start_fetch()

                MDRaisedButton:
                    id: btn_stop
                    text: "■  Stop"
                    md_bg_color: app.border_color
                    disabled: True
                    on_release: app.stop_fetch()

                MDTextField:
                    id: pages_field
                    hint_text: "Stron (0=∞)"
                    text: "0"
                    mode: "rectangle"
                    size_hint_x: None
                    width: dp(90)
                    hint_text_color_normal: app.sub_color
                    text_color_normal: app.text_color
                    line_color_normal: app.border_color
                    line_color_focus: app.accent_color
                    input_filter: "int"

        # ── Progress bar ─────────────────────────────────────────────────────
        MDProgressBar:
            id: progress_bar
            value: 0
            color: app.accent_color

        # ── Stats strip ──────────────────────────────────────────────────────
        MDBoxLayout:
            size_hint_y: None
            height: dp(28)
            padding: dp(12), 0
            md_bg_color: app.surface_color

            MDLabel:
                id: stats_label
                text: "Podaj adres i wybierz sieć."
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: app.sub_color

        # ── Transaction list ─────────────────────────────────────────────────
        TxRecycleView:
            id: rv
            key_viewclass: "viewclass"
            key_size: "height"

            RecycleBoxLayout:
                padding: dp(8), dp(4)
                spacing: dp(6)
                default_size: None, dp(90)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: "vertical"
"""

# ── RecycleView item ──────────────────────────────────────────────────────────

class TxCard(RecycleDataViewBehavior, MDCard):
    hash_short = StringProperty()
    method     = StringProperty()
    date       = StringProperty()
    value      = StringProperty()
    status     = StringProperty()
    tx_data    = ObjectProperty({})

    def refresh_view_attrs(self, rv, index, data):
        self.hash_short = data.get("hash_short", "")
        self.method     = data.get("method", "")
        self.date       = data.get("date", "")
        self.value      = data.get("value", "")
        self.status     = data.get("status", "")
        self.tx_data    = data.get("tx_data", {})
        return super().refresh_view_attrs(rv, index, data)


class TxRecycleView(RecycleView):
    pass


# ── Chip widget ───────────────────────────────────────────────────────────────

Builder.load_string("""
<NetworkChip@ButtonBehavior+MDBoxLayout>:
    size_hint: None, None
    size: dp(64), dp(32)
    padding: dp(8), dp(4)
    radius: [dp(16)]
    ripple_behavior: True
    selected: False
    net_key: ""
    canvas.before:
        Color:
            rgba: app.chip_bg(self.selected, self.net_key)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(16)]
    MDLabel:
        text: root.net_key
        font_style: "Caption"
        bold: root.selected
        halign: "center"
        theme_text_color: "Custom"
        text_color: (1,1,1,1) if root.selected else app.sub_color
""")


# ── Detail dialog content ─────────────────────────────────────────────────────

Builder.load_string("""
<DetailContent>:
    orientation: "vertical"
    spacing: dp(6)
    size_hint_y: None
    height: self.minimum_height
    padding: dp(4)
""")


class DetailContent(MDBoxLayout):
    def add_row(self, label: str, value: str):
        from kivymd.uix.label import MDLabel
        row = MDBoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        row.add_widget(MDLabel(
            text=label, font_style="Caption", bold=True,
            theme_text_color="Custom",
            text_color=MDApp.get_running_app().sub_color,
            size_hint_x=None, width=dp(80),
        ))
        val_lbl = MDLabel(
            text=value or "—", font_style="Caption",
            theme_text_color="Custom",
            text_color=MDApp.get_running_app().text_color,
        )
        row.add_widget(val_lbl)
        self.add_widget(row)


# ── App ───────────────────────────────────────────────────────────────────────

Builder.load_string(KV)


class CryptoScannerApp(MDApp):
    # Colors
    bg_color      = [0.051, 0.067, 0.090, 1]   # #0d1117
    surface_color = [0.086, 0.106, 0.133, 1]   # #161b22
    border_color  = [0.188, 0.212, 0.239, 1]   # #30363d
    text_color    = [0.902, 0.929, 0.953, 1]   # #e6edf3
    sub_color     = [0.545, 0.580, 0.620, 1]   # #8b949e
    accent_color  = [0.122, 0.435, 0.922, 1]   # #1f6feb
    green_color   = [0.137, 0.525, 0.212, 1]   # #238636
    card_color    = [0.086, 0.106, 0.133, 1]

    def __init__(self, **kw):
        super().__init__(**kw)
        self._rows: list[dict] = []
        self._stop = threading.Event()
        self._net_key = "ETH"
        self._dialog = None
        self._chips: dict = {}

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        screen = Builder.load_string(KV)  # already loaded above, returns MDScreen
        return screen

    def on_start(self):
        self._build_chips()

    def _build_chips(self):
        row = self.root.ids.chip_row
        row.clear_widgets()
        for key in NETWORKS:
            chip = self._make_chip(key)
            self._chips[key] = chip
            row.add_widget(chip)
        self._select_chip("ETH")

    def _make_chip(self, key: str):
        from kivy.factory import Factory
        chip = Factory.NetworkChip()
        chip.net_key = key
        chip.bind(on_release=lambda c, k=key: self._select_chip(k))
        return chip

    def _select_chip(self, key: str):
        self._net_key = key
        for k, chip in self._chips.items():
            chip.selected = (k == key)

    def chip_bg(self, selected, key):
        if not selected:
            return (*self.border_color[:3], 1)
        color_hex = NETWORKS.get(key, {}).get("color", "#1f6feb")
        r, g, b = int(color_hex[1:3], 16)/255, int(color_hex[3:5], 16)/255, int(color_hex[5:7], 16)/255
        return [r, g, b, 1]

    def status_color(self, status: str):
        if status == "OK":
            return [0.137, 0.525, 0.212, 1]
        return [0.855, 0.212, 0.200, 1]

    # ── Fetch ──────────────────────────────────────────────────────────────

    def start_fetch(self):
        addr = self.root.ids.addr_field.text.strip()
        if not re.match(r"^0x[0-9a-fA-F]{40}$", addr):
            self._snack("Nieprawidłowy adres Ethereum.")
            return

        try:
            max_pages = int(self.root.ids.pages_field.text or "0")
        except ValueError:
            max_pages = 0

        self._rows.clear()
        self.root.ids.rv.data = []
        self.root.ids.progress_bar.value = 0
        self.root.ids.stats_label.text = "Łączę…"
        self.root.ids.btn_fetch.disabled = True
        self.root.ids.btn_stop.disabled = False
        self._stop.clear()

        threading.Thread(
            target=fetch_transactions,
            args=(addr, self._net_key, max_pages,
                  lambda r: Clock.schedule_once(lambda dt: self._add_row(r)),
                  lambda m: Clock.schedule_once(lambda dt: self._set_status(m)),
                  lambda p, n: Clock.schedule_once(lambda dt: self._set_progress(p, n)),
                  lambda rows: Clock.schedule_once(lambda dt: self._done(rows))),
            kwargs={"stop": self._stop},
            daemon=True,
        ).start()

    def stop_fetch(self):
        self._stop.set()
        self.root.ids.btn_stop.disabled = True

    def _add_row(self, row: dict):
        self._rows.append(row)
        h = row["Hash"]
        self.root.ids.rv.data.append({
            "viewclass": "TxCard",
            "hash_short": h[:10] + "…" + h[-6:] if len(h) > 16 else h,
            "method":     (row["Metoda"] or "transfer")[:18],
            "date":       row["Data"],
            "value":      row["Wartość"],
            "status":     row["Status"],
            "tx_data":    row,
            "height":     dp(90),
        })

    def _set_status(self, msg: str):
        self.root.ids.stats_label.text = msg

    def _set_progress(self, page: int, total: int):
        p = min(page / 20, 1.0) if total < 20 else min(total / (total + 10), 0.95)
        self.root.ids.progress_bar.value = p * 100

    def _done(self, rows: list):
        self.root.ids.btn_fetch.disabled = False
        self.root.ids.btn_stop.disabled = True
        self.root.ids.progress_bar.value = 100
        self.root.ids.stats_label.text = f"{len(rows)} transakcji · {NETWORKS[self._net_key]['name']}"

    # ── Detail dialog ──────────────────────────────────────────────────────

    def show_detail(self, tx: dict):
        content = DetailContent()
        content.add_row("Hash",    tx.get("Hash", ""))
        content.add_row("Metoda",  tx.get("Metoda", ""))
        content.add_row("Blok",    tx.get("Blok", ""))
        content.add_row("Data",    tx.get("Data", ""))
        content.add_row("Od",      tx.get("Od", ""))
        content.add_row("Do",      tx.get("Do", ""))
        content.add_row("Wartość", tx.get("Wartość", ""))
        content.add_row("Opłata",  tx.get("Opłata", ""))
        content.add_row("Status",  tx.get("Status", ""))

        self._dialog = MDDialog(
            title="Szczegóły transakcji",
            type="custom",
            content_cls=content,
            buttons=[
                MDFlatButton(text="Kopiuj Hash",
                             on_release=lambda x: self._copy(tx.get("Hash", ""))),
                MDFlatButton(text="Zamknij",
                             on_release=lambda x: self._dialog.dismiss()),
            ],
        )
        self._dialog.open()

    def _copy(self, text: str):
        Clipboard.copy(text)
        self._snack(f"Skopiowano: {text[:20]}…")
        if self._dialog:
            self._dialog.dismiss()

    # ── Export CSV ─────────────────────────────────────────────────────────

    def export_csv(self):
        if not self._rows:
            self._snack("Brak danych do eksportu.")
            return

        if platform == "android":
            from android.storage import primary_external_storage_path
            folder = join(primary_external_storage_path(), "Download")
        else:
            from pathlib import Path
            folder = str(Path.home() / "Downloads")

        net_name = NETWORKS[self._net_key]["name"]
        addr     = self.root.ids.addr_field.text.strip()[:10]
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        path     = join(folder, f"tx_{net_name}_{addr}_{ts}.csv")

        fieldnames = ["Hash", "Metoda", "Blok", "Data", "Od", "Do", "Wartość", "Opłata", "Status"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self._rows)

        self._snack(f"Zapisano: {path}")

        # Android share intent
        if platform == "android":
            try:
                from jnius import autoclass
                from android import activity
                Intent    = autoclass("android.content.Intent")
                Uri       = autoclass("android.net.Uri")
                File      = autoclass("java.io.File")
                FileProvider = autoclass("androidx.core.content.FileProvider")
                intent    = Intent(Intent.ACTION_SEND)
                intent.setType("text/csv")
                uri = FileProvider.getUriForFile(
                    activity, "org.cryptoscanner.fileprovider", File(path)
                )
                intent.putExtra(Intent.EXTRA_STREAM, uri)
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                activity.startActivity(Intent.createChooser(intent, "Udostępnij CSV"))
            except Exception:
                pass

    def _snack(self, text: str):
        Snackbar(text=text, snackbar_x=dp(8), snackbar_y=dp(8),
                 size_hint_x=0.95).open()


if __name__ == "__main__":
    CryptoScannerApp().run()
