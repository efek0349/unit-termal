#!/usr/bin/env python3
"""
ThermalScope - UNI-T / Guide termal kamera goruntuleyici (Windows)

Mobil "Thermal Mobile" uygulamasinin yaptigini PC'de yapar:
  * UVC kamerasinin 256x384 YUY2 akisini acar (Windows Kamera uygulamasinin
    gri gordugu akis), icindeki 16-bit radyometrik veriyi cozer,
  * palet + otomatik olcek (AGC) ile renkli termal goruntu uretir,
  * imlec/maks/min/merkez/ortalama sicakliklarini gosterir,
  * kalibrasyon ve fotograf kaydetme sunar.

Veri yolu: ffmpeg (DirectShow) -> raw YUY2 -> numpy -> QImage.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, Signal, QObject
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QFont, QLinearGradient, QBrush
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QLabel, QPushButton, QComboBox, QCheckBox,
    QDoubleSpinBox, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QMessageBox,
    QDialog, QListWidget, QDialogButtonBox, QSizePolicy, QFormLayout, QSlider, QScrollArea, QFrame,
    QAbstractSpinBox,
)

APP_NAME = "ThermalScope"
APP_VERSION = "1.0.0"
APP_AUTHOR = "efek"
GITHUB_URL = "https://github.com/efek0349"
TELEGRAM_URL = "https://t.me/efek0349"
GPG_KEY = "0x2BE4D2A863E2EAB4"
BASE_DIR = Path(__file__).resolve().parent
PALETTE_DIR = BASE_DIR / "palettes"
SETTINGS_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "ThermalScope"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# --- uygulama ikonu (256x256 PNG, Iron paleti + nişangah) ------------------
ICON_PNG_B64 = (
    "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"
    "/z+MWmbwYYGYZQAAAABJRU5ErkJggg=="
)

def app_icon():
    """Gömülü base64 PNG'den QIcon üretir (harici dosya gerekmez)."""
    from PySide6.QtGui import QIcon, QPixmap
    pm = QPixmap()
    pm.loadFromData(base64.b64decode(ICON_PNG_B64), "PNG")
    return QIcon(pm)


def materialize_icon_file() -> Path:
    """Kısayolun kullanabilmesi için ikonu %APPDATA% altına yazar."""
    target = SETTINGS_DIR / "ThermalScope.png"
    try:
        if not target.exists() or target.stat().st_size < 1000:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(ICON_PNG_B64))
    except Exception:
        pass
    return target


STREAM_W, STREAM_H = 256, 384          # packed 16-bit layout (two 256x192 planes)
SENSOR_W, SENSOR_H = 256, 192
ZOOM = 3                                # display magnification
DEFAULT_SCALE = 1.0 / 1024.0            # degC per count (measured)
DEFAULT_OFFSET = 2.359375               # degC at raw 18064


# ----------------------------------------------------------------------------
# settings
# ----------------------------------------------------------------------------

@dataclass
class Settings:
    device: str = ""
    ffmpeg: str = ""
    palette: str = "Iron"
    auto_scale: bool = True
    manual_min: float = 15.0
    manual_max: float = 40.0
    scale: float = DEFAULT_SCALE
    offset: float = DEFAULT_OFFSET
    nuc_enabled: bool = True
    sharpen: bool = True
    contrast: float = 1.0
    shading: bool = True
    detail: float = 0.35
    rotation: int = 0
    mirror_h: bool = False
    mirror_v: bool = False

    @staticmethod
    def load() -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            s = Settings()
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            return s
        except Exception:
            return Settings()

    def save(self) -> None:
        try:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except Exception:
            pass


# ----------------------------------------------------------------------------
# palettes
# ----------------------------------------------------------------------------

@dataclass
class Palette:
    name: str
    lut: np.ndarray  # (256, 3) uint8

    @staticmethod
    def load_all(folder: Path) -> list["Palette"]:
        out: list[Palette] = []
        if not folder.is_dir():
            return out
        for path in sorted(folder.iterdir()):
            try:
                if path.suffix.lower() == ".rgb":
                    lut = Palette._parse_rgb(path)
                elif path.suffix.lower() == ".txt":
                    lut = Palette._parse_565(path)
                else:
                    continue
            except Exception:
                continue
            if lut is not None:
                out.append(Palette(path.stem, lut))
        if not out:
            out.append(Palette("Gray", Palette._gray()))
        return out

    @staticmethod
    def _gray() -> np.ndarray:
        g = np.arange(256, dtype=np.uint8)
        return np.stack([g, g, g], axis=1)

    @staticmethod
    def _parse_rgb(path: Path) -> np.ndarray | None:
        """24-bit palet: 256 satır, her satır 'RRGGBB' (mobil uygulama 4.1.2'den)."""
        rows: list[tuple[int, int, int]] = []
        for line in path.read_text(encoding="ascii", errors="ignore").splitlines():
            line = line.strip().lstrip("#")
            if len(line) < 6:
                continue
            rows.append((int(line[0:2], 16), int(line[2:4], 16), int(line[4:6], 16)))
            if len(rows) == 256:
                break
        if len(rows) != 256:
            return None
        return np.array(rows, dtype=np.uint8)

    @staticmethod
    def _parse_565(path: Path) -> np.ndarray | None:
        """Eski RGB565 palet (3.x sürümünden); 24-bit yoksa yedek yol."""
        text = path.read_text(encoding="utf-8", errors="ignore")
        values = [int(m, 16) for m in re.findall(r"0x([0-9A-Fa-f]{1,4})", text)]
        if len(values) != 256:
            return None
        v = np.array(values, dtype=np.uint32)
        r = ((v >> 11) & 0x1F) * 255 // 31
        g = ((v >> 5) & 0x3F) * 255 // 63
        b = (v & 0x1F) * 255 // 31
        return np.stack([r, g, b], axis=1).astype(np.uint8)


# ----------------------------------------------------------------------------
# capture
# ----------------------------------------------------------------------------

def find_ffmpeg(configured: str = "") -> str | None:
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    candidates: list[str] = []
    if configured:
        candidates.append(configured)
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if part:
            candidates.append(str(Path(part) / exe))
    candidates.append(str(BASE_DIR / exe))
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        candidates.append(str(Path(local) / "Microsoft" / "WinGet" / "Links" / exe))
    candidates.append(r"C:\ffmpeg\bin\ffmpeg.exe")
    for c in candidates:
        try:
            if Path(c).is_file():
                return c
        except OSError:
            continue
    return None


def list_devices(ffmpeg: str) -> list[str]:
    args = [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
    try:
        res = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=15,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,  # Terminal penceresini gizle
        )
        text = (res.stderr or "") + (res.stdout or "")
    except Exception:
        return []

    names: list[str] = []
    for line in text.splitlines():
        m = re.search(r'"([^"]+)"\s*\((video|none|audio)\)', line)
        if not m:
            continue
        if m.group(2) == "audio":
            continue
        if m.group(1) not in names:
            names.append(m.group(1))
    return names


