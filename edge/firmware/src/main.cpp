#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ── Config (injected via build_flags) ────────────────────────────────────────
#ifndef WIFI_SSID
  #define WIFI_SSID "your_wifi_ssid"
#endif
#ifndef WIFI_PASS
  #define WIFI_PASS "your_wifi_password"
#endif
#ifndef MQTT_HOST
  #define MQTT_HOST "192.168.0.1"
#endif
#ifndef MQTT_PORT
  #define MQTT_PORT 1883
#endif
#ifndef LOT_ID
  #define LOT_ID "00000000-0000-0000-0000-000000000000"
#endif
#ifndef SLOT_LABEL
  #define SLOT_LABEL "A-01"
#endif
#ifndef TRIGGER_PIN
  #define TRIGGER_PIN 5
#endif
#ifndef ECHO_PIN
  #define ECHO_PIN 18
#endif

// ── MQTT topic ────────────────────────────────────────────────────────────────
// parking/<lot_id>/slot/<slot_label>/state
static const char* TOPIC = "parking/" LOT_ID "/slot/" SLOT_LABEL "/state";

// ── Globals ───────────────────────────────────────────────────────────────────
WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);

// ── Helpers ───────────────────────────────────────────────────────────────────
float measure_distance_cm() {
    digitalWrite(TRIGGER_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIGGER_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIGGER_PIN, LOW);

    long duration = pulseIn(ECHO_PIN, HIGH, 30000);  // 30 ms timeout ~ 5 m
    if (duration == 0) return -1.0f;
    return duration * 0.034f / 2.0f;
}

void connect_wifi() {
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }
}

void connect_mqtt() {
    mqtt.setServer(MQTT_HOST, MQTT_PORT);
    while (!mqtt.connected()) {
        if (!mqtt.connect("esp32-" SLOT_LABEL)) {
            delay(2000);
        }
    }
}

// ── Arduino lifecycle ─────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    pinMode(TRIGGER_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    connect_wifi();
    connect_mqtt();
}

void loop() {
    if (!mqtt.connected()) connect_mqtt();
    mqtt.loop();

    float distance_cm = measure_distance_cm();
    if (distance_cm < 0) {
        delay(1000);
        return;
    }

    // Build JSON payload and publish at 1 Hz
    StaticJsonDocument<64> doc;
    doc["distance_cm"] = distance_cm;
    doc["ts"]          = millis();

    char buf[64];
    serializeJson(doc, buf);
    mqtt.publish(TOPIC, buf);

    delay(1000);
}
