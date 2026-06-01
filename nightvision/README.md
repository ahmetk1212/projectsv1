# NightVision Goggles — Raspberry Pi 3A+ Build

## Donanım

| Parça | Açıklama |
|---|---|
| Raspberry Pi 3A+ | Ana bilgisayar |
| NoIR Kamera Module | 60° FOV, infrared gece görüşü |
| 3× 3W IR LED (850nm) | Gece aydınlatması — GPIO PWM ile kontrol |
| GPIO pin: 17, 27, 22 | LED kontrol pinleri (BCM numaralandırma) |

---

## Proje Yapısı

```
nightvision/
├── main.py              # Ana giriş noktası — sistemi başlatır
├── config.py            # Tüm ayarlar tek dosyada
├── requirements.txt     # Python bağımlılıkları
│
├── camera/
│   └── interface.py     # PiCamera2 / picamera / webcam / demo modu
├── led/
│   └── controller.py    # 3W IR LED GPIO PWM kontrolü
├── zoom/
│   └── controller.py    # ROI kırpma tabanlı zoom (1x–8x, animasyonlu)
├── detection/
│   └── yolo.py          # YOLOv4-tiny + fallback hareket algılama
└── hud/
    └── engine.py        # JARVIS tarzı HUD overlay (sci-fi görünüm)
```

---

## Kurulum (Raspberry Pi üzerinde)

```bash
# 1. Bağımlılıkları yükle
sudo apt update && sudo apt install -y libopencv-dev python3-opencv python3-picamera2

# 2. Sanal ortam oluştur
python3 -m venv ~/.venv/nightvision
source ~/.venv/nightvision/bin/activate
pip install opencv-python-headless numpy

# 3. Projeyi kopyala ve çalıştır
git clone <repo> ~/nightvision
cd ~/nightvision
python main.py              # Canlı mod (PiCamera + gerçek LED)
python main.py --demo      # Demo mod (bilgisayarda test)
```

---

## Kontroller

| Tuş | İşlev |
|---|---|
| `i` / `+` | Zoom in |
| `o` / `-` | Zoom out |
| `r` | Zoom sıfırla |
| `l` | LED aç/kapa |
| `f` | LED flaş |
| `d` | Nesne algılama aç/kapa |
| `q` / `ESC` | Çıkış |

---

## LED Pin Bağlantısı

```
3W IR LED × 3 ───┬─── 330Ω ─── GPIO 17 (BCM)
                 ├─── 330Ω ─── GPIO 27 (BCM)
                 └─── 330Ω ─── GPIO 22 (BCM)

Tüm LED'lerin GND'si → RPi GND pin'e
NOT: 3W LED için 330Ω ön direnç ZORUNLU (aksi halde LED yanar)
```

Farklı pin kullanıyorsan `config.py` içinde `LED_PINS` listesini düzenle.

---

## LED Parlaklık Ayarı

`config.py` içinde:
```python
LED_DEFAULT_BRIGHTNESS = 80   # 0–100 arası
```

Yazılımda anlık değiştirmek için — `main.py`'de bir tuş ekle:
```python
elif k == 'b':
    brightness = (brightness + 10) % 100
    led.set_brightness(brightness)
```

---

## YOLOv4-tiny Kurulumu (Gerçek Nesne Tanıma)

Varsayılan olarak yazılım `motion detection` fallback modunda çalışır.
Gerçek nesne tanıma için:

```bash
mkdir -p ~/nightvision/models
cd ~/nightvision/models

# Ağırlıklar (~22MB)
wget https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4-tiny.weights

# Konfigürasyon
wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg

# Sınıf isimleri (opsiyonel — detections.py'a ekle)
wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names
```

`config.py` içinde yolu doğrula:
```python
DETECTION_WEIGHTS = "/home/pi/nightvision/models/yolov4-tiny.weights"
DETECTION_CFG = "/home/pi/nightvision/models/yolov4-tiny.cfg"
```

---

## HUD Özelleştirme

Tüm HUD renk ve davranışları `config.py`'de:

```python
HUD_COLOR_PRIMARY   = (0, 255, 255)   # Cyan — ana elemanlar
HUD_COLOR_SECONDARY = (0, 200, 255)   # Amber — alt bilgi
HUD_COLOR_DETECTION = (0, 255, 0)     # Yeşil — algılanan nesne
HUD_COLOR_ALERT     = (0, 80, 255)    # Kırmızı-turuncu — uyarılar

HUD_SHOW_COMPASS    = True   # Pusula animasyonu
HUD_SHOW_SCAN_LINE   = True   # Yatay tarama çizgisi
HUD_PULSE_RATE       = 1.5   # Nabız hızı (Hz)
```

Yeni HUD elementi eklemek için — `hud/engine.py` içinde `_draw_*` fonksiyonu oluştur ve `render()` içinde çağır.

---

## Zoom Özelliği

ROI kırpma + yeniden ölçeklendirme ile çalışır (dijital zoom, optik değil).

```python
ZOOM_MIN     = 1.0   # Hiç zoom yok
ZOOM_MAX     = 8.0   # Maksimum zoom
ZOOM_STEP    = 0.5   # Her tuş basışında zoom miktarı
ZOOM_SMOOTH  = True  # Animasyonlu geçiş
```

Zoom bölgesini kaydırmak için (örn. mouse ile) — `zoom/controller.py` içinde `pan(dx, dy)` fonksiyonu mevcut. Bir GUI tuşa bağla:

```python
elif k == 'w': zoom.pan(0, -0.05)  # yukarı
elif k == 's': zoom.pan(0, +0.05)  # aşağı
```

---

## Performans İpucu

Pi 3A+'da `yolov4-tiny` ile ~8-12 FPS beklenir.
Düşürmek için `config.py`'de:

```python
CAMERA_RESOLUTION = (640, 480)   # Yarı çözünürlük
DETECTION_CONFIDENCE = 0.6        # Daha yüksek eşik — daha az algılama
```

---

## Gerçek Donanım Test

Pi üzerinde test için:
```bash
# RPi GPIO ve kamera ile tam mod
python main.py

# LED pin değiştirmek için
python main.py --no-led       # LED disabled (pin değişikliği)
```