class Capture(threading.Thread):
    """Reads packed YUY2 frames from ffmpeg and publishes the latest 16-bit frame."""

    def __init__(self, ffmpeg: str, device: str, on_error):
        super().__init__(daemon=True)
        self.ffmpeg = ffmpeg
        self.device = device
        self.on_error = on_error
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest: np.ndarray | None = None      # (192,256) uint16
        self.fps = 0.0
        self.frame_count = 0
        self._proc: subprocess.Popen | None = None

    def run(self) -> None:
        args = [
            self.ffmpeg, "-hide_banner", "-loglevel", "error",
            "-fflags", "nobuffer", "-flags", "low_delay",
            "-f", "dshow", "-rtbufsize", "256M",
            "-video_size", f"{STREAM_W}x{STREAM_H}", "-framerate", "25",
            "-i", f"video={self.device}",
            "-an", "-f", "rawvideo", "-pix_fmt", "yuyv422", "-",
        ]
        try:
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                creationflags=subprocess.CREATE_NO_WINDOW,  # Terminal penceresini gizle
            )
        except Exception as exc:  # pragma: no cover
            self.on_error(f"ffmpeg başlatılamadı: {exc}")
            return

        frame_size = STREAM_W * STREAM_H * 2
        t_last = time.time()
        frames = 0

        while not self.stop_event.is_set():
            buf = bytearray()
            while len(buf) < frame_size:
                chunk = self._proc.stdout.read(frame_size - len(buf))
                if not chunk:
                    break
                buf.extend(chunk)
            if len(buf) < frame_size:
                break

            plane = np.frombuffer(bytes(buf), dtype=np.uint8).reshape(STREAM_H, STREAM_W, 2)
            hi = plane[0:SENSOR_H, :, 0].astype(np.uint16)
            lo = plane[SENSOR_H:STREAM_H, :, 0].astype(np.uint16)
            raw = (hi << 8) | lo

            with self.lock:
                self.latest = raw
                self.frame_count += 1
                frames += 1

            now = time.time()
            if now - t_last >= 1.0:
                self.fps = frames / (now - t_last)
                frames = 0
                t_last = now

        if not self.stop_event.is_set():
            err = ""
            try:
                err = (self._proc.stderr.read() or b"").decode("utf-8", "replace").strip()
            except Exception:
                pass
            self.on_error("Kamera akışı durdu" + (f": {err.splitlines()[-1]}" if err else "."))

    def snapshot(self) -> np.ndarray | None:
        with self.lock:
            return None if self.latest is None else self.latest.copy()

    def stop(self) -> None:
        self.stop_event.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def raw_to_celsius(raw: np.ndarray, scale: float, offset: float) -> np.ndarray:
    return raw.astype(np.float32) * scale + offset


def celsius_to_index(temps: np.ndarray, lo: float, hi: float) -> np.ndarray:
    span = max(hi - lo, 1e-6)
    idx = (temps - lo) * (255.0 / span)
    return np.clip(idx, 0, 255).astype(np.uint8)


def apply_contrast(idx: np.ndarray, gain: float) -> np.ndarray:
    """S-curve around mid grey - the 'contrast' knob every thermal app has."""
    if abs(gain - 1.0) < 0.02:
        return idx
    out = 128.0 + (idx.astype(np.float32) - 128.0) * gain
    return np.clip(out, 0, 255).astype(np.uint8)


def despeckle(img: np.ndarray, threshold: float = 150.0) -> np.ndarray:
    """
    Replaces hot / dead pixels: a pixel that differs from the 3x3 median by more
    than `threshold` raw counts is a detector defect, not scene content.
    """
    p = np.pad(img, 1, mode="edge")
    stack = np.stack([p[dy:dy + img.shape[0], dx:dx + img.shape[1]]
                      for dy in range(3) for dx in range(3)], axis=0)
    med = np.median(stack, axis=0)
    mask = np.abs(img - med) > threshold
    if not mask.any():
        return img
    out = img.copy()
    out[mask] = med[mask]
    return out


def box_blur(a: np.ndarray, radius: int = 20) -> np.ndarray:
    """Fast separable mean filter (running sum) - used to estimate the shading field."""
    if radius < 1:
        return a

    f = a.astype(np.float32)
    h, w = f.shape
    r = int(min(radius, h - 1, w - 1))
    if r < 1:
        return f

    pad = np.pad(f, ((0, 0), (r, r)), mode="edge")
    cs = np.cumsum(pad, axis=1)
    cs = np.concatenate([np.zeros((h, 1), np.float32), cs], axis=1)
    f = (cs[:, 2 * r + 1:] - cs[:, :-2 * r - 1]) / (2 * r + 1)

    pad = np.pad(f, ((r, r), (0, 0)), mode="edge")
    cs = np.cumsum(pad, axis=0)
    cs = np.concatenate([np.zeros((1, w), np.float32), cs], axis=0)
    return (cs[2 * r + 1:, :] - cs[:-2 * r - 1, :]) / (2 * r + 1)


def fix_shading(idx: np.ndarray, strength: float = 0.55, radius: int = 24) -> np.ndarray:
    """
    Display-only shadow removal: subtracts the slow illumination / fixed-pattern
    gradient so the picture looks flat like the phone app. It works on the
    palette index, so absolute temperatures are untouched.
    """
    if strength <= 0.0:
        return idx
    base = box_blur(idx, radius)
    out = idx.astype(np.float32) + strength * (idx.astype(np.float32) - base)
    return np.clip(out, 0, 255).astype(np.uint8)


def smooth_temporal(prev: np.ndarray | None, raw: np.ndarray, alpha: float = 0.35) -> np.ndarray:
    """Exponential moving average in the raw domain (kills sensor noise)."""
    cur = raw.astype(np.float32)
    if prev is None or prev.shape != cur.shape:
        return cur
    return prev + (cur - prev) * alpha


def blur3(arr: np.ndarray) -> np.ndarray:
    """Separable 1-2-1 blur - the small spatial smoothing a thermal imager normally applies."""
    p = np.pad(arr, ((1, 1), (0, 0)), mode="edge")
    a = (p[:-2, :] + 2.0 * p[1:-1, :] + p[2:, :]) * 0.25
    q = np.pad(a, ((0, 0), (1, 1)), mode="edge")
    return (q[:, :-2] + 2.0 * q[:, 1:-1] + q[:, 2:]) * 0.25


def adaptive_temporal(prev: np.ndarray | None, raw: np.ndarray,
                      sigma: float = 4.0) -> np.ndarray:
    """
    Motion-adaptive recursive filter.

    Static pixels get heavy averaging (noise disappears); pixels that change
    faster than the sensor noise (real motion) are updated almost instantly, so
    the image does not smear or leave shadows behind moving objects.
    """
    cur = raw.astype(np.float32)
    if prev is None or prev.shape != cur.shape:
        return cur

    diff = cur - prev
    motion = np.clip(np.abs(diff) / (sigma * 2.0), 0.0, 1.0)
    alpha = 0.22 + 0.73 * motion          # 0.22 static ... 0.95 moving
    return prev + alpha * diff


def unsharp(img: np.ndarray, amount: float = 0.8) -> np.ndarray:
    """Restores the edge crispness that smoothing takes away."""
    blurred = blur3(img)
    return img + amount * (img - blurred)


def enhance_detail(img: np.ndarray, amount: float) -> np.ndarray:
    """
    DDE (digital detail enhancement): geniş yarıçaplı unsharp ile orta ölçekli
    detayı belirginleştirir - telefon uygulamasındaki 'keskin/canlı' görünümün
    PC tarafındaki karşılığı.
    """
    if amount <= 0.02:
        return img
    base = blur3(blur3(img))
    return img + amount * (img - base)


