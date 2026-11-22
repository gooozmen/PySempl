import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QPushButton, QSlider, QTabWidget, QVBoxLayout, QWidget
)

from engine import AudioEngine, PAD_COUNT
from visualizer import VisualizerWidget


class WaveformPlot(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.setBackground('#1e1f20')
        self.showGrid(x=True, y=True, alpha=0.15)
        for axis_name in ('left', 'bottom'):
            axis = self.getAxis(axis_name)
            axis.setPen(pg.mkPen('#444746'))
            axis.setTextPen(pg.mkPen('#9aa0a6'))
        self.setMouseEnabled(x=False, y=False)
        self.hideButtons()
        self.lines = []

    def show_wave(self, y, sr):
        time_axis = np.linspace(0, len(y) / sr, len(y))
        self.clear()
        self.lines = []
        self.plot(time_axis, y, pen=pg.mkPen(color='#a8c7fa', width=1))

    def show_slices(self, duration, count):
        for line in self.lines:
            self.removeItem(line)
        self.lines = []

        # count частей = count - 1 внутренних границ
        for i in range(1, count):
            line = pg.InfiniteLine(pos=duration / count * i, pen=pg.mkPen('red', width=2))
            self.addItem(line)
            self.lines.append(line)


class EffectCard(QGroupBox):
    def __init__(self, title, default_level=50, parent=None):
        super().__init__(title, parent)

        self.check = QCheckBox("Enable")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(default_level)
        self.label = QLabel(f"{default_level}%")

        layout = QVBoxLayout(self)
        layout.addWidget(self.check)

        row = QHBoxLayout()
        row.addWidget(QLabel("Level"))
        row.addWidget(self.slider)
        row.addWidget(self.label)
        layout.addLayout(row)

        self.slider.valueChanged.connect(lambda v: self.label.setText(f"{v}%"))

    def is_enabled(self):
        return self.check.isChecked()

    def level(self):
        return self.slider.value() / 100


class SamplerTab(QWidget):
    pad_clicked = pyqtSignal(int)

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        self.wave_plot = WaveformPlot()
        main_layout.addWidget(self.wave_plot, stretch=1)

        self.visualizer = VisualizerWidget(self.engine)
        main_layout.addWidget(self.visualizer, stretch=1)

        control_layout = QHBoxLayout()

        self.btn_open = QPushButton("Open Audio File")
        self.btn_open.setObjectName("accent")
        self.btn_open.clicked.connect(self.open_audio_file)
        control_layout.addWidget(self.btn_open)

        self.check_poly = QCheckBox("Polyphony")
        control_layout.addWidget(self.check_poly)

        self.cut_eghte = QPushButton("Cut to 8 parts")
        self.cut_eghte.clicked.connect(self.cut_sample)

        control_layout.addStretch()
        main_layout.addLayout(control_layout)

        vol_layout = QHBoxLayout()
        volume_title = QLabel("Volume")
        volume_title.setObjectName("hint")
        vol_layout.addWidget(volume_title)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setPageStep(5)
        vol_layout.addWidget(self.volume_slider)

        self.volume_value_label = QLabel("50%")
        self.volume_value_label.setObjectName("value")
        self.volume_value_label.setFixedWidth(40)
        self.volume_value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        vol_layout.addWidget(self.volume_value_label)

        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.on_volume_changed(self.volume_slider.value())

        vol_layout.addWidget(self.cut_eghte)
        main_layout.addLayout(vol_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        self.pad_buttons = []
        for i in range(PAD_COUNT):
            btn = QPushButton(f"Pad {i + 1}")
            btn.setToolTip(f"Key {i + 1}")
            btn.clicked.connect(lambda checked, idx=i: self.play_pad(idx))
            self.pad_buttons.append(btn)
            buttons_layout.addWidget(btn)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.clicked.connect(lambda: self.engine.stop_all())
        buttons_layout.addWidget(self.btn_stop)

        main_layout.addLayout(buttons_layout)

    def cut_sample(self):
        if self.engine.split():
            duration = len(self.engine.y) / self.engine.sr
            self.wave_plot.show_slices(duration, PAD_COUNT)

    def play_pad(self, index):
        self.engine.play(index, self.check_poly.isChecked())
        self.pad_clicked.emit(index)

    def open_audio_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            "",
            "Audio Files (*.wav *.mp3);;All Files (*)"
        )
        if not file_path:
            return

        try:
            y, sr = self.engine.load(file_path)
            self.wave_plot.show_wave(y, sr)
        except Exception as e:
            print(f"Ошибка файла: {e}")

    def on_volume_changed(self, value):
        self.volume_value_label.setText(f"{value}%")
        self.engine.set_volume(value / 100)


class EffectsTab(QWidget):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.all_effects = dict(engine.effects[0])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Apply to"))

        self.effect_target = QComboBox()
        self.effect_target.addItem("All pads", None)
        for i in range(PAD_COUNT):
            self.effect_target.addItem(f"Pad {i + 1}", i)
        target_layout.addWidget(self.effect_target, stretch=1)
        layout.addLayout(target_layout)

        self.distortion = EffectCard("Distortion", default_level=50)
        layout.addWidget(self.distortion)

        self.reverb = EffectCard("Reverb", default_level=30)
        layout.addWidget(self.reverb)

        self.btn_apply_effects = QPushButton("Apply effects")
        self.btn_apply_effects.setObjectName("accent")
        self.btn_apply_effects.clicked.connect(self.apply_effects)
        layout.addWidget(self.btn_apply_effects)

        layout.addStretch()

        self.effect_target.currentIndexChanged.connect(self.load_effect_settings)

        self.distortion.check.toggled.connect(self.apply_effects)
        self.reverb.check.toggled.connect(self.apply_effects)
        self.distortion.slider.sliderReleased.connect(self.apply_effects)
        self.reverb.slider.sliderReleased.connect(self.apply_effects)

    def select_pad(self, index):
        self.effect_target.setCurrentIndex(index + 1)

    def reset_effects(self):
        self.all_effects = dict(self.engine.effects[0])
        self.load_effect_settings()

    def load_effect_settings(self, index=None):
        target = self.effect_target.currentData()
        values = self.all_effects if target is None else self.engine.effects[target]

        widgets = (
            self.distortion.check,
            self.distortion.slider,
            self.reverb.check,
            self.reverb.slider,
        )
        for widget in widgets:
            widget.blockSignals(True)

        self.distortion.check.setChecked(values["distortion"])
        self.distortion.slider.setValue(int(values["distortion_level"] * 100))
        self.reverb.check.setChecked(values["reverb"])
        self.reverb.slider.setValue(int(values["reverb_level"] * 100))

        for widget in widgets:
            widget.blockSignals(False)

        self.distortion.label.setText(f"{self.distortion.slider.value()}%")
        self.reverb.label.setText(f"{self.reverb.slider.value()}%")

    def apply_effects(self, *args):
        target = self.effect_target.currentData()
        values = {
            "distortion": self.distortion.is_enabled(),
            "distortion_level": self.distortion.level(),
            "reverb": self.reverb.is_enabled(),
            "reverb_level": self.reverb.level(),
        }

        self.engine.apply_effects(target, **values)

        if target is None:
            self.all_effects = values


class SamplerUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sampler UI Design")
        self.resize(800, 550)

        self.engine = AudioEngine()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.sampler_tab = SamplerTab(self.engine)
        self.effects_tab = EffectsTab(self.engine)

        self.tabs.addTab(self.sampler_tab, "Sampler")
        self.tabs.addTab(self.effects_tab, "Effects")

        self.sampler_tab.pad_clicked.connect(self.effects_tab.select_pad)
        self.sampler_tab.cut_eghte.clicked.connect(self.effects_tab.reset_effects)

        self.pad_shortcuts = []
        for i in range(PAD_COUNT):
            shortcut = QShortcut(QKeySequence(str(i + 1)), self)
            shortcut.activated.connect(lambda idx=i: self.sampler_tab.play_pad(idx))
            self.pad_shortcuts.append(shortcut)

    def closeEvent(self, event):
        self.engine.close()
        event.accept()
