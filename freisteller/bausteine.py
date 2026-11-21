"""Wiederverwendbare Oberflächen-Bausteine im Dashboard-Stil."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QColorDialog, QFrame, QHBoxLayout,
                               QLabel, QPushButton, QSlider, QVBoxLayout,
                               QWidget)

from . import theme


class _KartenKopf(QWidget):
    geklickt = Signal()

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self.geklickt.emit()


class Karte(QFrame):
    """Karte mit Teal-Statuspunkt vor dem Titel; einklappbar."""

    umgeschaltet = Signal(bool)

    def __init__(self, titel: str, offen: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Karte")
        aussen = QVBoxLayout(self)
        aussen.setContentsMargins(14, 10, 14, 12)
        aussen.setSpacing(8)

        self.kopf = _KartenKopf()
        self.kopf.setCursor(Qt.PointingHandCursor)
        kl = QHBoxLayout(self.kopf)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.setSpacing(8)
        punkt = QLabel("●")
        punkt.setStyleSheet(f"color:{theme.TEAL};font-size:9pt;background:transparent;")
        self.titel = QLabel(titel)
        self.titel.setStyleSheet("font-weight:600;background:transparent;")
        self.pfeil = QLabel()
        self.pfeil.setStyleSheet(f"color:{theme.TEXT_GEDAEMPFT};background:transparent;")
        kl.addWidget(punkt)
        kl.addWidget(self.titel)
        kl.addStretch(1)
        kl.addWidget(self.pfeil)
        self.kopf.geklickt.connect(self.umschalten)
        aussen.addWidget(self.kopf)

        self.inhalt = QWidget()
        self.layout_inhalt = QVBoxLayout(self.inhalt)
        self.layout_inhalt.setContentsMargins(0, 4, 0, 0)
        self.layout_inhalt.setSpacing(8)
        aussen.addWidget(self.inhalt)
        self.setze_offen(offen)

    def setze_offen(self, offen: bool) -> None:
        self._offen = bool(offen)
        self.inhalt.setVisible(self._offen)
        self.pfeil.setText("▾" if self._offen else "▸")

    def umschalten(self) -> None:
        self.setze_offen(not self._offen)
        self.umgeschaltet.emit(self._offen)

    @property
    def offen(self) -> bool:
        return self._offen

    def add(self, w) -> None:
        if isinstance(w, QWidget):
            self.layout_inhalt.addWidget(w)
        else:
            self.layout_inhalt.addLayout(w)


class SchieberZeile(QWidget):
    """Beschriftung, Schieberegler und Wertanzeige in einer Zeile."""

    wert_geaendert = Signal(int)

    def __init__(self, text: str, minimum: int, maximum: int, wert: int,
                 einheit: str = "", tipp: str = "", formatierer=None, parent=None) -> None:
        super().__init__(parent)
        self._einheit = einheit
        self._formatierer = formatierer
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        oben = QHBoxLayout()
        oben.setContentsMargins(0, 0, 0, 0)
        self.beschriftung = QLabel(text)
        self.beschriftung.setObjectName("Gedaempft")
        self.anzeige = QLabel()
        self.anzeige.setObjectName("Wert")
        self.anzeige.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        oben.addWidget(self.beschriftung)
        oben.addStretch(1)
        oben.addWidget(self.anzeige)
        lay.addLayout(oben)
        self.schieber = QSlider(Qt.Horizontal)
        self.schieber.setRange(minimum, maximum)
        self.schieber.setValue(wert)
        self.schieber.valueChanged.connect(self._geaendert)
        lay.addWidget(self.schieber)
        if tipp:
            self.setToolTip(tipp)
        self._text_setzen(wert)

    def _text_setzen(self, w: int) -> None:
        if self._formatierer:
            self.anzeige.setText(self._formatierer(w))
        else:
            self.anzeige.setText(f"{w}{self._einheit}")

    def _geaendert(self, w: int) -> None:
        self._text_setzen(w)
        self.wert_geaendert.emit(w)

    def wert(self) -> int:
        return self.schieber.value()

    def setze(self, w: int, still: bool = False) -> None:
        if still:
            self.schieber.blockSignals(True)
        self.schieber.setValue(int(w))
        self._text_setzen(self.schieber.value())
        if still:
            self.schieber.blockSignals(False)


class Segmente(QWidget):
    """Segment-Auswahl (wie die Zeitbereich-Auswahl der Dashboards)."""

    gewaehlt = Signal(str)

    def __init__(self, eintraege: list[tuple[str, str]], gleich_breit: bool = True,
                 parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.gruppe = QButtonGroup(self)
        self.gruppe.setExclusive(True)
        self.knoepfe: dict[str, QPushButton] = {}
        n = len(eintraege)
        for i, (schluessel, text) in enumerate(eintraege):
            b = QPushButton(text)
            b.setCheckable(True)
            b.setObjectName("Segment")
            b.setCursor(Qt.PointingHandCursor)
            rad = []
            if i == 0:
                rad.append("border-top-left-radius:6px;border-bottom-left-radius:6px;")
            if i == n - 1:
                rad.append("border-top-right-radius:6px;border-bottom-right-radius:6px;")
            if i > 0:
                rad.append("margin-left:-1px;")
            if rad:
                b.setStyleSheet("QPushButton#Segment{" + "".join(rad) + "}")
            b.clicked.connect(lambda _=False, s=schluessel: self.gewaehlt.emit(s))
            self.gruppe.addButton(b)
            self.knoepfe[schluessel] = b
            lay.addWidget(b, 1 if gleich_breit else 0)

    def setze(self, schluessel: str) -> None:
        if schluessel in self.knoepfe:
            self.knoepfe[schluessel].setChecked(True)

    def aktuell(self) -> str:
        for k, b in self.knoepfe.items():
            if b.isChecked():
                return k
        return next(iter(self.knoepfe))


class FarbKnopf(QPushButton):
    """Kleiner Knopf, der eine Farbe zeigt und per Dialog ändert."""

    farbe_geaendert = Signal(str)

    def __init__(self, farbe: str = "#000000", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Farbe")
        self.setCursor(Qt.PointingHandCursor)
        self._farbe = farbe
        self._stil()
        self.clicked.connect(self._waehlen)

    def _stil(self) -> None:
        self.setStyleSheet(
            f"QPushButton#Farbe{{background:{self._farbe};border:1px solid {theme.LINIE};"
            f"border-radius:6px;}} QPushButton#Farbe:hover{{border-color:{theme.TEAL};}}")
        self.setToolTip(self._farbe.upper())

    def farbe(self) -> str:
        return self._farbe

    def setze(self, farbe: str, still: bool = False) -> None:
        self._farbe = QColor(farbe).name()
        self._stil()
        if not still:
            self.farbe_geaendert.emit(self._farbe)

    def _waehlen(self) -> None:
        f = QColorDialog.getColor(QColor(self._farbe), self.window(), "Farbe wählen")
        if f.isValid():
            self.setze(f.name())


def trenner() -> QFrame:
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{theme.LINIE};border:none;")
    return f
