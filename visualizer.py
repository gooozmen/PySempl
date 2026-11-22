import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget

BANDS = 16


class VisualizerWidget(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setMinimumHeight(170)

        self.levels = np.zeros(BANDS)
        self.edges = np.geomspace(1, 400, BANDS + 1).astype(int)

        timer = QTimer(self)
        timer.timeout.connect(self.tick)
        timer.start(16)

    def tick(self):
        spectrum = np.abs(np.fft.rfft(self.engine.scope * np.hanning(len(self.engine.scope))))
        spectrum /= len(self.engine.scope) / 4

        for i in range(BANDS):
            value = spectrum[self.edges[i]:self.edges[i + 1] + 1].max()
            level = np.clip((20 * np.log10(value + 1e-6) + 60) / 60, 0, 1)
            self.levels[i] = max(level, self.levels[i] * 0.85)

        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#050805"))

        w, h = self.width(), self.height()
        bar_w = w / BANDS
        for i in range(BANDS):
            bar_h = self.levels[i] * h
            color = QColor.fromHsv(int(120 * (1 - self.levels[i])), 255, 255)
            p.fillRect(int(i * bar_w + 2), int(h - bar_h), int(bar_w - 4), int(bar_h), color)
        p.end()
