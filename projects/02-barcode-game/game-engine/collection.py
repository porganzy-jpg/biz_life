"""
BarcodeQuest 도감 시스템

수집, 완성도, 보상 관리
"""
from datetime import datetime
from typing import Dict, List, Optional


class MonsterCollection:
    """도감(컬렉션) 시스템"""

    # 타입별 도감 카테고리
    CATEGORIES = {
        "Fire": "화염 계열",
        "Water": "수생 계열",
        "Earth": "대지 계열",
        "Wind": "바람 계열",
        "Food": "음식 계열",
        "Tech": "테크 계열",
        "Nature": "자연 계열",
        "Spirit": "영혼 계열",
        "Dark": "암흑 계열",
        "Light": "빛 계열",
    }

    RARITY_ORDER = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]

    def __init__(self):
        self.collection: Dict[str, dict] = {}  # monster_id → monster data
        self.discovery_log: List[dict] = []

    def add_monster(self, monster: dict) -> dict:
        """
        몬스터 도감 등록

        Returns:
            dict: {is_new, monster_id, collection_size, rarity_message}
        """
        monster_id = monster["id"]
        is_new = monster_id not in self.collection

        if is_new:
            self.collection[monster_id] = {
                **monster,
                "discovered_at": datetime.now().isoformat(),
                "battle_count": 0,
                "win_count": 0,
            }
            self.discovery_log.append({
                "monster_id": monster_id,
                "name": monster["name"],
                "rarity": monster["rarity"],
                "timestamp": datetime.now().isoformat(),
            })

        return {
            "is_new": is_new,
            "monster_id": monster_id,
            "collection_size": len(self.collection),
            "rarity_message": f"NEW! {monster['rarity']} 몬스터 발견!" if is_new else "이미 보유 중",
        }

    def get_completion_stats(self) -> dict:
        """도감 완성도 통계"""
        by_rarity = {}
        by_type = {}

        for m in self.collection.values():
            r = m.get("rarity", "Common")
            by_rarity[r] = by_rarity.get(r, 0) + 1

            t = m.get("primary_type", "Unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_collected": len(self.collection),
            "by_rarity": by_rarity,
            "by_type": by_type,
            "rarity_progress": {
                r: by_rarity.get(r, 0) for r in self.RARITY_ORDER
            },
        }

    def get_collection_list(self, sort_by: str = "rarity") -> list:
        """도감 목록 반환"""
        monsters = list(self.collection.values())

        if sort_by == "rarity":
            monsters.sort(key=lambda m: self.RARITY_ORDER.index(m.get("rarity", "Common")), reverse=True)
        elif sort_by == "name":
            monsters.sort(key=lambda m: m.get("name", ""))
        elif sort_by == "level":
            monsters.sort(key=lambda m: m.get("level", 1), reverse=True)

        return monsters

    def check_rewards(self) -> list:
        """완성도 기반 보상 확인"""
        stats = self.get_completion_stats()
        total = stats["total_collected"]
        rewards = []

        milestones = [
            (5, "초보 수집가", 100),
            (10, "열정 수집가", 300),
            (25, "마스터 수집가", 1000),
            (50, "레전더리 수집가", 5000),
            (100, "도감 완성자", 20000),
        ]

        for count, title, gold in milestones:
            if total >= count:
                rewards.append({"title": title, "gold": gold, "requirement": f"{count}종 수집"})

        # 희귀도별 보상
        for rarity in ["Rare", "Epic", "Legendary"]:
            count = stats["by_rarity"].get(rarity, 0)
            if count >= 3:
                rewards.append({
                    "title": f"{rarity} 컬렉터",
                    "gold": {"Rare": 500, "Epic": 2000, "Legendary": 10000}[rarity],
                    "requirement": f"{rarity} 3종 이상",
                })

        return rewards
