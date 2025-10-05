/*
  ESP32 C3 MS01 BTHome Multi Sensor
  (c) 2025 Rysiek Labus - https://sq9mdd.qrz.pl
*/
#include <WiFi.h>                   // biblioteka do obsługi Wi-Fi w ESP32
#include "esp_wifi.h"               // biblioteka do obsługi Wi-Fi w ESP32
#include "esp_bt.h"                 // biblioteka do obsługi Bluetooth w ESP32
#include "NimBLEDevice.h"           // biblioteka NimBLE-Arduino  
#include <BtHomeV2Device.h>         // biblioteka BtHomeV2Device
#include "esp_sleep.h"              // biblioteka do obsługi trybów uśpienia ESP32
#include <Wire.h>                   // biblioteka do obsługi I2C
#include <Adafruit_BME280.h>        // biblioteka do obsługi czujnika BME280


//#define LED_PIN 8                 // ESP32C3-DevKitM-1: GPIO8 (LED wbudowana)
#define VBAT_ADC_PIN 0              // GPIO0 (ADC1_0)
#define VBAT_GATE_PIN  1            // GPIO1 (wirtualna masa)
#define R1 220000.0f                // rezystor R1 dzielnika do VBAT
#define R2 100000.0f                // rezystor R2 dzielnika do "masy" (GPIO1)
#define GPIO_DEEP_SLEEP_DURATION 5  // sleep x seconds and then wake up
#define TX_DBM 9                    // transmit power in dBm (ESP32-C3: -12, -9, -6, -3, 0, 3, 6, 9 dBm)
#define bme_pwr 5                   // GPIO5 - zasilanie BME280 
#define above_sea_lvl 123           // wysokość nad poziomem morza w metrach (dla korekty ciśnienia bezwzględnego)
#define BH1750_ADDR 0x23            // 0x23 albo 0x5C (gdy ADDR=HIGH)

// Procedura kalibracji pomiaru napięcia VBAT
// wymaga zasilacza laboratoryjnego i miernika cyfrowego:
// ustaw CAL_K = 1.0 i CAL_BmV = 0.0
// podlacz urzadzenie do zasilacza laboratoryjnego i ustaw napiecie np. 4.20V
// zanotuj przesyłane napiecie (np. v1 = 4.05V)
// zmień napiecie na 3.30V
// zanotuj przesyłane napiecie (np. v2 = 3.15V)
// uruchom program python tools/calibration-voltage-divider.py z podanymi wartościami
// program wyliczy i poda wartości CAL_K i CAL_BmV
// wprowadź te wartości do poniższych stałych i wgraj program do ESP32
// sprawdź czy teraz przesyłane wartości są prawidłowe
// jeśli nie, powtórz procedurę
static constexpr float CAL_K   = 1.0f;      // współczynnik kalibracji default 01.00f
static constexpr float CAL_BmV = 0.0f;       // offset kalibracji w mV 0.0f

RTC_DATA_ATTR static uint32_t bootcount;     // persists bootcount across deep sleep cycles using RTC memory
float sensor_temperature = 0.1f;
float sensor_humidity = 0.0f;
float sensor_dewpoint = 0.0f;
float sensor_baro = 0.0f;
float sensor_lux = -1.0f;

Adafruit_BME280 bme; 

static bool bh1750_begin(uint8_t addr = BH1750_ADDR) {
  Wire.beginTransmission(addr);
  Wire.write(0x01); // Power ON
  if (Wire.endTransmission() != 0) return false;
  delay(10);

  Wire.beginTransmission(addr);
  Wire.write(0x07); // Reset
  if (Wire.endTransmission() != 0) return false;
  delay(10);

  return true;
}

static float bh1750_read_lux(uint8_t addr=BH1750_ADDR){
  // Continuous H-Resolution (1 lx, ~120–180 ms)
  Wire.beginTransmission(addr); Wire.write(0x10); Wire.endTransmission();
  delay(180);
  if (Wire.requestFrom((int)addr, 2) != 2) return -1.0f;
  uint16_t raw = (Wire.read() << 8) | Wire.read();
  return raw / 1.2f; // przelicznik z datasheetu
}

void read_bme(){
  delay(10);
  // test for BME280 sensor
  if (!bme.begin(0x76)) {
    sensor_temperature = -273.15;  // error value zero absolutne
    return;
  }
  delay(10);
  float hPa_offset = float(above_sea_lvl) * 0.10933;
  sensor_temperature = bme.readTemperature();
  //sensor_temperature = bme.readTemperature();

  sensor_humidity = bme.readHumidity();
  //sensor_dewpoint = dewPointFast(sensor_temperature,sensor_humidity);
  sensor_baro = bme.readPressure() / 100.0F + hPa_offset; 
  digitalWrite(bme_pwr,LOW);
}

