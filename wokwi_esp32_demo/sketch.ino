#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Wire.h>

#include "gts_root_r4.h"
#include "radio_config.h"
#include "station_config.h"
#include "virtual_lora.h"

// Wokwi ESP32-S3 pins: three simulated analog inputs, a vibration button,
// local indicators, and I2C for the MPU6050.
static const uint8_t PIN_MOISTURE = 4;
static const uint8_t PIN_TILT_INPUT = 5;
static const uint8_t PIN_BATTERY = 6;
static const uint8_t PIN_VIBRATION = 7;
static const uint8_t PIN_I2C_SDA = 8;
static const uint8_t PIN_I2C_SCL = 9;
static const uint8_t PIN_LED_GREEN = 15;
static const uint8_t PIN_LED_YELLOW = 16;
static const uint8_t PIN_LED_RED = 17;
static const uint8_t PIN_BUZZER = 18;

static const char *WIFI_SSID = "Wokwi-GUEST";
static const char *WIFI_PASSWORD = "";
static const char *TLS_HOST = "himrakshak.onrender.com";
static const char *INGEST_URL = "https://himrakshak.onrender.com/api/v2/radio/transmissions";
static const unsigned long TELEMETRY_INTERVAL_MS = 10000;
static const unsigned long WIFI_RETRY_INTERVAL_MS = 5000;
static const unsigned long RETRY_MAX_MS = 60000;
static const uint8_t MAX_PENDING_PACKETS = 10;

struct PendingPacket {
  bool occupied;
  String packetId;
  String payload;
  unsigned long sequence;
  unsigned long attemptNumber;
  unsigned long nextAttemptAt;
  unsigned long retryDelayMs;
};

struct Reading {
  float moisture;
  float tilt;
  float vibration;
  float battery;
  bool sensorFault;
};

Adafruit_MPU6050 mpu;
bool mpuReady = false;
PendingPacket pending[MAX_PENDING_PACKETS];
unsigned long nextSequence = 1;
unsigned long lastTelemetryAt = 0;
unsigned long lastWifiAttemptAt = 0;
unsigned long lastBuzzerAt = 0;
unsigned long droppedPackets = 0;
unsigned long deliveredPackets = 0;
unsigned long retryPackets = 0;
float filteredTilt = 0.0f;
float previousAcceleration = 0.0f;

String stationUrl() {
  return String(INGEST_URL);
}

void setIndicators(const char *riskLevel) {
  bool normal = strcmp(riskLevel, "NORMAL") == 0;
  bool warning = strcmp(riskLevel, "WARNING") == 0;
  digitalWrite(PIN_LED_GREEN, normal ? HIGH : LOW);
  digitalWrite(PIN_LED_YELLOW, warning ? HIGH : LOW);
  digitalWrite(PIN_LED_RED, (!normal && !warning) ? HIGH : LOW);
  if (!normal && millis() - lastBuzzerAt >= 1000) {
    tone(PIN_BUZZER, 1800, 120);
    lastBuzzerAt = millis();
  }
}

int demoScore(const Reading &reading) {
  float raw = max(0.0f, (reading.moisture - 45.0f) / 55.0f) * 35.0f;
  raw += max(0.0f, (reading.tilt - 2.0f) / 10.0f) * 45.0f;
  raw += max(0.0f, (reading.vibration - 25.0f) / 75.0f) * 20.0f;
  return constrain((int)floor(raw + 0.5f), 0, 100);
}

const char *localRisk(const Reading &reading) {
  int score = demoScore(reading);
  bool criticalTilt = reading.tilt >= 8.0f;
  bool criticalCombination = reading.moisture >= 75.0f && reading.tilt >= 4.0f;
  bool criticalScore = score >= 55;
  if (criticalTilt || criticalCombination || criticalScore) {
    return "CRITICAL";
  }
  if (reading.moisture >= 60.0f || reading.tilt >= 4.0f ||
      reading.vibration >= 65.0f || score >= 25) {
    return "WARNING";
  }
  return "NORMAL";
}

