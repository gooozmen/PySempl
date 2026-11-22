import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from ui import SamplerUI

CSS_PATH = Path(__file__).with_name("dark_theme.css")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(CSS_PATH.read_text(encoding="utf-8"))
    window = SamplerUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
