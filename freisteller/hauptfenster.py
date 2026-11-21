"""Hauptfenster von Bild-SVG-Converter-MK2."""

from __future__ import annotations

import io
import time
import traceback
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from PySide6.QtCore import (QBuffer, QByteArray, QIODevice, QObject, QRunnable,
                            QSettings, Qt, QThreadPool, QTimer, Signal)
from PySide6.QtGui import QImage, QKeySequence, QPainter, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                               QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QProgressBar,
                               QPushButton, QScrollArea,
                               QStatusBar, QVBoxLayout, QWidget)

from . import maske as mk
from . import segmentierung as seg
from . import svg_export as svgx
from . import theme
from .ansicht import HINTERGRUENDE, BildAnsicht
from .bausteine import FarbKnopf, Karte, SchieberZeile, Segmente, trenner
from .pfade import eigene_modelle_ordner, einstellungen_datei
from .version import APP_TITEL, APP_VERSION

BILD_ENDUNGEN = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff",
                 ".gif", ".ico", ".jfif", ".tga")

ANSICHTEN = [
    ("ergebnis", "Ergebnis"),
    ("ueberlagerung", "Überlagerung"),
    ("maske", "Maske"),
    ("original", "Original"),
    ("svg", "SVG-Vorschau"),
]


# --------------------------------------------------------------------------
# Hintergrundaufgaben
# --------------------------------------------------------------------------

class _Signale(QObject):
    fertig = Signal(str, int, object)
    fehler = Signal(str, int, str)


class Aufgabe(QRunnable):
    def __init__(self, art: str, kennung: int, funktion, *args) -> None:
        super().__init__()
        self.art = art
        self.kennung = kennung
        self.funktion = funktion
        self.args = args
        self.signale = _Signale()

    def run(self) -> None:  # noqa: D401
        try:
            ergebnis = self.funktion(*self.args)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.signale.fehler.emit(self.art, self.kennung, f"{type(exc).__name__}: {exc}")
            return
        self.signale.fertig.emit(self.art, self.kennung, ergebnis)


def qimage_aus_pil(bild: Image.Image) -> tuple[QImage, np.ndarray]:
    arr = np.ascontiguousarray(np.asarray(bild.convert("RGBA"), dtype=np.uint8))
    h, w = arr.shape[:2]
    return QImage(arr.data, w, h, 4 * w, QImage.Format_RGBA8888), arr


def pil_aus_qimage(qbild: QImage) -> Image.Image:
    puffer = QBuffer()
    puffer.open(QIODevice.WriteOnly)
    qbild.save(puffer, "PNG")
    return Image.open(io.BytesIO(bytes(puffer.data()))).copy()


def svg_rendern(svg: str, max_seite: int = 3000) -> QImage:
    r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    groesse = r.defaultSize()
    w, h = max(groesse.width(), 1), max(groesse.height(), 1)
    if max(w, h) > max_seite:
        f = max_seite / max(w, h)
        w, h = max(int(w * f), 1), max(int(h * f), 1)
    bild = QImage(w, h, QImage.Format_RGBA8888_Premultiplied)
    bild.fill(Qt.transparent)
    p = QPainter(bild)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p)
    p.end()
    return bild.convertToFormat(QImage.Format_RGBA8888)


# --------------------------------------------------------------------------
# Hauptfenster
# --------------------------------------------------------------------------