Reading readSensors() {
  Reading reading;
  reading.sensorFault = !mpuReady;
  reading.moisture = (analogRead(PIN_MOISTURE) / 4095.0f) * 100.0f;
  float knobTilt = (analogRead(PIN_TILT_INPUT) / 4095.0f) * 8.0f;
  reading.battery = (analogRead(PIN_BATTERY) / 4095.0f) * 100.0f;
  reading.vibration = digitalRead(PIN_VIBRATION) == LOW ? 85.0f : 12.0f;

  if (mpuReady) {
    sensors_event_t acceleration, gyro, temperature;
    mpu.getEvent(&acceleration, &gyro, &temperature);
    float accelerationMagnitude = sqrt(
        acceleration.acceleration.x * acceleration.acceleration.x +
        acceleration.acceleration.y * acceleration.acceleration.y +
        acceleration.acceleration.z * acceleration.acceleration.z);
    float accelerationTilt = fabs(atan2(
        acceleration.acceleration.x, acceleration.acceleration.z) * 57.2958f);
    filteredTilt = filteredTilt * 0.8f + accelerationTilt * 0.2f;
    float delta = fabs(accelerationMagnitude - previousAcceleration);
    previousAcceleration = accelerationMagnitude;
    reading.vibration = max(reading.vibration, constrain(delta * 12.0f, 0.0f, 100.0f));
  }
  reading.tilt = constrain(knobTilt + filteredTilt * 0.5f, 0.0f, 15.0f);

#if HIMRAKSHAK_USE_SCENARIO_PRESET
  if (strcmp(HIMRAKSHAK_SCENARIO, "heavy_rain") == 0) {
    reading.moisture = max(reading.moisture, 82.0f);
  } else if (strcmp(HIMRAKSHAK_SCENARIO, "slope_shift") == 0) {
    reading.tilt = max(reading.tilt, 5.5f);
  }
#endif
  return reading;
}

String makePayload(const Reading &reading, unsigned long sequence) {
  StaticJsonDocument<768> doc;
  doc["node_id"] = HIMRAKSHAK_STATION_ID;
  doc["sequence"] = sequence;
  doc["timestamp"] = "SIMULATED";
  doc["soil_moisture_pct"] = round(reading.moisture * 10.0f) / 10.0f;
  doc["tilt_deg"] = round(reading.tilt * 10.0f) / 10.0f;
  doc["vibration_level"] = round(reading.vibration * 10.0f) / 10.0f;
  doc["battery_pct"] = round(reading.battery * 10.0f) / 10.0f;
  doc["transport"] = "WOKWI_SOFTWARE_SIMULATION";
  doc["scenario"] = HIMRAKSHAK_SCENARIO;
  String payload;
  serializeJson(doc, payload);
  return payload;
}

int findFreePacket() {
  for (uint8_t i = 0; i < MAX_PENDING_PACKETS; ++i) {
    if (!pending[i].occupied) return i;
  }
  return -1;
}

void enqueueReading(const Reading &reading) {
  int slot = findFreePacket();
  if (slot < 0) {
    droppedPackets++;
    Serial.println("Queue full; local alert preserved and packet dropped");
    return;
  }
  pending[slot].occupied = true;
  pending[slot].sequence = nextSequence++;
  pending[slot].packetId = String(HIMRAKSHAK_STATION_ID) + "-" +
                           String(pending[slot].sequence);
  pending[slot].payload = makePayload(reading, pending[slot].sequence);
  pending[slot].attemptNumber = 0;
  pending[slot].nextAttemptAt = 0;
  pending[slot].retryDelayMs = 1000;
}

void diagnoseTransportFailure(int status) {
  if (status == 0) Serial.println("DNS/TCP/TLS failure or backend unavailable");
  else Serial.printf("HTTP status %d\n", status);
}

bool shouldRetry(int status) {
  return status == 0 || status == 408 || status == 425 || status == 429 ||
         status >= 500;
}

