"""지하철역 데이터 로더 (JSON 시드)"""
import json
import logging
import os
from collectors.base_collector import BaseCollector

logger = logging.getLogger("homefinder.collector.subway")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class SubwayCollector(BaseCollector):
    name = "subway"

    def collect(self, **kwargs) -> dict:
        """지하철역 데이터는 seed_data.py에서 로딩"""
        path = os.path.join(DATA_DIR, "seoul_subway_stations.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"fetched": len(data), "new": 0, "updated": 0}
        return {"fetched": 0, "new": 0, "updated": 0}
