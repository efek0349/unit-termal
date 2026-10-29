"""UI mantik testi: AGC <-> Alt/Ust etkilesimi."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from PySide6.QtWidgets import QApplication

import ThermalScope as ts

app = QApplication(sys.argv)
win = ts.MainWindow()
lines = []

# 1) AGC acikken spin degistir -> AGC kapanmali, deger korunmali
win.agc_check.setChecked(True)
win.on_agc()
win.min_spin.setValue(12.5)
win.max_spin.setValue(41.5)
lines.append(f"agc_checked_after_edit={win.agc_check.isChecked()}")
lines.append(f"settings_min={win.settings.manual_min} settings_max={win.settings.manual_max}")
lines.append(f"spin_values={win.min_spin.value()}/{win.max_spin.value()}")
lines.append(f"hint='{win.span_hint.text()[:40]}'")

# 2) AGC'yi tekrar ac -> pencere devralinmali
win.agc.lo, win.agc.hi = 17.0, 33.0
win.agc_check.setChecked(True)
win.on_agc()
lines.append(f"after_agc_on: spins={win.min_spin.value()}/{win.max_spin.value()} hint='{win.span_hint.text()[:30]}'")

Path("uitest.log").write_text("\n".join(lines), encoding="utf-8")
win.close()
app.quit()
