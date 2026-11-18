import json
import os

# Carpeta de configuración y datos basada en el usuario
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "MiPOS")
os.makedirs(USER_DATA_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(USER_DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "business_name": "Mi POS",
    "rut": "",
    "address": "",
    "phone": "",
    "logo_path": "",
    "theme": "neutro"
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        try:
            return {**DEFAULT_CONFIG, **json.load(f)}
        except json.JSONDecodeError:
            return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
