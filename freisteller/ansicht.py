"""Bildansicht mit Karo-Hintergrund, Zoom, Pinsel und Pipette."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QImage, QPainter, QPen, QPixmap,
                           QFont)
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem,
                               QGraphicsScene, QGraphicsView)

from . import theme

HINTERGRUENDE = {
    "karo_dunkel": "Karo dunkel",
    "karo_hell": "Karo hell",
    "weiss": "Weiß",
    "schwarz": "Schwarz",
    "teal": "Teal",
}


def _karo(hell: bool) -> QPixmap:
    groesse = 12
    pm = QPixmap(groesse * 2, groesse * 2)
    a, b = (QColor("#FFFFFF"), QColor("#D6D9DE")) if hell else (QColor("#232830"), QColor("#1A1E24"))
    pm.fill(a)
    p = QPainter(pm)
    p.fillRect(0, 0, groesse, groesse, b)
    p.fillRect(groesse, groesse, groesse, groesse, b)
    p.end()
    return pm


class BildItem(QGraphicsItem):
    """Zeichnet ein QImage direkt (ohne Umweg über QPixmap)."""

    def __init__(self) -> None:
        super().__init__()
        self._bild: QImage | None = None
        self._puffer = None  # hält das numpy-Array am Leben

    def setze(self, bild: QImage | None, puffer=None) -> None:
        alt = self.boundingRect()
        self._bild = bild
        self._puffer = puffer
        if alt != self.boundingRect():
            self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802
        if self._bild is None:
            return QRectF()
        return QRectF(0, 0, self._bild.width(), self._bild.height())

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: D401
        if self._bild is None:
            return
        massstab = painter.worldTransform().m11()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, massstab < 1.0)
        bereich = option.exposedRect.intersected(self.boundingRect())
        bereich = bereich.toAlignedRect().adjusted(-1, -1, 1, 1).intersected(
            self.boundingRect().toRect())
        painter.drawImage(QRectF(bereich), self._bild, QRectF(bereich))


class BildAnsicht(QGraphicsView):
    dateien_abgelegt = Signal(list)
    strich_start = Signal()
    strich_teil = Signal(float, float, float, float)
    strich_ende = Signal()
    farbe_gewaehlt = Signal(int, int)
    position = Signal(int, int)
    zoom_geaendert = Signal(float)
    pinsel_radius_geaendert = Signal(float)

    WERKZEUGE = ("verschieben", "behalten", "entfernen", "pipette")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.item = BildItem()
        self.scene().addItem(self.item)
        self.cursor_kreis = QGraphicsEllipseItem()
        pen = QPen(QColor(theme.TEAL), 1.5)
        pen.setCosmetic(True)
        self.cursor_kreis.setPen(pen)
        self.cursor_kreis.setZValue(10)
        self.cursor_kreis.hide()
        self.scene().addItem(self.cursor_kreis)

        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        self._werkzeug = "verschieben"
        self._pinsel_radius = 20.0
        self._malt = False
        self._letzter: QPointF | None = None
        self._schwenkt = False
        self._schwenk_start = None
        self._hintergrund = "karo_dunkel"
        self._karo_dunkel = _karo(False)
        self._karo_hell = _karo(True)
        self._leer_text = True
        self._drag_aktiv = False
        self._pinsel_erlaubt = True
        self._werkzeug_cursor()

    # -- Inhalt ------------------------------------------------------------
    def setze_bild(self, bild: QImage | None, puffer=None, einpassen: bool = False) -> None:
        self.item.setze(bild, puffer)
        self._leer_text = bild is None
        if bild is not None:
            r = QRectF(0, 0, bild.width(), bild.height())
            rand = max(r.width(), r.height()) * 0.5
            self.setSceneRect(r.adjusted(-rand, -rand, rand, rand))
        if einpassen:
            self.einpassen()
        self.viewport().update()

    def bereich_aktualisieren(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self.item.update(QRectF(x0, y0, x1 - x0, y1 - y0))

    def setze_hintergrund(self, name: str) -> None:
        self._hintergrund = name if name in HINTERGRUENDE else "karo_dunkel"
        self.viewport().update()
        self.scene().update()

    def setze_pinsel_erlaubt(self, erlaubt: bool) -> None:
        self._pinsel_erlaubt = erlaubt
        self._werkzeug_cursor()

    # -- Zoom --------------------------------------------------------------
    def einpassen(self) -> None:
        r = self.item.boundingRect()
        if r.isEmpty():
            return
        self.resetTransform()
        self.fitInView(r.adjusted(-10, -10, 10, 10), Qt.KeepAspectRatio)
        if self.transform().m11() > 4:
            self.setTransform(self.transform().fromScale(4, 4))
            self.centerOn(r.center())
        self.zoom_geaendert.emit(self.transform().m11())
        self._kreis_aktualisieren()

    def originalgroesse(self) -> None:
        mitte = self.mapToScene(self.viewport().rect().center())
        self.resetTransform()
        self.centerOn(mitte)
        self.zoom_geaendert.emit(1.0)
        self._kreis_aktualisieren()

    def zoomen(self, faktor: float) -> None:
        aktuell = self.transform().m11()
        ziel = min(max(aktuell * faktor, 0.02), 40.0)
        f = ziel / aktuell
        self.scale(f, f)
        self.zoom_geaendert.emit(ziel)
        self._kreis_aktualisieren()

    def wheelEvent(self, ev) -> None:  # noqa: N802
        if ev.modifiers() & Qt.AltModifier:
            # Alt + Rad: Pinselgröße
            schritt = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
            self.setze_pinsel_radius(self._pinsel_radius * schritt)
            self.pinsel_radius_geaendert.emit(self._pinsel_radius)
            return
        delta = ev.angleDelta().y()
        if delta:
            self.zoomen(1.2 if delta > 0 else 1 / 1.2)

    # -- Werkzeuge ---------------------------------------------------------
    @property
    def werkzeug(self) -> str:
        return self._werkzeug

    def setze_werkzeug(self, name: str) -> None:
        self._werkzeug = name if name in self.WERKZEUGE else "verschieben"
        self._werkzeug_cursor()

    def setze_pinsel_radius(self, radius: float) -> None:
        self._pinsel_radius = float(min(max(radius, 1.0), 1000.0))
        self._kreis_aktualisieren()

    def _ist_pinsel(self) -> bool:
        return self._werkzeug in ("behalten", "entfernen") and self._pinsel_erlaubt

    def _werkzeug_cursor(self) -> None:
        if self._ist_pinsel():
            self.viewport().setCursor(Qt.CrossCursor)
            farbe = QColor(theme.TEAL if self._werkzeug == "behalten" else theme.ROT)
            pen = QPen(farbe, 1.5)
            pen.setCosmetic(True)
            self.cursor_kreis.setPen(pen)
        elif self._werkzeug == "pipette":
            self.viewport().setCursor(Qt.PointingHandCursor)
            self.cursor_kreis.hide()
        else:
            self.viewport().setCursor(Qt.OpenHandCursor)
            self.cursor_kreis.hide()

    def _kreis_aktualisieren(self, szene_pos: QPointF | None = None) -> None:
        if not self._ist_pinsel() or self.item.boundingRect().isEmpty():
            self.cursor_kreis.hide()
            return
        if szene_pos is None:
            pos = self.viewport().mapFromGlobal(self.cursor().pos())
            if not self.viewport().rect().contains(pos):
                self.cursor_kreis.hide()
                return
            szene_pos = self.mapToScene(pos)
        r = self._pinsel_radius
        self.cursor_kreis.setRect(szene_pos.x() - r, szene_pos.y() - r, 2 * r, 2 * r)
        self.cursor_kreis.show()

    # -- Maus --------------------------------------------------------------
    def mousePressEvent(self, ev) -> None:  # noqa: N802
        hat_bild = not self.item.boundingRect().isEmpty()
        if ev.button() in (Qt.MiddleButton, Qt.RightButton) or (
                ev.button() == Qt.LeftButton and (self._werkzeug == "verschieben"
                                                  or not self._pinsel_erlaubt
                                                  and self._werkzeug != "pipette")):
            self._schwenkt = True
            self._schwenk_start = ev.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        if ev.button() == Qt.LeftButton and hat_bild:
            p = self.mapToScene(ev.position().toPoint())
            if self._werkzeug == "pipette":
                self.farbe_gewaehlt.emit(int(p.x()), int(p.y()))
                return
            if self._ist_pinsel():
                self._malt = True
                self._letzter = p
                self.strich_start.emit()
                self.strich_teil.emit(p.x(), p.y(), p.x(), p.y())
                return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        p = self.mapToScene(ev.position().toPoint())
        self.position.emit(int(p.x()), int(p.y()))
        if self._schwenkt and self._schwenk_start is not None:
            d = ev.position() - self._schwenk_start
            self._schwenk_start = ev.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(d.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(d.y()))
            return
        self._kreis_aktualisieren(p)
        if self._malt and self._letzter is not None:
            self.strich_teil.emit(self._letzter.x(), self._letzter.y(), p.x(), p.y())
            self._letzter = p
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        if self._schwenkt:
            self._schwenkt = False
            self._werkzeug_cursor()
            return
        if self._malt:
            self._malt = False
            self._letzter = None
            self.strich_ende.emit()
            return
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev) -> None:  # noqa: N802
        if self._werkzeug == "verschieben":
            self.einpassen()
        else:
            super().mouseDoubleClickEvent(ev)

    def leaveEvent(self, ev) -> None:  # noqa: N802
        self.cursor_kreis.hide()
        super().leaveEvent(ev)

    # -- Drag & Drop -------------------------------------------------------
    def dragEnterEvent(self, ev) -> None:  # noqa: N802
        if ev.mimeData().hasUrls() or ev.mimeData().hasImage():
            ev.acceptProposedAction()
            self._drag_aktiv = True
            self.viewport().update()
        else:
            ev.ignore()

    def dragMoveEvent(self, ev) -> None:  # noqa: N802
        if ev.mimeData().hasUrls() or ev.mimeData().hasImage():
            ev.acceptProposedAction()
        else:
            ev.ignore()

    def dragLeaveEvent(self, ev) -> None:  # noqa: N802
        self._drag_aktiv = False
        self.viewport().update()

    def dropEvent(self, ev) -> None:  # noqa: N802
        self._drag_aktiv = False
        self.viewport().update()
        md = ev.mimeData()
        dateien = [u.toLocalFile() for u in md.urls() if u.isLocalFile()]
        if dateien:
            self.dateien_abgelegt.emit(dateien)
        elif md.hasImage():
            self.dateien_abgelegt.emit([md.imageData()])
        ev.acceptProposedAction()

    # -- Zeichnen ----------------------------------------------------------
    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        painter.fillRect(rect, QColor(theme.FELD))
        r = self.item.boundingRect()
        if r.isEmpty():
            return
        painter.save()
        if self._hintergrund in ("karo_dunkel", "karo_hell"):
            # Karomuster in Bildschirmgröße, unabhängig vom Zoom
            pm = self._karo_hell if self._hintergrund == "karo_hell" else self._karo_dunkel
            ziel = self.mapFromScene(r).boundingRect()
            painter.resetTransform()
            painter.setClipRect(ziel)
            painter.fillRect(ziel, QBrush(pm))
        else:
            farbe = {"weiss": "#FFFFFF", "schwarz": "#000000",
                     "teal": theme.TEAL}[self._hintergrund]
            painter.fillRect(r, QColor(farbe))
        painter.restore()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        if not (self._leer_text or self._drag_aktiv):
            return
        painter.save()
        painter.resetTransform()
        vr = self.viewport().rect().adjusted(24, 24, -24, -24)
        pen = QPen(QColor(theme.TEAL if self._drag_aktiv else theme.LINIE), 2, Qt.DashLine)
        painter.setPen(pen)
        if self._drag_aktiv:
            painter.setBrush(QColor(29, 73, 67, 90))
        painter.drawRoundedRect(vr, 14, 14)
        f = QFont(theme.SCHRIFT, 15)
        f.setWeight(QFont.DemiBold)
        painter.setFont(f)
        painter.setPen(QColor(theme.TEAL if self._drag_aktiv else theme.TEXT))
        mitte = vr.center()
        painter.drawText(QRectF(vr.left(), mitte.y() - 40, vr.width(), 30),
                         Qt.AlignCenter, "Bild hierher ziehen")
        painter.setFont(QFont(theme.SCHRIFT, 10))
        painter.setPen(QColor(theme.TEXT_GEDAEMPFT))
        painter.drawText(QRectF(vr.left(), mitte.y() - 4, vr.width(), 50),
                         Qt.AlignCenter,
                         "PNG, JPG, BMP, WEBP, TIFF, GIF\n"
                         "oder Strg+O zum Öffnen, Strg+V zum Einfügen")
        painter.restore()