def flat_field(raw: np.ndarray, nuc: np.ndarray) -> np.ndarray:
    """Subtract the per-pixel offset measured with the lens covered."""
    return raw.astype(np.float32) - nuc


def orient(arr: np.ndarray, rotation: int = 0, mirror_h: bool = False,
           mirror_v: bool = False) -> np.ndarray:
    """
    Görüntü yönü: ayna + saat yönünde döndürme (0/90/180/270).
    Kamera yatay tutulduğunda görüntüyü dik hâle getirmek için kullanılır.
    """
    out = arr
    if mirror_h:
        out = out[:, ::-1]
    if mirror_v:
        out = out[::-1, :]
    k = (int(rotation) // 90) % 4
    if k:
        out = np.rot90(out, -k)          # -k => saat yönünde
    return np.ascontiguousarray(out)


class AutoGain:
    def __init__(self) -> None:
        self.lo = 15.0
        self.hi = 40.0
        self._primed = False

    def reset(self) -> None:
        self._primed = False

    def update(self, temps: np.ndarray, smoothing: float = 0.30) -> None:
        sample = temps[::7].ravel()
        if sample.size > 8192:
            sample = sample[:8192]
        lo, hi = np.percentile(sample, [2, 98])

        # Düz sahnelerede aralık aşırı daralıp gürültüyü büyütmesin: en az 6 K
        min_span = 6.0
        if hi - lo < min_span:
            mid = (hi + lo) / 2.0
            lo, hi = mid - min_span / 2.0, mid + min_span / 2.0

        if not self._primed:
            self.lo, self.hi = float(lo), float(hi)
            self._primed = True
            return
        self.lo += (float(lo) - self.lo) * smoothing
        self.hi += (float(hi) - self.hi) * smoothing


# ----------------------------------------------------------------------------
# widgets
# ----------------------------------------------------------------------------

class ThermalView(QWidget):
    """Renders the thermal image, colour bar overlays and the spot cursor."""

    spotMoved = Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._image: QImage | None = None
        self._src_size: tuple[int, int] = (SENSOR_W, SENSOR_H)
        self._spot: tuple[float, float] | None = None
        self._spot_text = ""
        self._mode_text = ""
        self._lut: np.ndarray | None = None
        self._span: tuple[float, float] = (15.0, 40.0)

    def set_scale(self, lut: np.ndarray, lo: float, hi: float) -> None:
        """Görüntünün sağ kenarına çizilen renk çubuğu için palet + sıcaklık aralığı."""
        self._lut = lut
        self._span = (float(lo), float(hi))

    def set_frame(self, rgb: np.ndarray, spot_text: str, mode_text: str) -> None:
        rgb = np.ascontiguousarray(rgb)
        h, w, _ = rgb.shape
        self._image = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()
        self._src_size = (w, h)
        self._spot_text = spot_text
        self._mode_text = mode_text
        self.update()

    def clear(self) -> None:
        self._image = None
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._image is None:
            return
        rect = self._image_rect()
        pos = event.position().toPoint()
        if not rect.contains(pos):
            self._spot = None
            return
        x = (pos.x() - rect.x()) * self._src_size[0] / max(rect.width(), 1)
        y = (pos.y() - rect.y()) * self._src_size[1] / max(rect.height(), 1)
        self._spot = (x, y)
        self.spotMoved.emit(x, y)
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._spot = None
        self.update()

    def _image_rect(self) -> QRect:
        if self._image is None:
            return QRect()
        iw, ih = self._image.width(), self._image.height()
        # aspect-fit with a small margin
        scale = min(self.width() * 0.98 / iw, self.height() * 0.98 / ih)
        w, h = int(iw * scale), int(ih * scale)
        return QRect((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def _to_widget(self, rect: QRect, x: float, y: float) -> tuple[float, float]:
        sx = rect.width() / max(self._src_size[0], 1)
        sy = rect.height() / max(self._src_size[1], 1)
        return rect.x() + x * sx, rect.y() + y * sy

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(12, 12, 14))
        if self._image is None:
            painter.setPen(QColor(140, 140, 140))
            painter.drawText(self.rect(), Qt.AlignCenter,
                             "Kamera bekleniyor…\n\nBaşlat düğmesine basın")
            return

        rect = self._image_rect()
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawImage(rect, self._image)

        # --- görüntü sağ kenarında renk çubuğu ---
        if self._lut is not None:
            bar_w = 12
            margin = 12
            top = rect.y() + 14
            bottom = rect.y() + rect.height() - 14
            x = rect.x() + rect.width() - bar_w - margin
            if bottom - top > 40:
                grad = QLinearGradient(x, top, x, bottom)
                grad.setColorAt(0.0, QColor(*(int(c) for c in self._lut[255])))
                grad.setColorAt(1.0, QColor(*(int(c) for c in self._lut[0])))
                painter.fillRect(QRect(x, top, bar_w, bottom - top), QBrush(grad))
                painter.setPen(QColor(0, 0, 0, 160))
                painter.drawRect(QRect(x, top, bar_w, bottom - top))

                lo, hi = self._span
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor(245, 245, 245))
                for label, y in (
                    (f"{hi:.0f} °C", top - 4),
                    (f"{(hi + lo) / 2:.0f} °C", (top + bottom) // 2 - 7),
                    (f"{lo:.0f} °C", bottom - 12),
                ):
                    box = QRect(x - 66, y, 62, 14)
                    painter.fillRect(QRect(box.x(), box.y(), box.width(), box.height()),
                                     QColor(0, 0, 0, 120))
                    painter.drawText(box, Qt.AlignRight | Qt.AlignVCenter, label)

        if self._spot is not None:
            cx, cy = self._to_widget(rect, self._spot[0], self._spot[1])
            painter.setPen(QPen(QColor(255, 255, 255, 235), 1.5))
            painter.drawLine(int(cx - 14), int(cy), int(cx + 14), int(cy))
            painter.drawLine(int(cx), int(cy - 14), int(cx), int(cy + 14))
            painter.drawEllipse(QPoint(int(cx), int(cy)), 4, 4)

            if self._spot_text:
                font = QFont("Segoe UI", 11, QFont.Bold)
                painter.setFont(font)
                metrics = painter.fontMetrics()
                tw = metrics.horizontalAdvance(self._spot_text) + 12
                th = metrics.height() + 6
                bx, by = int(cx + 14), int(cy + 14)
                painter.fillRect(QRect(bx, by, tw, th), QColor(0, 0, 0, 175))
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(QRect(bx + 6, by + 3, tw, th), Qt.AlignLeft | Qt.AlignVCenter, self._spot_text)

        if self._mode_text:
            painter.setFont(QFont("Segoe UI", 9))
            metrics = painter.fontMetrics()
            tw = metrics.horizontalAdvance(self._mode_text) + 10
            th = metrics.height() + 4
            painter.fillRect(QRect(8, self.height() - th - 10, tw, th), QColor(0, 0, 0, 150))
            painter.setPen(QColor(210, 210, 210))
            painter.drawText(QRect(13, self.height() - th - 10, tw, th), Qt.AlignLeft | Qt.AlignVCenter, self._mode_text)


# ----------------------------------------------------------------------------
# calibration dialog
# ----------------------------------------------------------------------------

class CalibrationDialog(QDialog):
    def __init__(self, parent, scale: float, offset: float, raw_getter):
        super().__init__(parent)
        self.setWindowTitle("Sıcaklık kalibrasyonu")
        self.resize(420, 460)
        self.scale = scale
        self.offset = offset
        self.raw_getter = raw_getter
        self.points: list[tuple[float, float]] = []

        self.live = QLabel("—")
        self.live.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.temp = QDoubleSpinBox()
        self.temp.setRange(-40, 600)
        self.temp.setDecimals(1)
        self.temp.setValue(20.0)
        self.temp.setSuffix(" °C")
        add = QPushButton("Noktayı ekle")
        add.clicked.connect(self.add_point)
        self.list = QListWidget()
        apply_btn = QPushButton("Uygula")
        apply_btn.clicked.connect(self.apply)
        reset_btn = QPushButton("Varsayılana dön")
        reset_btn.clicked.connect(self.reset)
        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.reject)

        hint = QLabel(
            "Kamerayı bilinen sıcaklıktaki bir yüzeye tutun\n"
            "(buzlu su ≈ 0 °C, kaynar su ≈ 100 °C, vücut ≈ 36.5 °C),\n"
            "gerçek değeri yazıp \"Noktayı ekle\" deyin.\n"
            "İki nokta birbirinden uzaksa doğruluk artar."
        )
        hint.setWordWrap(True)

        form = QFormLayout()
        form.addRow("İmleçteki değer:", self.live)
        form.addRow("Gerçek sıcaklık:", self.temp)
        form.addRow(add)

        buttons = QHBoxLayout()
        buttons.addWidget(apply_btn)
        buttons.addWidget(reset_btn)
        buttons.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Kalibrasyon noktaları:"))
        layout.addWidget(self.list)
        layout.addWidget(hint)
        layout.addLayout(buttons)

        self.result_scale: float | None = None
        self.result_offset: float | None = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_live)
        self.timer.start(250)
        self.update_live()

    def update_live(self) -> None:
        raw = self.raw_getter()
        if raw is None:
            self.live.setText("radyometrik veri yok")
            return
        t = raw * self.scale + self.offset
        self.live.setText(f"raw {raw}  →  {t:.1f} °C")

    def add_point(self) -> None:
        raw = self.raw_getter()
        if raw is None:
            QMessageBox.information(self, "Kalibrasyon", "Şu anda radyometrik veri yok.")
            return
        self.points.append((float(raw), float(self.temp.value())))
        self.list.addItem(f"raw {raw:7.0f}   →   {self.temp.value():.1f} °C")

    def apply(self) -> None:
        if not self.points:
            QMessageBox.information(self, "Kalibrasyon", "Önce en az bir nokta ekleyin.")
            return
        if len(self.points) == 1:
            raw, temp = self.points[0]
            self.result_scale = self.scale
            self.result_offset = temp - self.scale * raw
        else:
            raws = np.array([p[0] for p in self.points])
            temps = np.array([p[1] for p in self.points])
            a, b = np.polyfit(raws, temps, 1)
            self.result_scale = float(a)
            self.result_offset = float(b)
        self.accept()

    def reset(self) -> None:
        self.result_scale = DEFAULT_SCALE
        self.result_offset = DEFAULT_OFFSET
        self.accept()