enum SubmitResult {
  SUBMIT_DELIVERED,
  SUBMIT_RETRY,
  SUBMIT_PERMANENT_FAILURE
};

SubmitResult submitPacket(PendingPacket &packet) {
  if (WiFi.status() != WL_CONNECTED) return SUBMIT_RETRY;
  WiFiClientSecure client;
  client.setCACert(HIMRAKSHAK_ROOT_CA);
  HTTPClient http;
  if (!http.begin(client, stationUrl())) {
    diagnoseTransportFailure(0);
    return SUBMIT_RETRY;
  }
  packet.attemptNumber++;
  String attemptId = makeAttemptId(packet.packetId, packet.attemptNumber);
  String envelope = makeTransmissionEnvelope(
      attemptId, packet.packetId, HIMRAKSHAK_STATION_ID, packet.sequence,
      packet.payload, packet.attemptNumber);
  http.addHeader("Content-Type", "application/json");
  if (strlen(HIMRAKSHAK_DEVICE_TOKEN) > 0) {
    http.addHeader("X-HimRakshak-Device-Token", HIMRAKSHAK_DEVICE_TOKEN);
  }
  int status = http.POST(envelope);
  String response = http.getString();
  http.end();
  if (status >= 200 && status < 300) {
    deliveredPackets++;
    Serial.printf("Delivered packet=%s attempt=%s\n",
                  packet.packetId.c_str(), attemptId.c_str());
    return SUBMIT_DELIVERED;
  }
  diagnoseTransportFailure(status);
  if (status == 400 || status == 401 || status == 403 || status == 404 ||
      status == 409) {
    Serial.printf("Permanent or reconciled response; packet removed from retry queue: %s\n",
                  response.c_str());
    return SUBMIT_PERMANENT_FAILURE;
  }
  return shouldRetry(status) ? SUBMIT_RETRY : SUBMIT_PERMANENT_FAILURE;
}

void serviceQueue() {
  unsigned long now = millis();
  for (uint8_t i = 0; i < MAX_PENDING_PACKETS; ++i) {
    if (!pending[i].occupied || now < pending[i].nextAttemptAt) continue;
    SubmitResult result = submitPacket(pending[i]);
    if (result == SUBMIT_DELIVERED || result == SUBMIT_PERMANENT_FAILURE) {
      pending[i].occupied = false;
      continue;
    }
    retryPackets++;
    pending[i].nextAttemptAt = now + pending[i].retryDelayMs;
    pending[i].retryDelayMs = min(RETRY_MAX_MS, pending[i].retryDelayMs * 2);
  }
}

void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  if (millis() - lastWifiAttemptAt < WIFI_RETRY_INTERVAL_MS) return;
  lastWifiAttemptAt = millis();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.println("Wi-Fi connection attempt scheduled");
}

// Kept as a non-blocking compatibility hook. SIMULATED timestamps do not
// require NTP and local alerts must start before network work.
void synchronizeClock() {}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_VIBRATION, INPUT_PULLUP);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  analogReadResolution(12);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  mpuReady = mpu.begin();
  if (!mpuReady) Serial.println("MPU6050 unavailable; using simulated tilt input");
  else {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  }
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  synchronizeClock();
  Serial.printf("HimRakshak %s ready; queue=%u\n",
                HIMRAKSHAK_STATION_ID, MAX_PENDING_PACKETS);
}

void loop() {
  ensureWiFi();
  Reading reading = readSensors();
  const char *risk = localRisk(reading);
  setIndicators(risk);

  unsigned long now = millis();
  if (now - lastTelemetryAt >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryAt = now;
    enqueueReading(reading);
    Serial.printf("Local %s moisture=%.1f tilt=%.1f vibration=%.1f battery=%.1f\n",
                  risk, reading.moisture, reading.tilt, reading.vibration,
                  reading.battery);
  }
  serviceQueue();
  delay(10);
}