void init_vbat_adc() { // Jednorazowa inicjalizacja (np. w setup())
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db); // ~0..3.3 V
}

static uint16_t read_vbat_mV() {
  init_vbat_adc();                      // inicjalizacja ADC do pomiaru VBAT 
  pinMode(VBAT_GATE_PIN, OUTPUT);
  digitalWrite(VBAT_GATE_PIN, LOW);     // włącz dzielnik
  (void)analogRead(VBAT_ADC_PIN);       // dummy read
  delay(12);                            // czas na RC + S/H

#if ESP_ARDUINO_VERSION_MAJOR >= 3      // Arduino-ESP32 v3.0.0+
  const int N = 32;
  uint32_t acc = 0;
  for (int i=0;i<N;++i) acc += analogReadMilliVolts(VBAT_ADC_PIN);
  uint16_t u_adc_mV = acc / N;
#else                                                             // Arduino-ESP32 < v3.0.0
  const int N = 64;                                               // liczba próbek do uśrednienia   
  uint32_t acc = 0;                                               // akumulator sumy próbek       
  for (int i=0;i<N;++i) acc += analogRead(VBAT_ADC_PIN);          // odczyt ADC i sumowanie 
  uint16_t raw = acc / N;                                         // średnia z N próbek
  uint16_t u_adc_mV = (uint16_t)lroundf((raw/4095.0f)*3300.0f);   // przelicz na mV
#endif

  pinMode(VBAT_GATE_PIN, INPUT);                  // odłącz dzielnik (Hi-Z)
  float vbat_mV = u_adc_mV * ((R1 + R2) / R2);    // skala dzielnika
  if (vbat_mV < 0) vbat_mV = 0;                   // zabezpieczenie
  if (vbat_mV > 65535) vbat_mV = 65535;           // zabezpieczenie
  return (uint16_t)lroundf(vbat_mV);              // zwróć surowe mV
}

uint16_t read_vbat_mV_calibrated() {              // skalibrowany pomiar VBAT w mV
  uint16_t mv = read_vbat_mV();                   // surowe mV
  int v = (int)lroundf(CAL_K * mv + CAL_BmV);     // skalibrowane mV
  if (v < 0) v = 0; if (v > 65535) v = 65535;     // ogranicz do zakresu uint16_t
  return (uint16_t)v;                             // zwróć skalibrowane mV      
}

/*
  estimate_battery_percent:
  Estimates the state of charge (SoC) of a single-cell Li-Ion/Li-Po battery based on its open-circuit voltage (OCV).
  Uses a lookup table (lut) mapping voltage values [V] to percentage [%] for typical Li-Ion/Li-Po cells.
  For voltages between table entries, linear interpolation is performed to provide a smooth percentage estimate.
  Assumes the voltage is measured without significant load (OCV).
*/
uint8_t estimate_battery_percent(float vbat) {          // oszacowanie poziomu naładowania baterii Li-Ion/Li-Po na podstawie napięcia
  // OCV tabela przybliżona (bez obciążenia); 
  // dopasuj pod swoją celę
  struct P { float v; uint8_t p; };                     // struktura wpisu w tabeli
  static const P lut[] = {                              // napięcie [V] i odpowiadający poziom naładowania [%]
    {4.20,100},{4.15,95},{4.10,90},{4.05,85},{4.00,80}, // dane dla ogniwa Li-Ion/Li-Po
    {3.95,74},{3.90,68},{3.85,62},{3.80,55},{3.75,48},
    {3.70,42},{3.65,36},{3.60,30},{3.55,24},{3.50,19},
    {3.45,14},{3.40,10},{3.35,7},{3.30,5},{3.25,3},
    {3.20,2},{3.10,1},{3.00,0}
  };

  if (vbat >= lut[0].v)   return lut[0].p;                   // powyżej 4.2V to 100%  
  if (vbat <= lut[sizeof(lut)/sizeof(lut[0])-1].v){          // poniżej 3.0V to 0%
    return lut[sizeof(lut)/sizeof(lut[0])-1].p;              // zabezpieczenie
  } 

  for (size_t i = 1; i < sizeof(lut)/sizeof(lut[0]); ++i) {  // szukaj w tabeli
    if (vbat > lut[i].v) {                                   // znaleziono przedział
      float x = (vbat - lut[i].v) / (lut[i-1].v - lut[i].v); // interpolacja liniowa
      float p = lut[i].p + x * (lut[i-1].p - lut[i].p);      // oblicz poziom naładowania
      if (p < 0) p = 0; if (p > 100) p = 100;                // zabezpieczenie
      return (uint8_t)(p + 0.5f);                            // zwróć poziom naładowania      
    }
  }
  return 0;
}

