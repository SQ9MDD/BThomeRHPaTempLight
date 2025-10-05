# ESP32-C3 MS01 BTHome Multi Sensor

Firmware for ultra-low-power **ESP32-C3** sensor node broadcasting environmental data via **BTHome v2** over BLE advertisements.

---

## 🇬🇧 English

### Features
- Alternating measurement cycle:
  - **Even boots:** temperature, humidity, and pressure from **BME280**
  - **Odd boots:** ambient light (lux) from **BH1750**
- Always transmits:
  - Battery voltage and percentage
  - Boot counter
- Designed for deep sleep operation with minimal power draw
- Compatible with Home Assistant (via BTHome integration)

### Hardware
- **ESP32-C3** (e.g. DevKitM-1)
- **BME280** (I²C, 0x76)
- **BH1750 / GY-302** (I²C, 0x23)
- Voltage divider for VBAT monitoring

### Configuration
- Deep sleep interval: `GPIO_DEEP_SLEEP_DURATION` (seconds)
- Transmit power: `TX_DBM`
- Sea level correction: `above_sea_lvl`
- Calibration constants: `CAL_K` and `CAL_BmV`

---

## 🇵🇱 Polski

### Funkcje
- Naprzemienny cykl pomiarowy:
  - **Parzyste uruchomienia:** temperatura, wilgotność i ciśnienie z **BME280**
  - **Nieparzyste uruchomienia:** natężenie oświetlenia (lux) z **BH1750**
- Zawsze wysyłane:
  - Napięcie i poziom baterii
  - Licznik uruchomień
- Tryb **deep sleep** z bardzo niskim poborem prądu
- Kompatybilny z **Home Assistant** (integracja BTHome)

### Sprzęt
- **ESP32-C3** (np. DevKitM-1)
- **BME280** (I²C, adres 0x76)
- **BH1750 / GY-302** (I²C, adres 0x23)
- Dzielnik napięcia do pomiaru VBAT

### Konfiguracja
- Czas uśpienia: `GPIO_DEEP_SLEEP_DURATION` (sekundy)  
- Moc nadawania BLE: `TX_DBM`  
- Wysokość nad poziomem morza: `above_sea_lvl`  
- Współczynniki kalibracji: `CAL_K`, `CAL_BmV`

---

## Author / Autor
(c) 2025 **Rysiek Labus** – [SQ9MDD](https://sq9mdd.qrz.pl)
