import os
import yaml
from pathlib import Path

_config = None

def load_config() -> dict:
    global _config
    if _config:
        return _config
    config_path = os.environ.get("MAZARINE_CONFIG", str(Path(__file__).parent.parent / "config.yaml"))
    with open(config_path) as f:
        _config = yaml.safe_load(f)
    _config["mazarine"]["secret_key"] = os.environ.get("MAZARINE_SECRET_KEY", _config["mazarine"]["secret_key"])
    _config["mazarine"]["db_path"] = os.environ.get("MAZARINE_DB_PATH", _config["mazarine"]["db_path"])
    return _config

def get_secret_key() -> str:
    return load_config()["mazarine"]["secret_key"]

def get_db_path() -> str:
    return load_config()["mazarine"]["db_path"]

def get_upload_dir() -> str:
    d = os.environ.get("MAZARINE_UPLOAD_DIR", load_config()["mazarine"].get("upload_dir", "uploads"))
    os.makedirs(d, exist_ok=True)
    return d

def get_ai_config() -> dict:
    return load_config().get("ai", {})

def get_defaults() -> dict:
    return load_config().get("defaults", {})
