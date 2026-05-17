#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

#define SENSOR_COUNT  5
#define RESET_PIN     0
#define RESET_HOLD_MS 3000

static const char* NVS_NS = "sp-cfg";

// ── Config ────────────────────────────────────────────────────────────────────
struct SensorCfg {
    String  slot_label;
    uint8_t trig_pin;
    uint8_t echo_pin;
};

// Default pin pairs for 5 sensors. Change in the provisioning form per board wiring.
static const uint8_t DEFAULT_TRIG[SENSOR_COUNT] = { 5, 13, 14, 23, 25};
static const uint8_t DEFAULT_ECHO[SENSOR_COUNT] = {18, 19, 21, 22, 26};

struct Config {
    String    wifi_ssid;
    String    wifi_pass;
    String    mqtt_host;
    uint16_t  mqtt_port = 1883;
    String    lot_id;
    SensorCfg sensors[SENSOR_COUNT];
};

Config cfg;
char   CLIENT_ID[32];

WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);
Preferences  prefs;

// ── NVS helpers ───────────────────────────────────────────────────────────────
bool load_config() {
    prefs.begin(NVS_NS, true);
    cfg.wifi_ssid  = prefs.getString("wifi_ssid", "");
    cfg.wifi_pass  = prefs.getString("wifi_pass",  "");
    cfg.mqtt_host  = prefs.getString("mqtt_host",  "");
    cfg.mqtt_port  = prefs.getUShort("mqtt_port",  1883);
    cfg.lot_id     = prefs.getString("lot_id",     "");

    char key[12];
    for (int i = 0; i < SENSOR_COUNT; i++) {
        snprintf(key, sizeof(key), "s%d_label", i);
        cfg.sensors[i].slot_label = prefs.getString(key, "");
        snprintf(key, sizeof(key), "s%d_trig", i);
        cfg.sensors[i].trig_pin = prefs.getUChar(key, DEFAULT_TRIG[i]);
        snprintf(key, sizeof(key), "s%d_echo", i);
        cfg.sensors[i].echo_pin = prefs.getUChar(key, DEFAULT_ECHO[i]);
    }
    prefs.end();

    if (cfg.wifi_ssid.length() == 0 || cfg.mqtt_host.length() == 0
            || cfg.lot_id.length() == 0) return false;
    // At least one sensor must be configured; sensors with empty labels are skipped at runtime.
    bool any = false;
    for (int i = 0; i < SENSOR_COUNT; i++) {
        if (cfg.sensors[i].slot_label.length() > 0) { any = true; break; }
    }
    return any;
}

void save_config(const Config& c) {
    prefs.begin(NVS_NS, false);
    prefs.putString("wifi_ssid", c.wifi_ssid);
    prefs.putString("wifi_pass", c.wifi_pass);
    prefs.putString("mqtt_host", c.mqtt_host);
    prefs.putUShort("mqtt_port", c.mqtt_port);
    prefs.putString("lot_id",    c.lot_id);

    char key[12];
    for (int i = 0; i < SENSOR_COUNT; i++) {
        snprintf(key, sizeof(key), "s%d_label", i);
        prefs.putString(key, c.sensors[i].slot_label);
        snprintf(key, sizeof(key), "s%d_trig", i);
        prefs.putUChar(key, c.sensors[i].trig_pin);
        snprintf(key, sizeof(key), "s%d_echo", i);
        prefs.putUChar(key, c.sensors[i].echo_pin);
    }
    prefs.end();
}

void clear_config() {
    prefs.begin(NVS_NS, false);
    prefs.clear();
    prefs.end();
}

