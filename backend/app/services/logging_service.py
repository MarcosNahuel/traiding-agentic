import json
import time
from typing import Any, Dict, Optional


class LoggingService:
    def __init__(self, file_path: Optional[str] = None) -> None:
        self.file_path = file_path or "./data/events.log"

    def _emit(self, level: str, event: str, payload: Dict[str, Any]) -> None:
        record = {
            "ts": int(time.time() * 1000),
            "level": level,
            "event": event,
            "payload": payload,
        }
        line = json.dumps(record, ensure_ascii=False)
        with open(self.file_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def info(self, event: str, payload: Dict[str, Any]) -> None:
        self._emit("INFO", event, payload)

    def error(self, event: str, payload: Dict[str, Any]) -> None:
        self._emit("ERROR", event, payload)
