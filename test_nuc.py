"""NUC (flat field) kod yolunu gercek kamera ile test eder."""
import sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import ThermalScope as ts

QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Ok)

app = QApplication(sys.argv)
win = ts.MainWindow()
win.show()

log = []

def step1():
    log.append(f"frames={getattr(win.capture, 'frame_count', 0)} raw={'yes' if win.last_raw is not None else 'no'}")
    win.acquire_nuc()

def step2():
    log.append(f"nuc={'set' if win.nuc is not None else 'none'} shape={None if win.nuc is None else win.nuc.shape}")
    log.append(f"file_exists={ts.SETTINGS_DIR.joinpath('nuc.npy').exists()}")
    if win.nuc is not None:
        log.append(f"nuc mean={win.nuc.mean():.2f} std={win.nuc.std():.2f} min={win.nuc.min():.1f} max={win.nuc.max():.1f}")
    log.append(f"status={win.status.text()}")
    Path("nuctest.log").write_text("\n".join(log), encoding="utf-8")
    app.quit()

QTimer.singleShot(5000, step1)
QTimer.singleShot(9000, step2)
app.exec()