# ----------------------------------------------------------------------------
# main window
# ----------------------------------------------------------------------------

class AboutDialog(QDialog):
    """Hakkında penceresi - geliştirici bilgileri ve teknik özet."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ThermalScope hakkında")
        self.setWindowIcon(app_icon())
        self.setFixedWidth(520)
        self.setStyleSheet("""
            QDialog { background:#202027; }
            QLabel { color:#d6d6d6; background:transparent; }
            QPushButton {
                background:#31313c; color:#f0f0f0; border:1px solid #44444f;
                border-radius:4px; padding:6px 18px;
            }
            QPushButton:hover { background:#3a3a48; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QHBoxLayout()
        logo = QLabel()
        pm = QPixmap()
        pm.loadFromData(base64.b64decode(ICON_PNG_B64), "PNG")
        logo.setPixmap(pm.scaled(76, 76, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setFixedSize(78, 78)

        title = QLabel(
            f"<div style='font-size:18px;font-weight:700;color:#ffffff'>ThermalScope "
            f"<span style='font-size:12px;color:#8f8f8f'>v{APP_VERSION}</span></div>"
            "<div style='color:#b9b9b9'>UNI-T / Guide UVC termal kamera görüntüleyici</div>"
            "<div style='color:#8f8f8f;font-size:11px'>Windows · Python + PySide6 · ffmpeg/DirectShow</div>"
        )
        header.addWidget(logo)
        header.addSpacing(8)
        header.addWidget(title, 1)
        layout.addLayout(header)

        body = QLabel(
            "<table cellspacing='0' cellpadding='3'>"
            f"<tr><td style='color:#9a9a9a'>Geliştirici</td><td><b>{APP_AUTHOR}</b> &nbsp;"
            f"<span style='color:#8f8f8f'>(@efek0349)</span></td></tr>"
            f"<tr><td style='color:#9a9a9a'>GitHub</td>"
            f"<td><a href='{GITHUB_URL}' style='color:#6ea8ff'>{GITHUB_URL}</a></td></tr>"
            f"<tr><td style='color:#9a9a9a'>Telegram</td>"
            f"<td><a href='{TELEGRAM_URL}' style='color:#6ea8ff'>{TELEGRAM_URL}</a></td></tr>"
            f"<tr><td style='color:#9a9a9a'>GPG</td><td><code style='color:#c8c8c8'>{GPG_KEY}</code></td></tr>"
            "<tr><td style='color:#9a9a9a'>Lisans</td><td>MIT</td></tr>"
            "</table>"
            "<hr style='border:0;border-top:1px solid #3a3a46;margin:10px 0'>"
            "<div style='color:#b9b9b9'><b>Nasıl çalışıyor?</b><br>"
            "Kamera 256×384 YUY2 modunda 16-bit radyometrik veriyi iki 8-bit düzlem olarak gönderir. "
            "Uygulama üst düzlemi yüksek bayt, alt düzlemi düşük bayt kabul edip ham değeri "
            "birleştirir; ardından sabit desen/gölge düzeltmesi, sıcak piksel onarımı, hareket "
            "uyarlamalı gürültü azaltma ve keskinleştirme uygular, ardından seçilen "
            "renk paletiyle renklendirir.<br><br>"
            "Sıcaklık, <b>T(°C) = a × ham + b</b> doğrusal modeliyle hesaplanır. Kameranın fabrika "
            "kalibrasyon eğrisi cihazın içinde çalıştığı için mutlak doğruluk adına "
            "<b>Kalibrasyon</b> penceresinden 1–2 referans noktası girmeniz önerilir.</div>"
            "<div style='color:#7f7f7f;font-size:11px;margin-top:8px'>"
            "Bu uygulama bağımsız bir araçtır; UNI-T / Guide Sensmart ile resmî bağlantısı yoktur.</div>"
        )
        body.setTextFormat(Qt.RichText)
        body.setOpenExternalLinks(True)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextBrowserInteraction)
        body.setStyleSheet("color:#d6d6d6;font-size:12px;")
        layout.addWidget(body)

        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close_btn)
        layout.addLayout(row)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"ThermalScope v{APP_VERSION} — UNI-T termal kamera görüntüleyici")
        self.setWindowIcon(app_icon())
        self.resize(1200, 740)

        self.settings = Settings.load()
        self.palettes = Palette.load_all(PALETTE_DIR)
        self.palette = next((p for p in self.palettes if p.name == self.settings.palette), self.palettes[0])
        self.agc = AutoGain()
        self.capture: Capture | None = None
        self.ffmpeg = find_ffmpeg(self.settings.ffmpeg)
        self.last_raw: np.ndarray | None = None
        self.last_temps: np.ndarray | None = None
        self.spot: tuple[int, int] | None = None
        self._ema: np.ndarray | None = None
        self.nuc: np.ndarray | None = self._load_nuc()

        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(40)

        self.refresh_devices()
        if self.ffmpeg is None:
            QMessageBox.warning(self, "ffmpeg bulunamadı",
                                "Görüntü DirectShow üzerinden ffmpeg ile alınır.\n"
                                "ffmpeg kurun (winget install Gyan.FFmpeg) veya ayarlarda yolunu belirtin.")
        elif self.device_combo.count() > 0:
            self.start_capture()
        else:
            # kamera henüz serbest kalmamış olabilir: kısa aralıklarla yeniden dene
            self._retries_left = 4
            QTimer.singleShot(1500, self._retry_start)

    def _retry_start(self) -> None:
        if self.capture and self.capture.is_alive():
            return
        self.refresh_devices()
        if self.device_combo.count() > 0:
            self.start_capture()
            return
        if getattr(self, "_retries_left", 0) > 0:
            self._retries_left -= 1
            QTimer.singleShot(1800, self._retry_start)

    # -- ui -------------------------------------------------------------
    def _make_temp_spin(self, value: float, lo: float, hi: float, tip: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setValue(value)
        spin.setSuffix(" °C")
        spin.setToolTip(tip)
        spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin.setAlignment(Qt.AlignCenter)
        spin.setMinimumHeight(30)
        spin.valueChanged.connect(self.on_span)
        return spin

    def _step_button(self, spin: QDoubleSpinBox, direction: int) -> QPushButton:
        btn = QPushButton("−" if direction < 0 else "+")
        btn.setFixedSize(38, 32)
        btn.setAutoRepeat(True)
        btn.setAutoRepeatDelay(350)
        btn.setAutoRepeatInterval(80)
        btn.setToolTip("0.5 °C azalt" if direction < 0 else "0.5 °C artır")
        btn.setStyleSheet("QPushButton{font-size:19px;font-weight:800;color:#ffffff;background:#3a3a48;border:1px solid #5a5a70;border-radius:4px;padding:0;} QPushButton:hover{background:#4c4c60;border-color:#7f8cff;} QPushButton:pressed{background:#2b2b35;}")
        btn.clicked.connect(lambda: self._bump(spin, direction))
        return btn

    def _bump(self, spin: QDoubleSpinBox, direction: int) -> None:
        value = spin.value() + direction * 0.5
        spin.setValue(round(min(max(value, spin.minimum()), spin.maximum()), 1))

    def _build_ui(self) -> None:
        self.view = ThermalView()
        self.view.spotMoved.connect(self.on_spot)
        self.view.set_scale(self.palette.lut, 15.0, 40.0)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        stage = QWidget()
        stage_row = QHBoxLayout(stage)
        stage_row.setContentsMargins(0, 0, 0, 0)
        stage_row.setSpacing(0)
        stage_row.addWidget(self.view, 1)
        root.addWidget(stage, 1)

        right = QWidget()
        right.setFixedWidth(320)
        right.setStyleSheet("""
            QWidget { background:#202027; color:#e8e8e8; }
            QLabel { color:#d6d6d6; }
            QComboBox, QDoubleSpinBox {
                background:#2c2c35; color:#f0f0f0; border:1px solid #3d3d48;
                border-radius:4px; padding:3px 6px; min-height:20px;
            }
            QComboBox QAbstractItemView { background:#2c2c35; color:#f0f0f0; selection-background-color:#3d5a80; }
            QPushButton {
                background:#31313c; color:#f0f0f0; border:1px solid #44444f;
                border-radius:4px; padding:6px 10px; min-height:22px;
            }
            QPushButton:hover { background:#3a3a48; }
            QPushButton:pressed { background:#26262e; }
            QPushButton:checked { background:#2f6fe0; border-color:#2f6fe0; }

            QCheckBox { color:#d6d6d6; spacing:8px; }
            QCheckBox::indicator {
                width:15px; height:15px;
                border:1px solid #5b5b6a; border-radius:3px;
                background:#2a2a33;
            }
            QCheckBox::indicator:hover { border-color:#7f8cff; }
            QCheckBox::indicator:checked {
                background:#3d7eff; border:1px solid #3d7eff;
                image:none;
            }
            QCheckBox::indicator:checked:hover { background:#5a93ff; border-color:#5a93ff; }

            QSlider::groove:horizontal {
                height:4px; background:#3a3a46; border-radius:2px;
            }
            QSlider::sub-page:horizontal { background:#3d7eff; border-radius:2px; }
            QSlider::handle:horizontal {
                background:#e8e8f0; width:12px; height:12px; margin:-5px 0;
                border-radius:6px;
            }
        """)
        panel = QVBoxLayout(right)
        panel.setContentsMargins(10, 10, 10, 8)
        panel.setSpacing(5)

        # --- cihaz + yenile + başlat/durdur: tek satır ---
        dev_row = QHBoxLayout()
        dev_row.setSpacing(5)
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(140)
        self.device_combo.setToolTip("Kaynak kamera")
        refresh = QPushButton("⟳")
        refresh.setFixedSize(30, 26)
        refresh.setToolTip("Cihazları yenile")
        refresh.clicked.connect(self.refresh_devices)
        self.start_btn = QPushButton("Başlat")
        self.start_btn.setFixedSize(78, 26)
        self.start_btn.clicked.connect(self.toggle_capture)
        dev_row.addWidget(self.device_combo, 1)
        dev_row.addWidget(refresh)
        dev_row.addWidget(self.start_btn)
        panel.addLayout(dev_row)

        # --- palet ---
        pal_row = QHBoxLayout()
        pal_row.setSpacing(6)
        pal_row.addWidget(QLabel("Palet"))
        self.palette_combo = QComboBox()
        for p in self.palettes:
            self.palette_combo.addItem(p.name)
        self.palette_combo.setCurrentText(self.palette.name)
        self.palette_combo.setToolTip(
            "256 adımlık renk tablosu (24-bit renk).\n"
            "Kamera verisi 16-bit radyometrik: piksel başına 65536 sıcaklık seviyesi."
        )
        self.palette_combo.currentTextChanged.connect(self.on_palette)
        pal_row.addWidget(self.palette_combo, 1)
        panel.addLayout(pal_row)

        # --- görüntü yönü (tek satır) ---
        rot_row = QHBoxLayout()
        rot_row.setSpacing(5)
        rot_row.addWidget(QLabel("Yön"))
        self.rot_combo = QComboBox()
        self.rot_combo.addItems(["Döndürme yok", "90° sağa", "180°", "90° sola"])
        self.rot_combo.setCurrentIndex(max(0, min(3, int(self.settings.rotation) // 90)))
        self.rot_combo.setToolTip("Kamera yatay tutulurken görüntüyü dik hâle getirir (R tuşu ile hızlı geçiş)")
        self.rot_combo.currentIndexChanged.connect(self.on_rotation)
        self.mirror_h_btn = QPushButton("⇄")
        self.mirror_h_btn.setCheckable(True)
        self.mirror_h_btn.setChecked(bool(self.settings.mirror_h))
        self.mirror_h_btn.setFixedSize(30, 26)
        self.mirror_h_btn.setToolTip("Yatay ayna")
        self.mirror_h_btn.clicked.connect(self.on_orientation_toggle)
        self.mirror_v_btn = QPushButton("⇅")
        self.mirror_v_btn.setCheckable(True)
        self.mirror_v_btn.setChecked(bool(self.settings.mirror_v))
        self.mirror_v_btn.setFixedSize(30, 26)
        self.mirror_v_btn.setToolTip("Dikey ayna")
        self.mirror_v_btn.clicked.connect(self.on_orientation_toggle)
        rot_row.addWidget(self.rot_combo, 1)
        rot_row.addWidget(self.mirror_h_btn)
        rot_row.addWidget(self.mirror_v_btn)
        panel.addLayout(rot_row)

        # --- onay kutuları: 2x2 ---
        check_grid = QGridLayout()
        check_grid.setHorizontalSpacing(8)
        check_grid.setVerticalSpacing(2)

        self.agc_check = QCheckBox("AGC")
        self.agc_check.setToolTip("Otomatik ölçek: görüntü aralığını %2–%98 arasına göre ayarlar")
        self.agc_check.setChecked(self.settings.auto_scale)
        self.agc_check.stateChanged.connect(self.on_agc)

        self.smooth_check = QCheckBox("Gürültü azaltma")
        self.smooth_check.setChecked(True)
        self.smooth_check.stateChanged.connect(self._reset_filters)

        self.sharpen_check = QCheckBox("Keskinleştir")
        self.sharpen_check.setChecked(self.settings.sharpen)
        self.sharpen_check.stateChanged.connect(lambda: setattr(self.settings, "sharpen",
                                                                self.sharpen_check.isChecked()))

        self.shading_check = QCheckBox("Gölge düzeltme")
        self.shading_check.setChecked(self.settings.shading)
        self.shading_check.stateChanged.connect(lambda: setattr(self.settings, "shading",
                                                                self.shading_check.isChecked()))

        check_grid.addWidget(self.agc_check, 0, 0)
        check_grid.addWidget(self.smooth_check, 0, 1)
        check_grid.addWidget(self.sharpen_check, 1, 0)
        check_grid.addWidget(self.shading_check, 1, 1)
        panel.addLayout(check_grid)

        contrast_row = QHBoxLayout()
        contrast_row.addWidget(QLabel("Kontrast"))
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(60, 160)
        self.contrast_slider.setValue(int(self.settings.contrast * 100))
        self.contrast_slider.valueChanged.connect(self.on_contrast)
        self.contrast_value = QLabel(f"{self.settings.contrast * 100:.0f}%")
        self.contrast_value.setFixedWidth(40)
        contrast_row.addWidget(self.contrast_slider, 1)
        contrast_row.addWidget(self.contrast_value)
        panel.addLayout(contrast_row)

        detail_row = QHBoxLayout()
        detail_row.addWidget(QLabel("Detay"))
        self.detail_slider = QSlider(Qt.Horizontal)
        self.detail_slider.setRange(0, 150)
        self.detail_slider.setValue(int(self.settings.detail * 100))
        self.detail_slider.setToolTip("Orta ölçekli detayı (DDE) belirginleştirir — telefon uygulamasındaki keskin görünüm")
        self.detail_slider.valueChanged.connect(self.on_detail)
        self.detail_value = QLabel(f"{self.settings.detail * 100:.0f}%")
        self.detail_value.setFixedWidth(40)
        detail_row.addWidget(self.detail_slider, 1)
        detail_row.addWidget(self.detail_value)
        panel.addLayout(detail_row)

        self.min_spin = self._make_temp_spin(self.settings.manual_min, -40, 400,
                                             "Görüntünün alt sıcaklık sınırı — değiştirince AGC kapanır")
        self.max_spin = self._make_temp_spin(self.settings.manual_max, -40, 600,
                                             "Görüntünün üst sıcaklık sınırı — değiştirince AGC kapanır")

        span_grid = QGridLayout()
        span_grid.setHorizontalSpacing(6)
        span_grid.setVerticalSpacing(4)
        span_grid.addWidget(QLabel("Alt"), 0, 0)
        span_grid.addWidget(self._step_button(self.min_spin, -1), 0, 1)
        span_grid.addWidget(self.min_spin, 0, 2)
        span_grid.addWidget(self._step_button(self.min_spin, +1), 0, 3)
        span_grid.addWidget(QLabel("Üst"), 1, 0)
        span_grid.addWidget(self._step_button(self.max_spin, -1), 1, 1)
        span_grid.addWidget(self.max_spin, 1, 2)
        span_grid.addWidget(self._step_button(self.max_spin, +1), 1, 3)
        span_grid.setColumnStretch(2, 1)
        panel.addLayout(span_grid)

        self.span_hint = QLabel("")
        self.span_hint.setStyleSheet("color:#9a9a9a;font-size:10px;")
        self.span_hint.setWordWrap(True)
        panel.addWidget(self.span_hint)
        self.on_agc()

        self.spot_label = QLabel("--.- °C")
        self.spot_label.setFont(QFont("Segoe UI", 21, QFont.Bold))
        self.spot_label.setStyleSheet("color:#ffffff;")
        self.spot_label.setFixedHeight(30)
        panel.addWidget(self.spot_label)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color:#c8c8c8;font-size:11px;")
        self.stats_label.setFixedHeight(32)
        panel.addWidget(self.stats_label)

        # --- düğmeler: 2x2 ---
        btn_grid = QGridLayout()
        btn_grid.setHorizontalSpacing(6)
        btn_grid.setVerticalSpacing(4)

        calib = QPushButton("Kalibrasyon…")
        calib.clicked.connect(self.open_calibration)
        shot = QPushButton("Fotoğraf (S)")
        shot.clicked.connect(self.save_snapshot)
        self.nuc_btn = QPushButton("NUC al")
        self.nuc_btn.setToolTip("Lensi kapatıp sabit desen düzeltmesi al (gölgelenmeyi siler)")
        self.nuc_btn.clicked.connect(self.acquire_nuc)
        self.nuc_clear_btn = QPushButton("NUC sil")
        self.nuc_clear_btn.clicked.connect(self.clear_nuc)

        btn_grid.addWidget(calib, 0, 0)
        btn_grid.addWidget(shot, 0, 1)
        btn_grid.addWidget(self.nuc_btn, 1, 0)
        btn_grid.addWidget(self.nuc_clear_btn, 1, 1)
        panel.addLayout(btn_grid)

        self._update_nuc_label()

        self.status = QLabel("Hazır")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#8f8f8f;font-size:11px;")
        panel.addWidget(self.status)
        panel.addStretch(1)   # içerik üstte toplansın, arada boşluk oluşmasın

        scroll = QScrollArea()
        scroll.setWidget(right)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(338)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        stage_row.addWidget(scroll)

        # --- alt bilgi çubuğu (her zaman görünür) ---
        footer = QWidget()
        footer.setStyleSheet("background:#17171c;")
        frow = QHBoxLayout(footer)
        frow.setContentsMargins(12, 5, 12, 5)
        frow.setSpacing(8)

        credit = QLabel(
            f"ThermalScope v{APP_VERSION} · geliştirici: "
            f"<b>{APP_AUTHOR}</b> (<a href='{GITHUB_URL}' style='color:#6ea8ff'>@efek0349</a>)"
        )
        credit.setTextFormat(Qt.RichText)
        credit.setOpenExternalLinks(True)
        credit.setStyleSheet("color:#8f8f8f;font-size:11px;background:transparent;")
        frow.addWidget(credit)
        frow.addStretch(1)

        about_btn = QPushButton("Hakkında")
        about_btn.setFixedHeight(24)
        about_btn.setStyleSheet(
            "QPushButton{background:#262630;color:#d8d8e0;border:1px solid #3c3c48;"
            "border-radius:4px;padding:2px 12px;font-size:11px;}"
            "QPushButton:hover{background:#32323e;border-color:#6ea8ff;}"
        )
        about_btn.clicked.connect(lambda: AboutDialog(self).exec())
        frow.addWidget(about_btn)
        root.addWidget(footer)

        self.setCentralWidget(central)

    # -- capture --------------------------------------------------------
    def refresh_devices(self) -> None:
        self.device_combo.clear()
        if self.ffmpeg is None:
            self.status.setText("ffmpeg bulunamadı.")
            return
        devices = list_devices(self.ffmpeg)
        for d in devices:
            self.device_combo.addItem(d)
        if devices:
            idx = devices.index(self.settings.device) if self.settings.device in devices else 0
            self.device_combo.setCurrentIndex(idx)
            self.status.setText(f"{len(devices)} kamera bulundu.")
        else:
            self.status.setText("Kamera bulunamadı. Takıp ⟳ ile yenileyin.")

    def toggle_capture(self) -> None:
        if self.capture and self.capture.is_alive():
            self.stop_capture()
        else:
            self.start_capture()

    def start_capture(self) -> None:
        if self.ffmpeg is None:
            return
        device = self.device_combo.currentText()
        if not device:
            self.status.setText("Önce bir kamera seçin.")
            return
        self.settings.device = device
        self.capture = Capture(self.ffmpeg, device, self.on_capture_error)
        self.capture.start()
        self.start_btn.setText("Durdur")
        self.agc.reset()
        self.status.setText("Başlatılıyor…")

    def stop_capture(self) -> None:
        if self.capture:
            self.capture.stop()
            self.capture = None
        self.start_btn.setText("Başlat")
        self.status.setText("Durduruldu.")
        self.view.clear()

    def on_capture_error(self, message: str) -> None:
        self.status.setText(message)
        QTimer.singleShot(0, lambda: self.start_btn.setText("Başlat"))

    # -- rendering ------------------------------------------------------
    def _reset_filters(self) -> None:
        self._ema = None

    def on_tick(self) -> None:
        if not self.capture:
            return
        raw = self.capture.snapshot()
        if raw is None:
            return

        self.last_raw = raw
        scale, offset = self.settings.scale, self.settings.offset

        # 1) flat field (NUC): removes the fixed pattern / shading of the lens+sensor
        work = raw.astype(np.float32)
        if self.nuc is not None and self.settings.nuc_enabled:
            work = work - self.nuc

        # 1b) hot/dead pixel repair
        work = despeckle(work, 150.0)

        # 2) motion-adaptive temporal filter (no smearing, no ghosting)
        if self.smooth_check.isChecked():
            self._ema = adaptive_temporal(self._ema, work, sigma=4.0)
            work = self._ema
        else:
            self._ema = None

        # 3) light spatial smoothing, then unsharp mask to keep edges crisp
        if self.smooth_check.isChecked():
            work = blur3(work)
        if self.sharpen_check.isChecked():
            work = unsharp(work, 0.65)
        work = enhance_detail(work, self.settings.detail)

        disp = work * scale + offset

        # 4) yön: döndürme / ayna (kamera yatay tutulduğunda görüntüyü düzeltir)
        disp = orient(disp, self.settings.rotation, self.settings.mirror_h, self.settings.mirror_v)
        self.last_temps = disp
        self.last_raw = orient(raw, self.settings.rotation, self.settings.mirror_h, self.settings.mirror_v)

        if self.agc_check.isChecked():
            self.agc.update(disp)
            lo, hi = self.agc.lo, self.agc.hi
        else:
            lo = self.min_spin.value()
            hi = self.max_spin.value()

        idx = celsius_to_index(disp, lo, hi)
        idx = apply_contrast(idx, self.settings.contrast)
        if self.shading_check.isChecked():
            idx = fix_shading(idx)
        rgb = self.palette.lut[idx]

        height, width = disp.shape
        spot_text = ""
        if self.spot is not None:
            x = int(np.clip(self.spot[0], 0, width - 1))
            y = int(np.clip(self.spot[1], 0, height - 1))
            spot_text = f"{disp[y, x]:.1f} °C"

        # "16-bit" = kamera verisi (65536 seviye); palet ise renk derinliği (24-bit).
        mode = "16-bit veri · 65536 seviye"
        if self.nuc is not None and self.settings.nuc_enabled:
            mode += " · NUC"
        if self.settings.rotation:
            mode += f" · {self.settings.rotation}°"
        self.view.set_frame(rgb, spot_text, mode)
        self.view.set_scale(self.palette.lut, lo, hi)
        self.update_stats(disp, spot_text)

    def update_stats(self, temps: np.ndarray, spot_text: str) -> None:
        self.spot_label.setText(spot_text or "--.- °C")

        height, width = temps.shape
        flat_idx = int(np.argmax(temps))
        y, x = divmod(flat_idx, width)
        flat_min = int(np.argmin(temps))
        ym, xm = divmod(flat_min, width)
        center = temps[height // 2, width // 2]

        self.stats_label.setText(
            f"Maks {temps.max():.1f} °C ({x},{y})   Min {temps.min():.1f} °C ({xm},{ym})\n"
            f"Merkez {center:.1f} °C   Ortalama {temps.mean():.1f} °C"
        )

        fps = getattr(self.capture, "fps", 0.0) if self.capture else 0.0
        self.status.setText(
            f"{width}x{height} · {fps:.0f} fps · veri 16-bit, palet 24-bit\n"
            f"T(°C) = {self.settings.scale:.8f} × raw + {self.settings.offset:.4f}"
        )

    # -- events ---------------------------------------------------------
    def on_spot(self, x: float, y: float) -> None:
        self.spot = (x, y)

    def on_rotation(self, index: int) -> None:
        self.settings.rotation = int(index) * 90
        self.settings.save()
        self.agc.reset()
        self._ema = None

    def on_orientation_toggle(self) -> None:
        self.settings.mirror_h = self.mirror_h_btn.isChecked()
        self.settings.mirror_v = self.mirror_v_btn.isChecked()
        self.settings.save()
        self.agc.reset()
        self._ema = None

    def cycle_rotation(self) -> None:
        index = (self.rot_combo.currentIndex() + 1) % 4
        self.rot_combo.setCurrentIndex(index)

    def on_palette(self, name: str) -> None:
        pal = next((p for p in self.palettes if p.name == name), None)
        if pal:
            self.palette = pal
            self.view.set_scale(pal.lut, *self.view._span)
            self.settings.palette = name

    def on_agc(self) -> None:
        auto = self.agc_check.isChecked()
        self.settings.auto_scale = auto

        if auto:
            self.span_hint.setText("AGC açık — otomatik ölçek. Elle aralık için Alt/Üst'ü değiştirin.")
        else:
            # elle moda geçerken mevcut AGC penceresini devral ki görüntü sıçramasın
            self.min_spin.blockSignals(True)
            self.max_spin.blockSignals(True)
            self.min_spin.setValue(round(self.agc.lo, 1))
            self.max_spin.setValue(round(self.agc.hi, 1))
            self.min_spin.blockSignals(False)
            self.max_spin.blockSignals(False)
            self.settings.manual_min = self.min_spin.value()
            self.settings.manual_max = self.max_spin.value()
            self.span_hint.setText("Elle ölçek — AGC'yi tekrar açmak için yukarıdaki kutuyu işaretleyin.")

        self.agc.reset()

    def on_span(self) -> None:
        # kullanıcı aralığı elle değiştirdi -> otomatik ölçekten çık
        if self.agc_check.isChecked():
            self.agc_check.blockSignals(True)
            self.agc_check.setChecked(False)
            self.agc_check.blockSignals(False)
            self.settings.auto_scale = False
            self.agc.reset()
            self.span_hint.setText("Elle ölçek — AGC'yi tekrar açmak için yukarıdaki kutuyu işaretleyin.")

        self.settings.manual_min = self.min_spin.value()
        self.settings.manual_max = self.max_spin.value()

    def on_contrast(self, value: int) -> None:
        self.settings.contrast = value / 100.0
        self.contrast_value.setText(f"{value}%")

    def on_detail(self, value: int) -> None:
        self.settings.detail = value / 100.0
        self.detail_value.setText(f"{value}%")

    # -- NUC (flat field) ------------------------------------------------
    def _nuc_file(self) -> Path:
        return SETTINGS_DIR / "nuc.npy"

    def _load_nuc(self) -> np.ndarray | None:
        try:
            arr = np.load(self._nuc_file())
            if arr.shape == (SENSOR_H, SENSOR_W):
                return arr.astype(np.float32)
        except Exception:
            pass
        return None

    def _update_nuc_label(self) -> None:
        """NUC durumunu düğme ipuçlarına yansıtır (panelde ayrı satır tutmuyoruz)."""
        if self.nuc is None:
            self.nuc_btn.setToolTip("Lensi kapatıp sabit desen düzeltmesi al (gölgelenmeyi siler)")
            self.nuc_clear_btn.setEnabled(False)
        else:
            self.nuc_btn.setToolTip("NUC etkin — sabit desen/gölgelenme düzeltiliyor. Yeniden almak için tıklayın.")
            self.nuc_clear_btn.setEnabled(True)

    def acquire_nuc(self) -> None:
        if not self.capture or not self.capture.is_alive():
            QMessageBox.information(self, "NUC", "Önce kamerayı başlatın.")
            return

        answer = QMessageBox.question(
            self, "NUC (flat field)",
            "Kameranın lensini tamamen kapatın (eliyle ya da kapağıyla),\n"
            "yüzeyin her yeri aynı sıcaklıkta olsun.\n\n"
            "Hazır olduğunuzda Tamam'a basın; 2 saniyelik referans alınacak.",
            QMessageBox.Ok | QMessageBox.Cancel)
        if answer != QMessageBox.Ok:
            return

        self.nuc_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            frames = []
            deadline = time.time() + 2.0
            while time.time() < deadline:
                frame = self.capture.snapshot()
                if frame is not None:
                    frames.append(frame.astype(np.float32))
                time.sleep(0.04)

            if len(frames) < 5:
                QMessageBox.warning(self, "NUC", "Yeterli kare alınamadı.")
                return

            reference = np.mean(np.stack(frames), axis=0)
            offset_map = reference - float(np.median(reference))
            self.nuc = offset_map.astype(np.float32)
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            np.save(self._nuc_file(), self.nuc)
            self._ema = None
            self.agc.reset()
            self._update_nuc_label()
            self.status.setText(f"NUC alındı ({len(frames)} kare).")

            spread = float(np.std(offset_map))
            if spread > 800.0:
                QMessageBox.warning(
                    self, "NUC",
                    f"Referans çok düzensiz (std {spread:.0f} sayım).\n"
                    "Lens tam kapanmamış olabilir; NUC kaydedildi ama görüntü bozulabilir.\n"
                    "Gerekirse 'NUC sil' ile kaldırıp tekrar deneyin.")
        finally:
            QApplication.restoreOverrideCursor()
            self.nuc_btn.setEnabled(True)

    def clear_nuc(self) -> None:
        self.nuc = None
        try:
            self._nuc_file().unlink(missing_ok=True)
        except Exception:
            pass
        self._ema = None
        self.agc.reset()
        self._update_nuc_label()
        self.status.setText("NUC silindi.")

    def open_calibration(self) -> None:
        def raw_getter():
            if self.last_raw is None:
                return None
            height, width = self.last_raw.shape
            if self.spot is not None:
                x = int(np.clip(self.spot[0], 0, width - 1))
                y = int(np.clip(self.spot[1], 0, height - 1))
                return int(self.last_raw[y, x])
            return int(self.last_raw[height // 2, width // 2])

        dlg = CalibrationDialog(self, self.settings.scale, self.settings.offset, raw_getter)
        if dlg.exec() == QDialog.Accepted and dlg.result_scale is not None:
            self.settings.scale = dlg.result_scale
            self.settings.offset = dlg.result_offset
            self.settings.save()
            self.agc.reset()

    def save_snapshot(self) -> None:
        if self.last_temps is None:
            return
        lo, hi = (self.agc.lo, self.agc.hi) if self.agc_check.isChecked() else (self.min_spin.value(), self.max_spin.value())
        idx = celsius_to_index(self.last_temps, lo, hi)
        idx = apply_contrast(idx, self.settings.contrast)
        if self.shading_check.isChecked():
            idx = fix_shading(idx)
        rgb = np.repeat(np.repeat(self.palette.lut[idx], ZOOM, axis=0), ZOOM, axis=1)

        out_dir = Path.home() / "Pictures" / "ThermalScope"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"thermal_{datetime.now():%Y%m%d_%H%M%S}.png"

        h, w, _ = rgb.shape
        image = QImage(np.ascontiguousarray(rgb).data, w, h, 3 * w, QImage.Format_RGB888).copy()
        image.save(str(path))
        self.status.setText(f"Kaydedildi:\n{path}")

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_S:
            self.save_snapshot()
        elif event.key() == Qt.Key_R:
            self.cycle_rotation()
        elif event.key() == Qt.Key_H:
            self.mirror_h_btn.toggle()
            self.on_orientation_toggle()
        elif event.key() == Qt.Key_V:
            self.mirror_v_btn.toggle()
            self.on_orientation_toggle()
        elif event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.stop_capture()
        self.settings.save()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    materialize_icon_file()          # kısayol ikonu için %APPDATA% altına kopyala
    win = MainWindow()
    win.show()

    if "--smoke" in sys.argv:
        def grab_and_quit() -> None:
            try:
                win.grab().save("smoke.png")
                Path("smoke_state.txt").write_text(win.status.text(), encoding="utf-8")
                dlg = AboutDialog(win)
                dlg.show()
                app.processEvents()
                dlg.grab().save("smoke_about.png")
                dlg.close()
            except Exception as exc:  # pragma: no cover
                Path("smoke_state.txt").write_text(f"error: {exc}", encoding="utf-8")
            app.quit()

        QTimer.singleShot(5000, grab_and_quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())