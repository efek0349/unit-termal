"""Headless dogrulama: ffmpeg -> Capture -> decode -> palet -> PNG (Qt'siz)."""
import sys, time
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ThermalScope as ts

log = []

def w(msg):
    log.append(str(msg))

ff = ts.find_ffmpeg()
w(f"ffmpeg: {ff}")
if not ff:
    Path("selftest.log").write_text("\n".join(log), encoding="utf-8")
    sys.exit(1)

devices = ts.list_devices(ff)
w(f"devices: {devices}")
if not devices:
    Path("selftest.log").write_text("\n".join(log), encoding="utf-8")
    sys.exit(2)

errors = []
cap = ts.Capture(ff, devices[0], errors.append)
cap.start()

deadline = time.time() + 8
raw = None
while time.time() < deadline:
    raw = cap.snapshot()
    if raw is not None and cap.frame_count >= 5:
        break
    time.sleep(0.2)

w(f"frames={cap.frame_count} fps={cap.fps:.1f} errors={errors}")
cap.stop()

if raw is None:
    Path("selftest.log").write_text("\n".join(log), encoding="utf-8")
    sys.exit(3)

temps = ts.raw_to_celsius(raw, ts.DEFAULT_SCALE, ts.DEFAULT_OFFSET)
w(f"raw {raw.min()}..{raw.max()} mean {raw.mean():.0f}")
w("temp p2/p50/p98 = " + ", ".join(f"{v:.1f}" for v in np.percentile(temps, [2, 50, 98])))
w(f"temp min/max = {temps.min():.1f} / {temps.max():.1f} C")

agc = ts.AutoGain()
agc.update(temps)
pals = ts.Palette.load_all(Path(__file__).resolve().parent / "palettes")
w("palettes: " + ", ".join(p.name for p in pals))
pal = next(p for p in pals if p.name == "Iron")
idx = ts.celsius_to_index(temps, agc.lo, agc.hi)
rgb = np.repeat(np.repeat(pal.lut[idx], 3, axis=0), 3, axis=1)
Image.fromarray(rgb).save("selftest_iron.png")
w(f"span {agc.lo:.1f}..{agc.hi:.1f}; wrote selftest_iron.png")

Path("selftest.log").write_text("\n".join(log), encoding="utf-8")
