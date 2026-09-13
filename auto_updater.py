import os
import sys
import threading
import time

MAX_EXE_SIZE = 536870912
ASSET_NAME = "ShaddaAntiDetect.dmg"


class UpdateManager:
    def __init__(self, config_provider=None, current_version="0.1"):
        self.config_provider = config_provider
        self.current_version = current_version
        self.state = "idle"
        self.progress = 0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.error_message = None
        self._thread = None

    def status(self):
        return {
            "state": self.state,
            "progress": self.progress,
            "downloadedBytes": self.downloaded_bytes,
            "totalBytes": self.total_bytes,
            "error": self.error_message,
            "currentVersion": self.current_version,
            "isLatest": True
        }

    def _set(self, state, progress=0, error=None):
        self.state = state
        self.progress = progress
        self.error_message = error

    def start(self, download_url=None, expected_sha=None, expected_size=None):
        self._set("idle", 100)
        return True

    def launch_replacer(self):
        return False
