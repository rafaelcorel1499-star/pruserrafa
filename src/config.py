from __future__ import annotations

import json
import os

from app_paths import data_dir
from sms_parser import DEFAULT_TEMPLATE

DEFAULTS = {
    "port": "auto",
    "baudrate": 115200,
    "manual_ports": [],
    "business_name": "",
    "logo_path": "",
    "primary": "#8B1FE8",
    "secondary": "#FFFFFF",
    "voice_enabled": True,
    "voice_name": "es-CO-SalomeNeural",
    "desktop_notifications": True,
    "autostart": False,
    "volume": 75,
    "message_template": DEFAULT_TEMPLATE,
}


class Config:
    def __init__(self):
        self.path = data_dir() / "config.json"
        self.data = json.loads(json.dumps(DEFAULTS))
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    def save(self):
        tmp = str(self.path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