class Hauptfenster(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_TITEL}  v{APP_VERSION}")
        self.setAcceptDrops(True)
        self.resize(1400, 880)
        self.setMinimumSize(980, 640)

        self.einst = QSettings(str(einstellungen_datei()), QSettings.IniFormat)
        self.pool = QThreadPool.globalInstance()
        self.ki = seg.KiFreisteller()
        self.modelle = seg.modelle_finden()

        # Zustand
        self.pfad: Path | None = None
        self.original: Image.Image | None = None
        self.rgb: np.ndarray | None = None
        self.alpha_orig: np.ndarray | None = None
        self.grund: np.ndarray | None = None
        self.basis: np.ndarray | None = None
        self.maske: np.ndarray | None = None
        self.pinsel: mk.PinselEbene | None = None
        self.anzeige_arr: np.ndarray | None = None
        self.anzeige_qimg: QImage | None = None
        self.ansicht_modus = "ergebnis"
        self.farbe = (255, 255, 255)
        self._masken_version = 0
        self._svg_cache: tuple | None = None   # (signatur, svg_text)
        self._svg_bild: QImage | None = None
        self._kennung = {"grund": 0, "bearbeiten": 0, "svg": 0}
        self._laeuft: set[str] = set()
        self._nach_svg_speichern: Path | None = None
        self._werkzeug_vor_pipette = "verschieben"
        self._t_start = 0.0

        self._oberflaeche()
        self._kurzbefehle()
        self._einstellungen_laden()
        self._status("Bereit", "bereit")
        self._knoepfe_aktualisieren()

        self.timer_bearbeiten = QTimer(self, singleShot=True, interval=120)
        self.timer_bearbeiten.timeout.connect(self._bearbeiten_starten)
        self.timer_grund = QTimer(self, singleShot=True, interval=180)
        self.timer_grund.timeout.connect(self.grund_berechnen)

    # ------------------------------------------------------------------
    # Aufbau
    # ------------------------------------------------------------------
    def _oberflaeche(self) -> None:
        zentral = QWidget()
        zentral.setObjectName("Hauptflaeche")
        self.setCentralWidget(zentral)
        haupt = QVBoxLayout(zentral)
        haupt.setContentsMargins(0, 0, 0, 0)
        haupt.setSpacing(0)

        # Kopfzeile
        kopf = QFrame()
        kopf.setObjectName("Kopf")
        kl = QHBoxLayout(kopf)
        kl.setContentsMargins(18, 10, 18, 10)
        kl.setSpacing(10)
        punkt = QLabel("●")
        punkt.setObjectName("Punkt")
        titel = QLabel("Bild-SVG Converter")
        titel.setObjectName("Titel")
        chip_mk = QLabel("MK2")
        chip_mk.setObjectName("Chip")
        self.lbl_datei = QLabel("Kein Bild geladen")
        self.lbl_datei.setObjectName("Untertitel")
        kl.addWidget(punkt)
        kl.addWidget(titel)
        kl.addWidget(chip_mk)
        kl.addSpacing(14)
        kl.addWidget(self.lbl_datei, 1)
        self.fortschritt = QProgressBar()
        self.fortschritt.setRange(0, 0)
        self.fortschritt.setFixedWidth(120)
        self.fortschritt.setFixedHeight(6)
        self.fortschritt.hide()
        kl.addWidget(self.fortschritt)
        self.chip_status = QLabel("Bereit")
        self.chip_status.setObjectName("ChipAktiv")
        kl.addWidget(self.chip_status)
        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("Chip")
        kl.addWidget(ver)
        haupt.addWidget(kopf)

        koerper = QHBoxLayout()
        koerper.setContentsMargins(14, 14, 14, 14)
        koerper.setSpacing(14)
        haupt.addLayout(koerper, 1)

        # Linke Seite: Werkzeugleiste + Ansicht
        links = QVBoxLayout()
        links.setSpacing(10)
        leiste = QHBoxLayout()
        leiste.setSpacing(10)
        self.seg_ansicht = Segmente(ANSICHTEN, gleich_breit=False)
        self.seg_ansicht.setze("ergebnis")
        self.seg_ansicht.gewaehlt.connect(self.setze_ansicht)
        leiste.addWidget(self.seg_ansicht)
        leiste.addStretch(1)
        lbl_hg = QLabel("Hintergrund")
        lbl_hg.setObjectName("Gedaempft")
        leiste.addWidget(lbl_hg)
        self.cmb_hintergrund = QComboBox()
        for k, t in HINTERGRUENDE.items():
            self.cmb_hintergrund.addItem(t, k)
        self.cmb_hintergrund.currentIndexChanged.connect(
            lambda _i: self.ansicht.setze_hintergrund(self.cmb_hintergrund.currentData()))
        leiste.addWidget(self.cmb_hintergrund)
        self.btn_einpassen = QPushButton("Einpassen")
        self.btn_einpassen.setToolTip("Bild in das Fenster einpassen (Strg+0)")
        self.btn_100 = QPushButton("100 %")
        self.btn_100.setToolTip("Originalgröße (Strg+1)")
        leiste.addWidget(self.btn_einpassen)
        leiste.addWidget(self.btn_100)
        links.addLayout(leiste)

        self.ansicht = BildAnsicht()
        self.ansicht.dateien_abgelegt.connect(self._abgelegt)
        self.ansicht.strich_start.connect(self._strich_start)
        self.ansicht.strich_teil.connect(self._strich_teil)
        self.ansicht.strich_ende.connect(self._strich_ende)
        self.ansicht.farbe_gewaehlt.connect(self._pipette)
        self.ansicht.position.connect(self._position)
        self.ansicht.zoom_geaendert.connect(lambda z: self.lbl_zoom.setText(f"{z * 100:.0f} %"))
        self.ansicht.pinsel_radius_geaendert.connect(
            lambda r: self.s_pinsel.setze(int(round(r)), still=True))
        self.btn_einpassen.clicked.connect(self.ansicht.einpassen)
        self.btn_100.clicked.connect(self.ansicht.originalgroesse)
        links.addWidget(self.ansicht, 1)
        koerper.addLayout(links, 1)

        # Rechte Seite: Karten
        scroll = QScrollArea()
        scroll.setObjectName("Seitenleiste")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(360)
        inhalt = QWidget()
        inhalt.setObjectName("SeitenleisteInhalt")
        self.spalte = QVBoxLayout(inhalt)
        self.spalte.setContentsMargins(0, 0, 8, 0)
        self.spalte.setSpacing(12)
        scroll.setWidget(inhalt)
        koerper.addWidget(scroll)

        self._karte_bild()
        self._karte_freistellen()
        self._karte_kante()
        self._karte_pinsel()
        self._karte_svg()
        self.spalte.addStretch(1)

        # Statusleiste
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.lbl_meldung = QLabel("")
        self.lbl_groesse = QLabel("–")
        self.lbl_pos = QLabel("")
        self.lbl_zoom = QLabel("100 %")
        sb.addWidget(self.lbl_meldung, 1)
        for w in (self.lbl_pos, self.lbl_groesse, self.lbl_zoom):
            sb.addPermanentWidget(w)

    def _karte_bild(self) -> None:
        k = Karte("Bild")
        self.karte_bild = k
        zeile = QHBoxLayout()
        self.btn_oeffnen = QPushButton("Öffnen …")
        self.btn_oeffnen.setToolTip("Bild öffnen (Strg+O) – oder einfach in das Fenster ziehen")
        self.btn_oeffnen.clicked.connect(self.oeffnen_dialog)
        self.btn_einfuegen = QPushButton("Einfügen")
        self.btn_einfuegen.setToolTip("Bild aus der Zwischenablage (Strg+V)")
        self.btn_einfuegen.clicked.connect(self.einfuegen)
        zeile.addWidget(self.btn_oeffnen, 1)
        zeile.addWidget(self.btn_einfuegen, 1)
        k.add(zeile)
        self.lbl_bildinfo = QLabel("Bild per Drag & Drop in das Fenster ziehen.")
        self.lbl_bildinfo.setObjectName("Gedaempft")
        self.lbl_bildinfo.setWordWrap(True)
        k.add(self.lbl_bildinfo)
        self.spalte.addWidget(k)

    def _karte_freistellen(self) -> None:
        k = Karte("Freistellen")
        self.karte_freistellen = k
        self.seg_methode = Segmente([("ki", "KI automatisch"), ("farbe", "Hintergrundfarbe")])
        self.seg_methode.setze("ki")
        self.seg_methode.gewaehlt.connect(self._methode_gewechselt)
        k.add(self.seg_methode)

        # KI
        self.box_ki = QWidget()
        lk = QVBoxLayout(self.box_ki)
        lk.setContentsMargins(0, 0, 0, 0)
        lk.setSpacing(6)
        l1 = QLabel("Modell")
        l1.setObjectName("Gedaempft")
        lk.addWidget(l1)
        self.cmb_modell = QComboBox()
        for m in self.modelle:
            self.cmb_modell.addItem(m.anzeige, m.name)
        if not self.modelle:
            self.cmb_modell.addItem("Kein Modell gefunden", "")
            self.cmb_modell.setEnabled(False)
        self.cmb_modell.currentIndexChanged.connect(lambda _i: self._grund_neu())
        lk.addWidget(self.cmb_modell)
        self.lbl_ki_hinweis = QLabel(
            "Läuft vollständig offline auf diesem Rechner." if self.modelle else
            "Kein KI-Modell gefunden. Eine .onnx-Datei (z. B. isnet-general-use.onnx) "
            f"in den Ordner {eigene_modelle_ordner()} legen.")
        self.lbl_ki_hinweis.setObjectName("Gedaempft" if self.modelle else "Hinweis")
        self.lbl_ki_hinweis.setWordWrap(True)
        lk.addWidget(self.lbl_ki_hinweis)
        k.add(self.box_ki)

        # Farbe
        self.box_farbe = QWidget()
        lf = QVBoxLayout(self.box_farbe)
        lf.setContentsMargins(0, 0, 0, 0)
        lf.setSpacing(8)
        zeile = QHBoxLayout()
        lbl = QLabel("Hintergrundfarbe")
        lbl.setObjectName("Gedaempft")
        self.btn_farbe = FarbKnopf("#FFFFFF")
        self.btn_farbe.farbe_geaendert.connect(self._farbe_gesetzt)
        self.btn_pipette = QPushButton("Pipette")
        self.btn_pipette.setCheckable(True)
        self.btn_pipette.setToolTip("Farbe durch Klick in das Bild aufnehmen (I)")
        self.btn_pipette.toggled.connect(self._pipette_umschalten)
        self.btn_randfarbe = QPushButton("Randfarbe")
        self.btn_randfarbe.setToolTip("Häufigste Farbe am Bildrand übernehmen")
        self.btn_randfarbe.clicked.connect(self._randfarbe)
        zeile.addWidget(lbl)
        zeile.addStretch(1)
        zeile.addWidget(self.btn_farbe)
        zeile.addWidget(self.btn_pipette)
        zeile.addWidget(self.btn_randfarbe)
        lf.addLayout(zeile)
        self.s_toleranz = SchieberZeile("Toleranz", 0, 60, 12, " %",
                                        "Wie stark eine Farbe abweichen darf und trotzdem entfernt wird")
        self.s_toleranz.wert_geaendert.connect(lambda _w: self._grund_neu(verzoegert=True))
        lf.addWidget(self.s_toleranz)
        self.s_farb_weich = SchieberZeile("Weicher Übergang", 0, 100, 15, " %",
                                          "Halbtransparenter Übergang an den Rändern")
        self.s_farb_weich.wert_geaendert.connect(lambda _w: self._grund_neu(verzoegert=True))
        lf.addWidget(self.s_farb_weich)
        self.chk_vom_rand = QCheckBox("Nur zusammenhängend vom Bildrand aus")
        self.chk_vom_rand.setChecked(True)
        self.chk_vom_rand.setToolTip("Aus: die Farbe wird überall im Bild entfernt "
                                     "(z. B. Innenflächen von Buchstaben)")
        self.chk_vom_rand.toggled.connect(lambda _c: self._grund_neu())
        lf.addWidget(self.chk_vom_rand)
        k.add(self.box_farbe)

        self.btn_neu = QPushButton("Neu freistellen")
        self.btn_neu.setToolTip("Freistellung neu berechnen (F5)")
        self.btn_neu.clicked.connect(self.grund_berechnen)
        k.add(self.btn_neu)
        self.spalte.addWidget(k)
        self._methode_boxen()

    def _karte_kante(self) -> None:
        k = Karte("Kante & Feinschliff", offen=False)
        self.karte_kante = k
        self.s_schwelle = SchieberZeile("Schwelle", 1, 99, 50, " %",
                                        "Ab welcher Sicherheit ein Pixel zum Motiv gehört")
        self.chk_weich = QCheckBox("Weiche Kanten (Haare, Fell, Unschärfe)")
        self.chk_weich.setChecked(True)
        self.s_kante = SchieberZeile("Kante verschieben", -25, 25, 0, " px",
                                     "Negativ: Rand abtragen (Farbsäume entfernen) – "
                                     "positiv: Motiv erweitern",
                                     formatierer=lambda w: f"{w:+d} px" if w else "0 px")
        self.s_glaetten = SchieberZeile("Kante glätten", 0, 20, 0, "",
                                        "Weichzeichnen der Kante",
                                        formatierer=lambda w: f"{w / 2:.1f} px")
        self.s_inseln = SchieberZeile("Kleine Inseln entfernen", 0, 100, 0, "",
                                      "Lose Motiv-Reste unter dieser Größe entfernen",
                                      formatierer=lambda w: "aus" if w == 0 else f"< {w * w} px²")
        self.chk_loecher = QCheckBox("Löcher im Motiv füllen")
        for w in (self.s_schwelle, self.s_kante, self.s_glaetten, self.s_inseln):
            w.wert_geaendert.connect(lambda _w: self._bearbeiten_planen())
            k.add(w)
        k.layout_inhalt.insertWidget(1, self.chk_weich)
        self.chk_weich.toggled.connect(lambda _c: self._bearbeiten_planen())
        self.chk_loecher.toggled.connect(lambda _c: self._bearbeiten_planen())
        k.add(self.chk_loecher)
        btn = QPushButton("Zurücksetzen")
        btn.clicked.connect(self._kante_zuruecksetzen)
        k.add(btn)
        self.spalte.addWidget(k)

    def _karte_pinsel(self) -> None:
        k = Karte("Pinsel-Korrektur", offen=False)
        self.karte_pinsel = k
        self.seg_werkzeug = Segmente([("verschieben", "Hand"),
                                      ("behalten", "Behalten"),
                                      ("entfernen", "Entfernen")])
        self.seg_werkzeug.setze("verschieben")
        self.seg_werkzeug.gewaehlt.connect(self.setze_werkzeug)
        self.seg_werkzeug.knoepfe["verschieben"].setToolTip("Ansicht verschieben (H)")
        self.seg_werkzeug.knoepfe["behalten"].setToolTip("Bereiche zum Motiv hinzumalen (B)")
        self.seg_werkzeug.knoepfe["entfernen"].setToolTip("Bereiche wegradieren (E)")
        k.add(self.seg_werkzeug)
        self.s_pinsel = SchieberZeile("Pinselgröße", 1, 400, 20, " px",
                                      "Radius in Bildpixeln – auch mit [ und ] oder Alt+Mausrad")
        self.s_pinsel.wert_geaendert.connect(lambda w: self.ansicht.setze_pinsel_radius(w))
        k.add(self.s_pinsel)
        zeile = QHBoxLayout()
        self.btn_rueck = QPushButton("Rückgängig")
        self.btn_rueck.setToolTip("Strg+Z")
        self.btn_rueck.clicked.connect(self.rueckgaengig)
        self.btn_vor = QPushButton("Wiederholen")
        self.btn_vor.setToolTip("Strg+Y")
        self.btn_vor.clicked.connect(self.wiederholen)
        zeile.addWidget(self.btn_rueck)
        zeile.addWidget(self.btn_vor)
        k.add(zeile)
        self.btn_pinsel_leeren = QPushButton("Alle Korrekturen löschen")
        self.btn_pinsel_leeren.clicked.connect(self._pinsel_leeren)
        k.add(self.btn_pinsel_leeren)
        hinweis = QLabel("Rechte oder mittlere Maustaste verschiebt die Ansicht, "
                         "Mausrad zoomt.")
        hinweis.setObjectName("Gedaempft")
        hinweis.setWordWrap(True)
        k.add(hinweis)
        self.spalte.addWidget(k)

    def _karte_svg(self) -> None:
        k = Karte("Speichern als SVG")
        self.karte_svg = k
        l1 = QLabel("Art der SVG-Datei")
        l1.setObjectName("Gedaempft")
        k.add(l1)
        self.cmb_svg_art = QComboBox()
        for schl, text in svgx.ARTEN.items():
            self.cmb_svg_art.addItem(text, schl)
        self.cmb_svg_art.currentIndexChanged.connect(self._svg_art_gewechselt)
        k.add(self.cmb_svg_art)
        self.lbl_svg_info = QLabel()
        self.lbl_svg_info.setObjectName("Gedaempft")
        self.lbl_svg_info.setWordWrap(True)
        k.add(self.lbl_svg_info)

        self.box_vektor = QWidget()
        lv = QVBoxLayout(self.box_vektor)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)
        self.s_farben = SchieberZeile("Farbgenauigkeit", 1, 8, 6, "",
                                      "Mehr = feinere Farbabstufungen, größere Datei",
                                      formatierer=lambda w: f"{w} Bit")
        self.s_farbabstand = SchieberZeile("Farbebenen-Abstand", 1, 64, 16, "",
                                           "Größer = weniger Farbflächen")
        self.s_flecken = SchieberZeile("Flecken filtern", 0, 64, 4, " px",
                                       "Kleinere Flächen werden verworfen")
        self.s_ecken = SchieberZeile("Eckenerkennung", 0, 180, 60, "°",
                                     "Kleiner = mehr scharfe Ecken")
        self.s_aufloesung = SchieberZeile("Auflösung für Vektorisierung", 2, 40, 15, "",
                                          "Längste Bildseite, die vektorisiert wird",
                                          formatierer=lambda w: f"{w * 100} px")
        self.s_alpha = SchieberZeile("Deckkraft-Schwelle", 1, 99, 50, " %",
                                     "Ab welcher Deckkraft ein Pixel in die Vektorgrafik kommt")
        self.chk_kurven = QCheckBox("Glatte Kurven (sonst Polygone)")
        self.chk_kurven.setChecked(True)
        zeile = QHBoxLayout()
        self.lbl_sil = QLabel("Farbe der Silhouette")
        self.lbl_sil.setObjectName("Gedaempft")
        self.btn_sil_farbe = FarbKnopf(theme.FENSTER)
        zeile.addWidget(self.lbl_sil)
        zeile.addStretch(1)
        zeile.addWidget(self.btn_sil_farbe)
        self.zeile_sil = QWidget()
        self.zeile_sil.setLayout(zeile)
        for w in (self.s_farben, self.s_farbabstand, self.s_flecken, self.s_ecken,
                  self.s_aufloesung, self.s_alpha, self.chk_kurven, self.zeile_sil):
            lv.addWidget(w)
        for w in (self.s_farben, self.s_farbabstand, self.s_flecken, self.s_ecken,
                  self.s_aufloesung, self.s_alpha):
            w.wert_geaendert.connect(lambda _w: self._svg_einstellung_geaendert())
        self.chk_kurven.toggled.connect(lambda _c: self._svg_einstellung_geaendert())
        self.btn_sil_farbe.farbe_geaendert.connect(lambda _f: self._svg_einstellung_geaendert())
        k.add(self.box_vektor)

        k.add(trenner())
        zeile2 = QHBoxLayout()
        self.chk_zuschneiden = QCheckBox("Auf Motiv zuschneiden")
        self.chk_zuschneiden.setChecked(True)
        self.chk_zuschneiden.toggled.connect(lambda _c: self._svg_einstellung_geaendert())
        zeile2.addWidget(self.chk_zuschneiden)
        k.add(zeile2)
        self.s_rand = SchieberZeile("Rand um das Motiv", 0, 200, 0, " px")
        self.s_rand.wert_geaendert.connect(lambda _w: self._svg_einstellung_geaendert())
        k.add(self.s_rand)

        self.btn_vorschau = QPushButton("SVG-Vorschau berechnen")
        self.btn_vorschau.clicked.connect(self.svg_vorschau)
        k.add(self.btn_vorschau)
        self.btn_svg = QPushButton("Als SVG speichern …")
        self.btn_svg.setObjectName("Primaer")
        self.btn_svg.setToolTip("Strg+S")
        self.btn_svg.clicked.connect(self.svg_speichern)
        k.add(self.btn_svg)
        self.btn_png = QPushButton("Als PNG speichern …")
        self.btn_png.setToolTip("Transparentes PNG (Strg+Umschalt+S)")
        self.btn_png.clicked.connect(self.png_speichern)
        k.add(self.btn_png)
        self.spalte.addWidget(k)
        self._svg_art_gewechselt()

    def _kurzbefehle(self) -> None:
        def kb(folge, funktion):
            s = QShortcut(QKeySequence(folge), self)
            s.activated.connect(funktion)
            return s

        kb(QKeySequence.Open, self.oeffnen_dialog)
        kb(QKeySequence.Paste, self.einfuegen)
        kb(QKeySequence.Save, self.svg_speichern)
        kb("Ctrl+Shift+S", self.png_speichern)
        kb(QKeySequence.Undo, self.rueckgaengig)
        kb("Ctrl+Y", self.wiederholen)
        kb("Ctrl+Shift+Z", self.wiederholen)
        kb("F5", self.grund_berechnen)
        kb("Ctrl+0", self.ansicht.einpassen)
        kb("Ctrl+1", self.ansicht.originalgroesse)
        kb("Ctrl++", lambda: self.ansicht.zoomen(1.25))
        kb("Ctrl+=", lambda: self.ansicht.zoomen(1.25))
        kb("Ctrl+-", lambda: self.ansicht.zoomen(1 / 1.25))
        kb("H", lambda: self.setze_werkzeug("verschieben"))
        kb("B", lambda: self.setze_werkzeug("behalten"))
        kb("E", lambda: self.setze_werkzeug("entfernen"))
        kb("I", lambda: self.btn_pipette.setChecked(not self.btn_pipette.isChecked()))
        kb("[", lambda: self.s_pinsel.setze(max(1, int(self.s_pinsel.wert() / 1.2))))
        kb("]", lambda: self.s_pinsel.setze(min(400, int(self.s_pinsel.wert() * 1.2) + 1)))
        for i, (schl, _t) in enumerate(ANSICHTEN, start=1):
            kb(str(i), lambda s=schl: self.setze_ansicht(s))
        kb("Ctrl+Q", self.close)

    # ------------------------------------------------------------------
    # Einstellungen
    # ------------------------------------------------------------------
    def _einstellungen_laden(self) -> None:
        e = self.einst
        geo = e.value("fenster/geometrie")
        if geo is not None:
            self.restoreGeometry(geo)
        if e.value("fenster/maximiert", False, type=bool):
            self.setWindowState(Qt.WindowMaximized)

        def i(schl, std):
            return e.value(schl, std, type=int)

        def b(schl, std):
            return e.value(schl, std, type=bool)

        self.seg_methode.setze(e.value("freistellen/methode", "ki"))
        modell = e.value("freistellen/modell", "")
        idx = self.cmb_modell.findData(modell)
        if idx >= 0:
            self.cmb_modell.blockSignals(True)
            self.cmb_modell.setCurrentIndex(idx)
            self.cmb_modell.blockSignals(False)
        self.btn_farbe.setze(e.value("freistellen/farbe", "#FFFFFF"), still=True)
        self.farbe = self._hex_zu_rgb(self.btn_farbe.farbe())
        self.s_toleranz.setze(i("freistellen/toleranz", 12), still=True)
        self.s_farb_weich.setze(i("freistellen/weich", 15), still=True)
        self._still(self.chk_vom_rand, b("freistellen/vom_rand", True))
        self._methode_boxen()

        self.s_schwelle.setze(i("kante/schwelle", 50), still=True)
        self._still(self.chk_weich, b("kante/weich", True))
        self.s_kante.setze(i("kante/verschieben", 0), still=True)
        self.s_glaetten.setze(i("kante/glaetten", 0), still=True)
        self.s_inseln.setze(i("kante/inseln", 0), still=True)
        self._still(self.chk_loecher, b("kante/loecher", False))

        self.s_pinsel.setze(i("pinsel/groesse", 20), still=True)
        self.ansicht.setze_pinsel_radius(self.s_pinsel.wert())

        art = e.value("svg/art", "pixel")
        idx = self.cmb_svg_art.findData(art)
        self.cmb_svg_art.blockSignals(True)
        self.cmb_svg_art.setCurrentIndex(max(idx, 0))
        self.cmb_svg_art.blockSignals(False)
        self.s_farben.setze(i("svg/farbgenauigkeit", 6), still=True)
        self.s_farbabstand.setze(i("svg/farbabstand", 16), still=True)
        self.s_flecken.setze(i("svg/flecken", 4), still=True)
        self.s_ecken.setze(i("svg/ecken", 60), still=True)
        self.s_aufloesung.setze(i("svg/aufloesung", 15), still=True)
        self.s_alpha.setze(i("svg/alpha", 50), still=True)
        self._still(self.chk_kurven, b("svg/kurven", True))
        self.btn_sil_farbe.setze(e.value("svg/silhouette_farbe", theme.FENSTER), still=True)
        self._still(self.chk_zuschneiden, b("svg/zuschneiden", True))
        self.s_rand.setze(i("svg/rand", 0), still=True)
        self._svg_art_gewechselt()

        hg = e.value("ansicht/hintergrund", "karo_dunkel")
        idx = self.cmb_hintergrund.findData(hg)
        self.cmb_hintergrund.setCurrentIndex(max(idx, 0))
        self.ansicht.setze_hintergrund(self.cmb_hintergrund.currentData())

        for name, karte in (("bild", self.karte_bild), ("freistellen", self.karte_freistellen),
                            ("kante", self.karte_kante), ("pinsel", self.karte_pinsel),
                            ("svg", self.karte_svg)):
            wert = e.value(f"karten/{name}")
            if wert is not None:
                karte.setze_offen(str(wert).lower() in ("true", "1"))

    def _einstellungen_speichern(self) -> None:
        e = self.einst
        e.setValue("fenster/maximiert", self.isMaximized())
        if not self.isMaximized():
            e.setValue("fenster/geometrie", self.saveGeometry())
        e.setValue("freistellen/methode", self.seg_methode.aktuell())
        e.setValue("freistellen/modell", self.cmb_modell.currentData() or "")
        e.setValue("freistellen/farbe", self.btn_farbe.farbe())
        e.setValue("freistellen/toleranz", self.s_toleranz.wert())
        e.setValue("freistellen/weich", self.s_farb_weich.wert())
        e.setValue("freistellen/vom_rand", self.chk_vom_rand.isChecked())
        e.setValue("kante/schwelle", self.s_schwelle.wert())
        e.setValue("kante/weich", self.chk_weich.isChecked())
        e.setValue("kante/verschieben", self.s_kante.wert())
        e.setValue("kante/glaetten", self.s_glaetten.wert())
        e.setValue("kante/inseln", self.s_inseln.wert())
        e.setValue("kante/loecher", self.chk_loecher.isChecked())
        e.setValue("pinsel/groesse", self.s_pinsel.wert())
        s = self._svg_einstellungen()
        e.setValue("svg/art", s.art)
        e.setValue("svg/farbgenauigkeit", s.farbgenauigkeit)
        e.setValue("svg/farbabstand", s.farbabstand)
        e.setValue("svg/flecken", s.flecken_px)
        e.setValue("svg/ecken", s.ecken_grad)
        e.setValue("svg/aufloesung", self.s_aufloesung.wert())
        e.setValue("svg/alpha", s.alpha_schwelle)
        e.setValue("svg/kurven", s.kurven)
        e.setValue("svg/silhouette_farbe", s.silhouette_farbe)
        e.setValue("svg/zuschneiden", self.chk_zuschneiden.isChecked())
        e.setValue("svg/rand", self.s_rand.wert())
        e.setValue("ansicht/hintergrund", self.cmb_hintergrund.currentData())
        for name, karte in (("bild", self.karte_bild), ("freistellen", self.karte_freistellen),
                            ("kante", self.karte_kante), ("pinsel", self.karte_pinsel),
                            ("svg", self.karte_svg)):
            e.setValue(f"karten/{name}", karte.offen)
        e.sync()

    @staticmethod
    def _still(chk: QCheckBox, wert: bool) -> None:
        chk.blockSignals(True)
        chk.setChecked(bool(wert))
        chk.blockSignals(False)

    @staticmethod
    def _hex_zu_rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def closeEvent(self, ev) -> None:  # noqa: N802
        self._einstellungen_speichern()
        super().closeEvent(ev)

    def showEvent(self, ev) -> None:  # noqa: N802
        super().showEvent(ev)
        theme.dunkle_titelleiste(self)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def _status(self, text: str, art: str = "bereit") -> None:
        name = {"bereit": "ChipAktiv", "arbeit": "ChipArbeit", "fehler": "ChipFehler",
                "leer": "Chip"}[art]
        self.chip_status.setObjectName(name)
        self.chip_status.setText(text)
        self.chip_status.style().unpolish(self.chip_status)
        self.chip_status.style().polish(self.chip_status)
        self.fortschritt.setVisible(art == "arbeit")

    def _meldung(self, text: str) -> None:
        self.lbl_meldung.setText(text)

    def _knoepfe_aktualisieren(self) -> None:
        hat_bild = self.original is not None
        hat_maske = self.maske is not None
        for w in (self.btn_svg, self.btn_png, self.btn_vorschau):
            w.setEnabled(hat_maske)
        self.btn_neu.setEnabled(hat_bild)
        p = self.pinsel
        self.btn_rueck.setEnabled(bool(p and p.kann_rueckgaengig))
        self.btn_vor.setEnabled(bool(p and p.kann_wiederholen))
        self.btn_pinsel_leeren.setEnabled(bool(p is not None and p.daten.any()))

    # ------------------------------------------------------------------
    # Laden
    # ------------------------------------------------------------------
    def _abgelegt(self, eintraege: list) -> None:
        for e in eintraege:
            if isinstance(e, str):
                if Path(e).suffix.lower() in BILD_ENDUNGEN or Path(e).is_file():
                    self.bild_laden(e)
                    return
            elif isinstance(e, QImage) and not e.isNull():
                self.bild_laden(pil_aus_qimage(e), name="Abgelegtes Bild")
                return

    def dragEnterEvent(self, ev) -> None:  # noqa: N802
        if ev.mimeData().hasUrls() or ev.mimeData().hasImage():
            ev.acceptProposedAction()

    def dropEvent(self, ev) -> None:  # noqa: N802
        md = ev.mimeData()
        dateien = [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
        if dateien:
            self._abgelegt(dateien)
        elif md.hasImage():
            self._abgelegt([md.imageData()])

    def oeffnen_dialog(self) -> None:
        start = self.einst.value("pfade/oeffnen", str(Path.home()))
        muster = "Bilder (" + " ".join(f"*{e}" for e in BILD_ENDUNGEN) + ");;Alle Dateien (*)"
        datei, _ = QFileDialog.getOpenFileName(self, "Bild öffnen", start, muster)
        if datei:
            self.bild_laden(datei)

    def einfuegen(self) -> None:
        md = QApplication.clipboard().mimeData()
        if md is None:
            return
        if md.hasUrls():
            dateien = [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
            if dateien:
                self._abgelegt(dateien)
                return
        if md.hasImage():
            bild = QApplication.clipboard().image()
            if not bild.isNull():
                self.bild_laden(pil_aus_qimage(bild), name="Eingefügtes Bild")
                return
        self._meldung("Kein Bild in der Zwischenablage.")

    def bild_laden(self, quelle, name: str | None = None) -> bool:
        try:
            if isinstance(quelle, Image.Image):
                bild = quelle
                self.pfad = None
                anzeige_name = name or "Bild"
            else:
                pfad = Path(quelle)
                with Image.open(pfad) as roh:
                    roh.seek(0) if getattr(roh, "is_animated", False) else None
                    bild = ImageOps.exif_transpose(roh)
                    bild.load()
                self.pfad = pfad
                anzeige_name = pfad.name
                self.einst.setValue("pfade/oeffnen", str(pfad.parent))
            hat_alpha = bild.mode in ("RGBA", "LA", "PA") or (
                bild.mode == "P" and "transparency" in bild.info)
            bild = bild.convert("RGBA")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Bild öffnen",
                                f"Das Bild konnte nicht geöffnet werden:\n{exc}")
            return False

        self.original = bild
        arr = np.asarray(bild, dtype=np.uint8)
        self.rgb = np.ascontiguousarray(arr[..., :3])
        self.alpha_orig = arr[..., 3].astype(np.float32) / 255.0
        self.grund = None
        self.basis = None
        self.maske = None
        self.pinsel = mk.PinselEbene(bild.width, bild.height)
        self._svg_cache = None
        self._svg_bild = None
        self._masken_version += 1
        self.lbl_datei.setText(anzeige_name)
        self.lbl_groesse.setText(f"{bild.width} × {bild.height} px")
        self.lbl_bildinfo.setText(
            f"{anzeige_name}\n{bild.width} × {bild.height} px"
            + ("  ·  hat bereits Transparenz" if hat_alpha else ""))
        if self.seg_methode.aktuell() == "farbe" and self.einst.value(
                "freistellen/randfarbe_auto", True, type=bool):
            self.farbe = seg.rand_farbe(bild)
            self.btn_farbe.setze("#%02X%02X%02X" % self.farbe, still=True)
        if self.ansicht_modus == "svg":
            self.setze_ansicht("ergebnis")
        self._anzeige_neu(einpassen=True)
        self._knoepfe_aktualisieren()
        self.grund_berechnen()
        return True

    # ------------------------------------------------------------------
    # Freistellen
    # ------------------------------------------------------------------
    def _methode_boxen(self) -> None:
        ki = self.seg_methode.aktuell() == "ki"
        self.box_ki.setVisible(ki)
        self.box_farbe.setVisible(not ki)
        if ki and self.btn_pipette.isChecked():
            self.btn_pipette.setChecked(False)

    def _methode_gewechselt(self, _m: str) -> None:
        self._methode_boxen()
        if self.seg_methode.aktuell() == "farbe" and self.original is not None:
            if self.farbe == (255, 255, 255) and self.btn_farbe.farbe().upper() == "#FFFFFF":
                self.farbe = seg.rand_farbe(self.original)
                self.btn_farbe.setze("#%02X%02X%02X" % self.farbe, still=True)
        self._grund_neu()

    def _grund_neu(self, verzoegert: bool = False) -> None:
        if self.original is None:
            return
        if verzoegert:
            self.timer_grund.start()
        else:
            self.grund_berechnen()

    def _aktuelles_modell(self) -> seg.ModellInfo | None:
        name = self.cmb_modell.currentData()
        for m in self.modelle:
            if m.name == name:
                return m
        return self.modelle[0] if self.modelle else None

    def grund_berechnen(self) -> None:
        if self.original is None:
            return
        self._kennung["grund"] += 1
        kennung = self._kennung["grund"]
        self._t_start = time.perf_counter()
        if self.seg_methode.aktuell() == "ki":
            modell = self._aktuelles_modell()
            if modell is None:
                self._status("Kein KI-Modell", "fehler")
                self._meldung("Kein KI-Modell gefunden – bitte „Hintergrundfarbe“ verwenden "
                              f"oder ein Modell in den Ordner {eigene_modelle_ordner()} legen.")
                return
            self._status("KI stellt frei …", "arbeit")
            self._meldung(f"Freistellen mit {modell.anzeige} …")
            aufgabe = Aufgabe("grund", kennung, self.ki.maske, self.original, modell)
        else:
            self._status("Farbe wird entfernt …", "arbeit")
            aufgabe = Aufgabe("grund", kennung, seg.farb_maske, self.original, self.farbe,
                              float(self.s_toleranz.wert()), self.chk_vom_rand.isChecked(),
                              float(self.s_farb_weich.wert()))
        self._starten(aufgabe)

    def _starten(self, aufgabe: Aufgabe) -> None:
        aufgabe.signale.fertig.connect(self._aufgabe_fertig)
        aufgabe.signale.fehler.connect(self._aufgabe_fehler)
        self._laeuft.add(aufgabe.art)
        self.pool.start(aufgabe)

    def _aufgabe_fehler(self, art: str, kennung: int, text: str) -> None:
        self._laeuft.discard(art)
        if kennung != self._kennung.get(art):
            return
        self._status("Fehler", "fehler")
        self._meldung(text)
        self._nach_svg_speichern = None
        QMessageBox.warning(self, "Fehler", text)

    def _aufgabe_fertig(self, art: str, kennung: int, ergebnis) -> None:
        self._laeuft.discard(art)
        if kennung != self._kennung.get(art):
            return
        if art == "grund":
            self.grund = ergebnis
            dauer = time.perf_counter() - self._t_start
            self._meldung(f"Freigestellt in {dauer:.1f} s")
            self._bearbeiten_starten()
        elif art == "bearbeiten":
            self.basis = ergebnis
            self._maske_zusammensetzen()
            self._masken_version += 1
            self._anzeige_neu()
            self._knoepfe_aktualisieren()
            if not self._laeuft & {"grund", "bearbeiten", "svg"}:
                self._status("Bereit", "bereit")
            if self.ansicht_modus == "svg":
                self.svg_vorschau()
        elif art == "svg":
            signatur, svg = ergebnis
            self._svg_cache = (signatur, svg)
            pfade = svgx.svg_pfade_zaehlen(svg)
            groesse = len(svg.encode("utf-8"))
            text = f"SVG: {self._groesse_text(groesse)}"
            if pfade:
                text += f", {pfade} Pfade"
            self.lbl_svg_info.setText(text)
            ziel = self._nach_svg_speichern
            self._nach_svg_speichern = None
            if ziel is not None:
                self._svg_schreiben(ziel, svg)
            if self.ansicht_modus == "svg":
                self._svg_bild = svg_rendern(svg)
                self.ansicht.setze_bild(self._svg_bild, None, einpassen=True)
            if not self._laeuft & {"grund", "bearbeiten", "svg"}:
                self._status("Bereit", "bereit")

    @staticmethod
    def _groesse_text(n: int) -> str:
        if n < 1024:
            return f"{n} B"
        if n < 1024 * 1024:
            return f"{n / 1024:.1f} KB"
        return f"{n / 1024 / 1024:.2f} MB"

    # -- Nachbearbeitung ------------------------------------------------
    def _masken_einstellungen(self) -> mk.MaskenEinstellungen:
        w = self.s_inseln.wert()
        return mk.MaskenEinstellungen(
            schwelle=self.s_schwelle.wert(),
            weiche_kanten=self.chk_weich.isChecked(),
            kante_px=self.s_kante.wert(),
            glaetten_px=self.s_glaetten.wert() / 2.0,
            inseln_px=w * w,
            loecher_fuellen=self.chk_loecher.isChecked(),
        )

    def _bearbeiten_planen(self) -> None:
        if self.grund is not None:
            self.timer_bearbeiten.start()

    def _bearbeiten_starten(self) -> None:
        if self.grund is None:
            return
        self._kennung["bearbeiten"] += 1
        self._status("Kante wird bearbeitet …", "arbeit")
        self._starten(Aufgabe("bearbeiten", self._kennung["bearbeiten"],
                              mk.maske_bearbeiten, self.grund,
                              self._masken_einstellungen(), None))

    def _kante_zuruecksetzen(self) -> None:
        self.s_schwelle.setze(50, still=True)
        self._still(self.chk_weich, True)
        self.s_kante.setze(0, still=True)
        self.s_glaetten.setze(0, still=True)
        self.s_inseln.setze(0, still=True)
        self._still(self.chk_loecher, False)
        self._bearbeiten_planen()

    def _maske_zusammensetzen(self, bereich=None) -> None:
        if self.basis is None:
            return
        if bereich is None:
            m = self.basis.copy()
            if self.pinsel is not None:
                p = self.pinsel.daten
                m[p > 0] = 1.0
                m[p < 0] = 0.0
            self.maske = m
        else:
            x0, y0, x1, y1 = bereich
            teil = self.basis[y0:y1, x0:x1].copy()
            p = self.pinsel.daten[y0:y1, x0:x1]
            teil[p > 0] = 1.0
            teil[p < 0] = 0.0
            self.maske[y0:y1, x0:x1] = teil

    # -- Farbe ----------------------------------------------------------
    def _farbe_gesetzt(self, farbe: str) -> None:
        self.farbe = self._hex_zu_rgb(farbe)
        if self.seg_methode.aktuell() != "farbe":
            self.seg_methode.setze("farbe")
            self._methode_boxen()
        self._grund_neu()

    def _randfarbe(self) -> None:
        if self.original is None:
            return
        self.farbe = seg.rand_farbe(self.original)
        self.btn_farbe.setze("#%02X%02X%02X" % self.farbe)

    def _pipette_umschalten(self, an: bool) -> None:
        if an:
            if self.ansicht.werkzeug != "pipette":
                self._werkzeug_vor_pipette = self.ansicht.werkzeug
            self.ansicht.setze_werkzeug("pipette")
            self._meldung("Pipette: in das Bild klicken, um die Hintergrundfarbe aufzunehmen.")
        else:
            self.ansicht.setze_werkzeug(self._werkzeug_vor_pipette)
            self.seg_werkzeug.setze(self._werkzeug_vor_pipette)

    def _pipette(self, x: int, y: int) -> None:
        if self.original is None:
            return
        x = min(max(x, 0), self.original.width - 1)
        y = min(max(y, 0), self.original.height - 1)
        # Mittelwert 3×3 gegen Rauschen
        y0, y1 = max(y - 1, 0), min(y + 2, self.original.height)
        x0, x1 = max(x - 1, 0), min(x + 2, self.original.width)
        farbe = self.rgb[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0)
        self.farbe = tuple(int(round(v)) for v in farbe)
        self.btn_pipette.setChecked(False)
        self.btn_farbe.setze("#%02X%02X%02X" % self.farbe)

    # ------------------------------------------------------------------
    # Pinsel
    # ------------------------------------------------------------------
    def setze_werkzeug(self, name: str) -> None:
        if self.btn_pipette.isChecked():
            self.btn_pipette.blockSignals(True)
            self.btn_pipette.setChecked(False)
            self.btn_pipette.blockSignals(False)
        self.seg_werkzeug.setze(name)
        self.ansicht.setze_werkzeug(name)
        if name in ("behalten", "entfernen"):
            if not self.karte_pinsel.offen:
                self.karte_pinsel.setze_offen(True)
            if self.ansicht_modus in ("svg",):
                self.setze_ansicht("ueberlagerung")

    def _strich_start(self) -> None:
        if self.pinsel is not None and self.maske is not None:
            self.pinsel.strich_beginnen()

    def _strich_teil(self, x0: float, y0: float, x1: float, y1: float) -> None:
        if self.pinsel is None or self.maske is None or self.basis is None:
            return
        wert = 1 if self.ansicht.werkzeug == "behalten" else -1
        bereich = self.pinsel.tupfen(x0, y0, x1, y1, self.s_pinsel.wert(), wert)
        if bereich is None:
            return
        self._maske_zusammensetzen(bereich)
        self._anzeige_bereich(bereich)
        self.ansicht.bereich_aktualisieren(*bereich)

    def _strich_ende(self) -> None:
        if self.pinsel is not None:
            self.pinsel.strich_beenden()
            self._masken_version += 1
            self._knoepfe_aktualisieren()

    def rueckgaengig(self) -> None:
        if self.pinsel and self.pinsel.rueckgaengig():
            self._nach_pinsel_verlauf()

    def wiederholen(self) -> None:
        if self.pinsel and self.pinsel.wiederholen():
            self._nach_pinsel_verlauf()

    def _pinsel_leeren(self) -> None:
        if self.pinsel:
            self.pinsel.leeren()
            self._nach_pinsel_verlauf()

    def _nach_pinsel_verlauf(self) -> None:
        self._maske_zusammensetzen()
        self._masken_version += 1
        self._anzeige_neu()
        self._knoepfe_aktualisieren()

    # ------------------------------------------------------------------
    # Anzeige
    # ------------------------------------------------------------------
    def setze_ansicht(self, modus: str) -> None:
        alt = self.ansicht_modus
        self.ansicht_modus = modus
        self.seg_ansicht.setze(modus)
        self.ansicht.setze_pinsel_erlaubt(modus != "svg")
        if modus == "svg":
            if self.maske is None:
                return
            sig = self._svg_signatur()
            if self._svg_cache and self._svg_cache[0] == sig:
                self._svg_bild = svg_rendern(self._svg_cache[1])
                self.ansicht.setze_bild(self._svg_bild, None, einpassen=True)
            else:
                self.svg_vorschau()
            return
        self._anzeige_neu(einpassen=(alt == "svg"))

    def _anzeige_neu(self, einpassen: bool = False) -> None:
        if self.original is None or self.ansicht_modus == "svg":
            return
        h, w = self.rgb.shape[:2]
        if self.anzeige_arr is None or self.anzeige_arr.shape[:2] != (h, w):
            self.anzeige_arr = np.zeros((h, w, 4), np.uint8)
            neu = True
        else:
            neu = False
        self._anzeige_bereich((0, 0, w, h))
        self.anzeige_qimg = QImage(self.anzeige_arr.data, w, h, 4 * w, QImage.Format_RGBA8888)
        self.ansicht.setze_bild(self.anzeige_qimg, self.anzeige_arr, einpassen=einpassen or neu)

    def _anzeige_bereich(self, bereich) -> None:
        if self.anzeige_arr is None or self.ansicht_modus == "svg":
            return
        x0, y0, x1, y1 = bereich
        ziel = self.anzeige_arr[y0:y1, x0:x1]
        rgb = self.rgb[y0:y1, x0:x1]
        a0 = self.alpha_orig[y0:y1, x0:x1]
        m = self.maske[y0:y1, x0:x1] if self.maske is not None else None
        modus = self.ansicht_modus
        if modus == "original" or m is None:
            ziel[..., :3] = rgb
            ziel[..., 3] = (a0 * 255 + 0.5).astype(np.uint8)
        elif modus == "ergebnis":
            ziel[..., :3] = rgb
            ziel[..., 3] = (a0 * m * 255 + 0.5).astype(np.uint8)
        elif modus == "maske":
            g = (m * 255 + 0.5).astype(np.uint8)
            ziel[..., 0] = g
            ziel[..., 1] = g
            ziel[..., 2] = g
            ziel[..., 3] = 255
        elif modus == "ueberlagerung":
            rot = np.array([255, 70, 70], np.float32)
            f = rgb.astype(np.float32)
            mm = m[..., None]
            gemischt = f * mm + (f * 0.45 + rot * 0.55) * (1.0 - mm)
            ziel[..., :3] = np.clip(gemischt + 0.5, 0, 255).astype(np.uint8)
            ziel[..., 3] = (a0 * 255 + 0.5).astype(np.uint8)

    def _position(self, x: int, y: int) -> None:
        if self.original is None:
            return
        if 0 <= x < self.original.width and 0 <= y < self.original.height:
            text = f"x {x}  y {y}"
            if self.maske is not None:
                text += f"  ·  Deckkraft {self.maske[y, x] * self.alpha_orig[y, x] * 100:.0f} %"
            self.lbl_pos.setText(text)
        else:
            self.lbl_pos.setText("")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _svg_art_gewechselt(self) -> None:
        art = self.cmb_svg_art.currentData()
        vektor = art in ("farbe", "silhouette")
        self.box_vektor.setVisible(vektor)
        for w in (self.s_farben, self.s_farbabstand):
            w.setVisible(art == "farbe")
        self.zeile_sil.setVisible(art == "silhouette")
        info = {
            "pixel": "Das freigestellte Bild wird verlustfrei mit Transparenz in die SVG "
                     "eingebettet. Sieht exakt aus wie das Ergebnis – für Fotos ideal.",
            "farbe": "Das Motiv wird in echte, skalierbare Vektorflächen umgewandelt. "
                     "Ideal für Logos, Grafiken, Icons und Plotter.",
            "silhouette": "Nur der Umriss des Motivs als einfarbige Vektorfläche – "
                          "z. B. für Schneideplotter, Laser oder Stempel.",
        }[art]
        self.lbl_svg_info.setText(info)
        self._svg_einstellung_geaendert(info_behalten=True)

    def _svg_einstellung_geaendert(self, info_behalten: bool = False) -> None:
        if self.ansicht_modus == "svg" and self.maske is not None:
            self._svg_timer().start()

    def _svg_timer(self) -> QTimer:
        if not hasattr(self, "_t_svg"):
            self._t_svg = QTimer(self, singleShot=True, interval=350)
            self._t_svg.timeout.connect(self.svg_vorschau)
        return self._t_svg

    def _svg_einstellungen(self) -> svgx.SvgEinstellungen:
        return svgx.SvgEinstellungen(
            art=self.cmb_svg_art.currentData(),
            farbgenauigkeit=self.s_farben.wert(),
            flecken_px=self.s_flecken.wert(),
            farbabstand=self.s_farbabstand.wert(),
            kurven=self.chk_kurven.isChecked(),
            ecken_grad=self.s_ecken.wert(),
            max_px=self.s_aufloesung.wert() * 100,
            silhouette_farbe=self.btn_sil_farbe.farbe(),
            alpha_schwelle=self.s_alpha.wert(),
        )

    def _svg_signatur(self) -> tuple:
        return (self._masken_version, tuple(sorted(self._svg_einstellungen().als_dict().items())),
                self.chk_zuschneiden.isChecked(), self.s_rand.wert())

    def export_bild(self) -> Image.Image | None:
        if self.original is None or self.maske is None:
            return None
        bild = mk.ergebnis_bild(self.original, self.maske)
        if self.chk_zuschneiden.isChecked():
            bild = mk.zuschneiden(bild, self.s_rand.wert())
        return bild

    def _svg_job(self, bild: Image.Image, e: svgx.SvgEinstellungen, signatur: tuple):
        return signatur, svgx.svg_erzeugen(bild, e)

    def svg_vorschau(self) -> None:
        bild = self.export_bild()
        if bild is None:
            return
        self._kennung["svg"] += 1
        self._status("SVG wird erzeugt …", "arbeit")
        self._starten(Aufgabe("svg", self._kennung["svg"], self._svg_job, bild,
                              self._svg_einstellungen(), self._svg_signatur()))
        if self.ansicht_modus != "svg":
            self.ansicht_modus = "svg"
            self.seg_ansicht.setze("svg")
            self.ansicht.setze_pinsel_erlaubt(False)

    def _vorschlag(self, endung: str) -> str:
        ordner = self.einst.value("pfade/speichern", "")
        if not ordner:
            ordner = str(self.pfad.parent) if self.pfad else str(Path.home())
        stamm = self.pfad.stem if self.pfad else "bild"
        return str(Path(ordner) / f"{stamm}_freigestellt{endung}")

    def svg_speichern(self) -> None:
        if self.maske is None:
            return
        ziel, _ = QFileDialog.getSaveFileName(self, "Als SVG speichern",
                                              self._vorschlag(".svg"), "SVG-Grafik (*.svg)")
        if not ziel:
            return
        ziel = Path(ziel)
        if ziel.suffix.lower() != ".svg":
            ziel = ziel.with_suffix(".svg")
        self.einst.setValue("pfade/speichern", str(ziel.parent))
        sig = self._svg_signatur()
        if self._svg_cache and self._svg_cache[0] == sig:
            self._svg_schreiben(ziel, self._svg_cache[1])
            return
        bild = self.export_bild()
        self._nach_svg_speichern = ziel
        self._kennung["svg"] += 1
        self._status("SVG wird erzeugt …", "arbeit")
        self._starten(Aufgabe("svg", self._kennung["svg"], self._svg_job, bild,
                              self._svg_einstellungen(), sig))

    def _svg_schreiben(self, ziel: Path, svg: str) -> None:
        try:
            ziel.write_text(svg, encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Speichern", f"Speichern fehlgeschlagen:\n{exc}")
            return
        self._meldung(f"Gespeichert: {ziel}  ({self._groesse_text(ziel.stat().st_size)})")
        self._status("Gespeichert", "bereit")

    def png_speichern(self) -> None:
        bild = self.export_bild()
        if bild is None:
            return
        ziel, _ = QFileDialog.getSaveFileName(self, "Als PNG speichern",
                                              self._vorschlag(".png"), "PNG-Bild (*.png)")
        if not ziel:
            return
        ziel = Path(ziel)
        if ziel.suffix.lower() != ".png":
            ziel = ziel.with_suffix(".png")
        self.einst.setValue("pfade/speichern", str(ziel.parent))
        try:
            bild.save(ziel, "PNG", optimize=True)
        except OSError as exc:
            QMessageBox.warning(self, "Speichern", f"Speichern fehlgeschlagen:\n{exc}")
            return
        self._meldung(f"Gespeichert: {ziel}  ({self._groesse_text(ziel.stat().st_size)})")
        self._status("Gespeichert", "bereit")
