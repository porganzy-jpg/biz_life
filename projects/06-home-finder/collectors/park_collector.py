"""공원/한강 데이터 로더 (JSON 시드)"""
import json
import logging
import os
from collectors.base_collector import BaseCollector

logger = logging.getLogger("homefinder.collector.park")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class ParkCollector(BaseCollector):
    name = "park"

    def collect(self, **kwargs) -> dict:
        """공원 데이터는 seed_data.py에서 로딩"""
        total = 0
        for fname in ["seoul_parks.json", "han_river_access.json"]:
            path = os.path.join(DATA_DIR, fname)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    total += len(json.load(f))
        return {"fetched": total, "new": 0, "updated": 0}
