from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Supabase
    supabase_url: str
    supabase_key: str

    # Gateway identity
    lot_id: str
    gateway_email: str
    gateway_password: str

    # MQTT
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883

    # Debounce — matches CLAUDE.md spec
    distance_occupied_cm: float = 80.0
    distance_free_cm: float = 120.0
    rolling_window: int = 5
    confirm_readings: int = 3
    cooldown_seconds: int = 10

    # Vision (used by detector.py; read at runtime so hot-reloadable)
    camera_confidence: float = 0.35
    camera_debounce_frames: int = 3
    camera_min_duration: int = 5
    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()  # type: ignore[call-arg]
