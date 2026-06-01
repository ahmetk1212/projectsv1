# NightVision Goggles — Raspberry Pi 3A+ Build

## Donanım

| Parça | Açıklama |
|---|---|
| Raspberry Pi 3A+ | Ana bilgisayar |
| NoIR Kamera Module | 60° FOV, infrared gece görüşü |
| 3× 3W IR LED (850nm) | Gece aydınlatması — GPIO PWM ile kontrol |
| GPIO pin: 17, 27, 22 | LED kontrol pinleri (BCM) |

---

## Proje Yapısı

```
nightvision/
├── main.py              # Ana giriş noktası (laptop/Pi/headless)
├── config.py            # Tüm ayarlar tek dosyada
├── requirements.txt     # Python bağımlılıkları
├── README.md
│
├── camera/interface.py     # PiCamera2 / laptop webcam / demo modu
├── led/controller.py       # 3× 3W IR LED GPIO PWM kontrolü
├── zoom/controller.py      # ROI kırpma tabanlı zoom (1x–8x, animasyonlu)
├── detection/yolo.py       # YOLOv4-tiny + fallback motion detection
├── hud/engine.py           # JARVIS tarzı HUD overlay
│
├── tools/
│   ├── test_runner.py      # Tüm modüllerin laptop'ta hızlı testi
│   ├── benchmark.py        # FPS benchmark — farklı çözünürlüklerde
│   ├── webcam_preview.py   # Sadece webcam + HUD önizleme
│   ├── zoom_test.py        # Zoom seviyelerini görsel test et
│   └── led_simulator.py    # LED kontrol mantığını simüle et
```

---

## Hızlı Başlangıç — Laptop (webcam ile)

```bash
# 1. Sanal ortam
python3 -m venv venv
source venv/bin/activate
pip install opencv-python-headless numpy

# 2. Test paketini çalıştır (hiçbir donanım gerekmez)
python tools/test_runner.py

# 3. Benchmark (sistemin hızını ölç)
python tools/benchmark.py

# 4. Tam uygulama (laptop webcam + HUD canlı)
python main.py

# VEYA demo modda (webcam bile gerekmez)
python main.py --demo

# VEYA tam Pi modu (LED + kamera)
python main.py --pi
```

### Çalışma modları özet

| Komut | Ne yapar |
|---|---|
| `python main.py` | Laptop webcam + ekranda HUD |
| `python main.py --demo` | Sentetik demo frames + HUD |
| `python main.py --webcam 1` | USB webcam index 1 |
| `python main.py --pi` | Raspberry Pi kamera + LED |
| `python main.py --headless` | Ekran yok, frame'leri diske yaz |
| `python main.py --record out.mp4` | Video kaydet |
| `python main.py --fullscreen` | Tam ekran pencere |
| `python main.py --duration 30` | 30 saniye sonra çık |
| `python tools/webcam_preview.py` | Sadece webcam + HUD (hafif) |
| `python tools/led_simulator.py` | LED mantığını simüle et |

---

## Kontroller

| Tuş | İşlev |
|---|---|
| `i` / `+` | Zoom in |
| `o` / `-` | Zoom out |
| `r` | Zoom sıfırla |
| `l` | IR LED aç/kapa |
| `f` | LED flaş |
| `d` | Nesne tanıma aç/kapa |
| `s` | Ekran görüntüsü kaydet |
| `SPACE` | Duraklat / devam et |
| `h` | Yardım overlay'i |
| `q` / `ESC` | Çıkış |

---

## LED Bağlantısı

```
3W IR LED × 3 ───┬─── 330Ω ─── GPIO 17 (BCM)
                 ├─── 330Ω ─── GPIO 27 (BCM)
                 └─── 330Ω ─── GPIO 22 (BCM)

Tüm LED GND → RPi GND
⚠ 3W LED için 330Ω ön direnç ZORUNLU!
```

Pin değiştirmek için `config.py`:
```python
LED_PINS = [17, 27, 22]
```

---

## YOLOv4-tiny Kurulumu

Varsayılan: motion detection fallback (dosya gerekmez).
Gerçek nesne tanıma için:

```bash
mkdir -p models
cd models
wget https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4-tiny.weights
wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg
```

`config.py`:
```python
DETECTION_WEIGHTS = "models/yolov4-tiny.weights"
DETECTION_CFG = "models/yolov4-tiny.cfg"
```

---

## HUD Özelleştirme

`config.py` içinde tüm renkler ve element açma/kapama:

```python
HUD_COLOR_PRIMARY   = (0, 255, 255)   # Cyan
HUD_COLOR_SECONDARY = (0, 200, 255)   # Amber
HUD_COLOR_DETECTION = (0, 255, 0)     # Yeşil — algılanan nesne
HUD_COLOR_ALERT     = (0, 80, 255)    # Kırmızı

HUD_SHOW_COMPASS    = True
HUD_SHOW_SCAN_LINE  = True
HUD_PULSE_RATE      = 1.5   # Hz
```

Yeni element eklemek için `hud/engine.py` içine `_draw_*` fonksiyonu yazıp `render()` içinde çağır.

---

## Zoom (ROI Crop)

Dijital zoom — kırpma + yeniden boyutlandırma. Pan eklemek için:

```python
# main.py içinde bir tuşa bağla
elif key == ord('w'): self.zoom.pan(0, -0.05)
elif key == ord('a'): self.zoom.pan(-0.05, 0)
elif key == ord('s'): self.zoom.pan(0, +0.05)
elif key == ord('d'): self.zoom.pan(+0.05, 0)
```

---

## Performans (Laptop, OpenCV 4.13, CPU)

| Konfigürasyon | FPS |
|---|---|
| 320×240 + HUD | ~169 |
| 640×480 + HUD | ~42 |
| 640×480 + HUD + Detection (fallback) | ~44 |
| 1280×720 + HUD | ~16 |

### Pi 3A+ referans (tipik)

| Konfigürasyon | FPS |
|---|---|
| 320×240 + HUD | ~20-25 |
| 640×480 + HUD | ~12-15 |
| 640×480 + HUD + YOLOv4-tiny | ~6-10 |
| 1280×720 + HUD | ~5-8 |

Pi'da yavaşsa:
```python
CAMERA_RESOLUTION = (640, 480)        # veya 320x240
DETECTION_CONFIDENCE = 0.6             # daha az algılama
# main.py'de her 3 karede bir algılama yap:
if self._frame_count % 3 == 0: self.detector.detect(...)
```

---

## Gerçek Donanım Test (Pi üzerinde)

```bash
# Kamerayı aktif et
sudo raspi-config    # Interface Options > Camera > Enable

# Pi'ye özel bağımlılıklar
sudo apt install -y python3-picamera2 python3-opencv python3-rpi.gpio

# Çalıştır
python3 main.py --pi
```

---

## Sorun Giderme

**Kamera açılmıyor (Pi'da)**
```bash
libcamera-hello   # kamerayı test et
sudo raspi-config # camera enable
```

**LED çalışmıyor**
```bash
# GPIO pinlerini test et
python3 -c "import RPi.GPIO as G; G.setmode(G.BCM); G.setup(17, G.OUT); G.output(17, True); input('OK?'); G.cleanup()"
```

**Yavaş FPS**
- `--demo` ile test et (donanım sorununu dışlar)
- Çözünürlüğü düşür
- Detection'ı kapat (`--no-detect`)
- Benchmark çalıştır: `python tools/benchmark.py`

**Webcam açılmıyor (laptop'ta)**
```bash
# Diğer indexleri dene
python main.py --webcam 1
```