void sendBeacon(uint8_t advertisementData[], size_t size, uint8_t repeats){     // funkcja wysyłająca reklamy BLE
  if (!repeats) return;                                                         // nic nie rób jeśli powtórzeń 0
  NimBLEDevice::init("");                                                       // inicjalizacja stosu NimBLE
  NimBLEDevice::setPower((int8_t)TX_DBM);                                       // ustaw moc nadawania
  NimBLEAdvertising *pAdvertising = NimBLEDevice::getAdvertising();             // uzyskaj wskaźnik do obiektu reklamowego
  NimBLEAdvertisementData pAdvData = BLEAdvertisementData();                    // obiekt danych reklamowych
  std::vector<uint8_t> data(advertisementData, advertisementData + size);       // skopiuj dane do wektora
  pAdvData.addData(data);                                                       // dodaj dane reklamowe
  pAdvertising->setAdvertisementData(pAdvData);                                 // ustaw dane reklamowe
  pAdvertising->setConnectableMode(0);                                          // reklama nie łącząca
  for (uint8_t i = 0; i < repeats; i++) {                                       // pętla wysyłająca reklamy
    pAdvertising->start();                                                      // rozpocznij reklamę
    delay(10);                                                                  // krótka chwila na rozgłoszenie
    pAdvertising->stop();                                                       // zatrzymaj reklamę
  }
  NimBLEDevice::deinit();                                                       // deinit NimBLE
}

void setup() {
  /*
    Prawidłowa kolejność zapewnia zmniejszenie poboru energii.
  */
  //setCpuFrequencyMhz(80);
  WiFi.persistent(false);                                                   // żadnych auto-zapisów
  WiFi.mode(WIFI_OFF);                                                      // wyłącz Wi-Fi
  esp_wifi_stop();                                                          // zatrzymaj sterownik Wi-Fi
  esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);                    // nie używamy klasycznego BT
                                                                            // initialize I2C only once
  // ----- odczyt danych z BME280 -----
  bootcount++;                                                              // increment bootcount
  pinMode(bme_pwr, OUTPUT);
  digitalWrite(bme_pwr, HIGH);  
  delay(10);                                                                 // czas na ustabilizowanie zasilania  
  Wire.begin();     
  if (bootcount % 2 == 0){
    read_bme();   // odczyt BME280
  } else {
    sensor_lux = bh1750_read_lux();
  }                                

  Wire.end();
  digitalWrite(bme_pwr, LOW); 
// ----- odczyt VBAT -----
  uint16_t vbat_mV = read_vbat_mV_calibrated();                               // odczyt VBAT w mV
  //digitalWrite(LED_PIN, HIGH);                                              // LED off
// ----- przygotowanie i wysłanie reklam BTHome -----
  uint8_t advertisementData[MAX_ADVERTISEMENT_SIZE];                          // bufor na dane reklamowe
  uint8_t size = 0;                                                           // rozmiar danych reklamowych
  BtHomeV2Device device("MS01", "MS01", false);                               // utwórz obiekt urządzenia BTHome
  if (bootcount % 2 == 0){
  device.addTemperature_neg327_to_327_Resolution_0_01(sensor_temperature);    // device.addTemperature_neg44_to_44_Resolution_0_35(dsTempC);  // alternatywnie mniejszy zakres i gorsza rozdzielczość
  device.addHumidityPercent_Resolution_0_01(sensor_humidity);                 // dodaj pomiar wilgotności RH
  device.addPressureHpa(sensor_baro);                                         // dodaj pomiar ciśnienia barometrycznego
  } else {
   device.addIlluminanceLux(sensor_lux); 
  }  
  device.addVoltage_0_to_65_resolution_0_001(vbat_mV / 1000.0f);              // dodaj pomiar napięcia VBAT
  device.addBatteryPercentage(estimate_battery_percent(vbat_mV/1000.0f));     // dodaj szacunkowy poziom naładowania baterii
  device.addCount_0_4294967295(bootcount);                                    // dodaj licznik restartów
  size = device.getAdvertisementData(advertisementData);                      // pobierz dane reklamowe do bufora
  sendBeacon(advertisementData, size, 5);                                     // nadaj reklamy X razy
// ----- przejście w tryb głębokiego uśpienia -----
  esp_sleep_enable_timer_wakeup(1000000LL * GPIO_DEEP_SLEEP_DURATION);        // enable timer wakeup
  esp_deep_sleep_start();                                                     // enter deep sleep
}

void loop() {
}
