"""Dondurme/ayna kod yolu testi (gercek kamera, offscreen)."""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import ThermalScope as ts

# saf fonksiyon testi
a = np.arange(6).reshape(2, 3)
assert ts.orient(a, 0).shape == (2, 3)
assert ts.orient(a, 90).shape == (3, 2)
assert ts.orient(a, 180).shape == (2, 3)
assert ts.orient(a, 270).shape == (3, 2)
assert ts.orient(a, 0, True, False)[0, 0] == a[0, 2]
assert ts.orient(a, 0, False, True)[0, 0] == a[1, 0]
r = ts.orient(a, 90)
assert r[0, -1] == a[0, 0], (r, a)      # 90 sağa: sol üst -> sağ üst

app = QApplication(sys.argv)
win = ts.MainWindow()
win.show()
log = []


def step():
    win.rot_combo.setCurrentIndex(1)          # 90 sağa
    win.mirror_h_btn.setChecked(True)
    win.on_orientation_toggle()
    log.append(f"settings rotation={win.settings.rotation} mirror_h={win.settings.mirror_h}")


def finish():
    log.append(f"ctx={win.view._src_size} temps={None if win.last_temps is None else win.last_temps.shape}")
    log.append("status=" + win.status.text().replace("\n", " | "))
    win.grab().save("rot_grab.png")
    Path("rottest.log").write_text("\n".join(log), encoding="utf-8")
    app.quit()


QTimer.singleShot(6000, step)
QTimer.singleShot(7500, finish)
app.exec()