// ── Provisioning HTML ─────────────────────────────────────────────────────────
static const char FORM_HEAD[] PROGMEM = R"(<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Parking — Setup</title>
<style>
  body{font-family:sans-serif;max-width:480px;margin:40px auto;padding:0 16px}
  h2{margin-bottom:4px}
  h3{margin:28px 0 4px;border-top:1px solid #e5e7eb;padding-top:20px;font-size:1em;color:#374151}
  .sub{color:#666;margin-top:0;font-size:.9em}
  label{display:block;margin-top:12px;font-weight:bold;font-size:.85em;color:#374151}
  input{width:100%;box-sizing:border-box;padding:8px;margin-top:4px;
        border:1px solid #ccc;border-radius:4px;font-size:1em}
  .row{display:flex;gap:8px}
  .row input{flex:1}
  button{margin-top:28px;width:100%;padding:12px;background:#2563eb;
         color:#fff;border:none;border-radius:4px;font-size:1em;cursor:pointer}
  button:hover{background:#1d4ed8}
</style>
</head>
<body>
<h2>Smart Parking — Sensor setup</h2>
<p class="sub">This ESP32 drives 5 sensors. Give each slot its own label and pin numbers.</p>
<form method="POST" action="/save">
<label>Wi-Fi SSID</label>
<input name="wifi_ssid" value="{{wifi_ssid}}" required>
<label>Wi-Fi password</label>
<input name="wifi_pass" type="password" value="{{wifi_pass}}">
<label>MQTT broker IP / hostname</label>
<div class="row">
  <input name="mqtt_host" value="{{mqtt_host}}" placeholder="192.168.0.110" required style="flex:3">
  <input name="mqtt_port" type="number" value="{{mqtt_port}}" placeholder="1883" style="flex:1">
</div>
<label>Lot ID (UUID from Supabase)</label>
<input name="lot_id" value="{{lot_id}}"
       placeholder="00000000-0000-0000-0000-000000000000" required>
)";

static const char FORM_SENSOR[] PROGMEM = R"(
<h3>Sensor {{n}}</h3>
<label>Slot label <span style="font-weight:normal;color:#9ca3af">(leave blank to disable)</span></label>
<input name="s{{i}}_label" value="{{label}}" placeholder="A-0{{n}}">
<label>Trigger / Echo pins</label>
<div class="row">
  <input name="s{{i}}_trig" type="number" value="{{trig}}" placeholder="TRIG">
  <input name="s{{i}}_echo" type="number" value="{{echo}}" placeholder="ECHO">
</div>
)";

static const char FORM_TAIL[] PROGMEM = R"(
<button type="submit">Save and reboot</button>
</form></body></html>)";

static const char SAVED_HTML[] PROGMEM = R"(<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Saved</title>
<style>body{font-family:sans-serif;max-width:420px;margin:40px auto;
padding:0 16px;text-align:center}</style></head>
<body><h2>Saved!</h2><p>The sensor is rebooting. You can close this page.</p>
</body></html>)";

// ── Provisioning mode (never returns) ────────────────────────────────────────
void run_provisioning() {
    Serial.println("[prov] Starting AP: SmartParking-Setup");
    WiFi.softAP("SmartParking-Setup");
    Serial.print("[prov] AP IP: ");
    Serial.println(WiFi.softAPIP());

    DNSServer dns;
    WebServer server(80);
    dns.start(53, "*", WiFi.softAPIP());

    auto build_form = [&]() -> String {
        String html = FPSTR(FORM_HEAD);
        html.replace("{{wifi_ssid}}", cfg.wifi_ssid);
        html.replace("{{wifi_pass}}", cfg.wifi_pass);
        html.replace("{{mqtt_host}}", cfg.mqtt_host);
        html.replace("{{mqtt_port}}", String(cfg.mqtt_port));
        html.replace("{{lot_id}}",    cfg.lot_id);

        for (int i = 0; i < SENSOR_COUNT; i++) {
            String row = FPSTR(FORM_SENSOR);
            row.replace("{{n}}",     String(i + 1));
            row.replace("{{i}}",     String(i));
            row.replace("{{label}}", cfg.sensors[i].slot_label);
            row.replace("{{trig}}",  String(cfg.sensors[i].trig_pin));
            row.replace("{{echo}}",  String(cfg.sensors[i].echo_pin));
            html += row;
        }
        html += FPSTR(FORM_TAIL);
        return html;
    };

    auto serve_form = [&]() {
        server.send(200, "text/html", build_form());
    };

    server.on("/",                    HTTP_GET, serve_form);
    server.on("/generate_204",        HTTP_GET, serve_form);  // Android
    server.on("/hotspot-detect.html", HTTP_GET, serve_form);  // iOS
    server.onNotFound(serve_form);

    server.on("/save", HTTP_POST, [&]() {
        Config c;
        c.wifi_ssid = server.arg("wifi_ssid");
        c.wifi_pass = server.arg("wifi_pass");
        c.mqtt_host = server.arg("mqtt_host");
        c.mqtt_port = (uint16_t)server.arg("mqtt_port").toInt();
        c.lot_id    = server.arg("lot_id");

        for (int i = 0; i < SENSOR_COUNT; i++) {
            c.sensors[i].slot_label = server.arg("s" + String(i) + "_label");
            c.sensors[i].trig_pin   = (uint8_t)server.arg("s" + String(i) + "_trig").toInt();
            c.sensors[i].echo_pin   = (uint8_t)server.arg("s" + String(i) + "_echo").toInt();
        }

        save_config(c);
        server.send(200, "text/html", FPSTR(SAVED_HTML));
        delay(1500);
        ESP.restart();
    });

    server.begin();
    while (true) {
        dns.processNextRequest();
        server.handleClient();
    }
}

// ── Normal mode helpers ───────────────────────────────────────────────────────
float measure_distance_cm(uint8_t trig, uint8_t echo) {
    digitalWrite(trig, LOW);
    delayMicroseconds(2);
    digitalWrite(trig, HIGH);
    delayMicroseconds(10);
    digitalWrite(trig, LOW);

    long duration = pulseIn(echo, HIGH, 30000);  // 30 ms ≈ 5 m max
    if (duration == 0) return -1.0f;
    float d = duration * 0.034f / 2.0f;
    if (d < 2.0f || d > 400.0f) return -1.0f;
    return d;
}

void get_timestamp(char* buf, size_t len) {
    struct tm t;
    if (!getLocalTime(&t)) { buf[0] = '\0'; return; }
    strftime(buf, len, "%Y-%m-%dT%H:%M:%S+08:00", &t);
}

void ensure_mqtt_connected() {
    if (mqtt.connected()) return;
    while (!mqtt.connected()) {
        if (!mqtt.connect(CLIENT_ID)) delay(2000);
    }
}

// ── Arduino lifecycle ─────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    pinMode(RESET_PIN, INPUT_PULLUP);

    // Hold BOOT button for 3 s on startup → factory reset
    if (digitalRead(RESET_PIN) == LOW) {
        unsigned long held = millis();
        Serial.println("[boot] Hold for factory reset...");
        while (digitalRead(RESET_PIN) == LOW) {
            if (millis() - held >= RESET_HOLD_MS) {
                clear_config();
                Serial.println("[boot] Config cleared — rebooting.");
                delay(500);
                ESP.restart();
            }
        }
    }

    bool configured = load_config();
    if (!configured) {
        run_provisioning();  // never returns
    }

    // Normal mode startup
    for (int i = 0; i < SENSOR_COUNT; i++) {
        if (cfg.sensors[i].slot_label.length() == 0) continue;
        pinMode(cfg.sensors[i].trig_pin, OUTPUT);
        pinMode(cfg.sensors[i].echo_pin, INPUT);
    }

    Serial.printf("[wifi] Connecting to %s...\n", cfg.wifi_ssid.c_str());
    WiFi.begin(cfg.wifi_ssid.c_str(), cfg.wifi_pass.c_str());
    while (WiFi.status() != WL_CONNECTED) delay(500);
    Serial.println("[wifi] Connected.");

    uint8_t mac[6];
    WiFi.macAddress(mac);
    snprintf(CLIENT_ID, sizeof(CLIENT_ID),
             "esp32-%02x%02x%02x%02x%02x%02x",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    configTime(8 * 3600, 0, "pool.ntp.org", "time.nist.gov");

    mqtt.setServer(cfg.mqtt_host.c_str(), cfg.mqtt_port);
    ensure_mqtt_connected();
    Serial.printf("[mqtt] Connected to %s:%d\n", cfg.mqtt_host.c_str(), cfg.mqtt_port);
}

void loop() {
    ensure_mqtt_connected();
    mqtt.loop();

    char ts[32];
    get_timestamp(ts, sizeof(ts));

    char buf[96];
    for (int i = 0; i < SENSOR_COUNT; i++) {
        // Skip sensors with no slot label configured
        if (cfg.sensors[i].slot_label.length() == 0) continue;

        float distance_cm = measure_distance_cm(
            cfg.sensors[i].trig_pin,
            cfg.sensors[i].echo_pin
        );

        // Skip invalid readings — Pi gateway tracks per-slot state
        if (distance_cm < 0) continue;

        String topic = "parking/" + cfg.lot_id
                     + "/slot/" + cfg.sensors[i].slot_label + "/state";

        JsonDocument doc;
        doc["distance_cm"] = serialized(String(distance_cm, 1));
        doc["ts"]          = ts;
        serializeJson(doc, buf);

        mqtt.publish(topic.c_str(), buf);
        Serial.printf("[%s] %s\n", cfg.sensors[i].slot_label.c_str(), buf);

        // Brief gap between sensors to let ultrasonic echo dissipate
        delay(5);
    }

    delay(1000);  // 1 Hz cycle — Pi gateway handles debouncing
}
