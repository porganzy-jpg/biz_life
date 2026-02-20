"""
맞춤 매칭 엔진 - 지능형 매물 추천 시스템

단순 필터링이 아니라, 사용자의 행동 패턴(후보 추가, 평점, 거절)에서
선호도를 학습하고 다차원 점수로 매칭하는 엔진.

Score breakdown (0-100):
  - location (위치):   지역 선호도 + 인프라 접근성
  - price (가격):      예산 적합도 + 시세 대비 가치
  - size (규모):       면적/구조 선호 적합도
  - quality (품질):    연식/향/층/관리비 종합
  - opportunity (기회): 시세 대비 할인 + 가격 추세
  - urgency (긴급):    신규 등록/가격 하락/경쟁 강도
"""
import json
import math
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from models.property import Property
from models.candidate import CandidateProperty
from models.saved_search import SavedSearch
from models.matching import UserProfile, MatchAlert, AlertSettings
from models.area import Area
from backend.config import settings

logger = logging.getLogger("homefinder.matching")


class MatchingEngine:
    """지능형 매칭 엔진"""

    # 기본 가중치
    DEFAULT_WEIGHTS = {
        "location": 0.30,
        "price": 0.25,
        "size": 0.15,
        "quality": 0.15,
        "opportunity": 0.10,
        "urgency": 0.05,
    }

    def __init__(self, db: Session):
        self.db = db

    # ────────────────────────────────────────────
    # 1. 사용자 프로필 빌드/학습
    # ────────────────────────────────────────────

    def get_or_create_profile(self) -> UserProfile:
        """프로필 조회 (없으면 생성)"""
        profile = self.db.query(UserProfile).first()
        if not profile:
            profile = UserProfile(
                price_min_krw=settings.BUDGET_MIN_KRW,
                price_max_krw=settings.BUDGET_MAX_KRW,
                price_sweet_min_krw=settings.BUDGET_MIN_KRW,
                price_sweet_max_krw=int(
                    settings.BUDGET_MIN_KRW
                    + (settings.BUDGET_MAX_KRW - settings.BUDGET_MIN_KRW) * 0.6
                ),
                district_weights_json=json.dumps(
                    {d: 0.5 for d in settings.TARGET_DISTRICTS},
                    ensure_ascii=False,
                ),
                preferred_types_json='["아파트"]',
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def build_user_profile(self) -> dict:
        """
        저장된 검색, 후보 매물 평점, 행동 데이터에서 선호 모델 구축.
        기존 프로필을 업데이트하고 결과를 반환.
        """
        profile = self.get_or_create_profile()

        # ── 후보 매물에서 학습 ──
        candidates = (
            self.db.query(CandidateProperty)
            .filter(CandidateProperty.status != "탈락")
            .all()
        )

        if candidates:
            property_ids = [c.property_id for c in candidates if c.property_id]
            properties = (
                self.db.query(Property)
                .filter(Property.id.in_(property_ids))
                .all()
            )
            prop_map = {p.id: p for p in properties}

            # 지역 선호도 학습
            district_scores = {}
            for cand in candidates:
                prop = prop_map.get(cand.property_id)
                if not prop or not prop.district:
                    continue

                # 가중치: 상태가 진행될수록 강한 선호
                status_weight = {
                    "발견": 0.3, "조사": 0.5, "관심": 0.8,
                    "방문예정": 0.9, "방문완료": 1.0, "결정": 1.0,
                }.get(cand.status, 0.3)

                # 평점 반영
                rating_weight = (cand.rating / 5.0) if cand.rating else 0.5

                # 거절 시 마이너스
                if cand.decision == "탈락":
                    combined = -0.3
                elif cand.decision == "최종후보":
                    combined = 1.0
                else:
                    combined = status_weight * 0.5 + rating_weight * 0.5

                if prop.district not in district_scores:
                    district_scores[prop.district] = []
                district_scores[prop.district].append(combined)

            # 지역 가중치 계산 (평균 -> 0~1 정규화)
            district_weights = {}
            if district_scores:
                for dist, scores in district_scores.items():
                    avg = sum(scores) / len(scores)
                    district_weights[dist] = round(max(0, min(1, (avg + 0.5) / 1.5)), 3)

            # 기존 config 지역도 기본값 유지
            for d in settings.TARGET_DISTRICTS:
                if d not in district_weights:
                    district_weights[d] = 0.5

            profile.district_weights_json = json.dumps(
                district_weights, ensure_ascii=False
            )

            # 가격 스윗스팟 학습 (좋은 평가를 받은 매물의 가격대)
            good_prices = []
            good_areas = []
            for cand in candidates:
                prop = prop_map.get(cand.property_id)
                if not prop:
                    continue
                # 관심 이상이거나 평점 3 이상
                is_positive = (
                    cand.status in ("관심", "방문예정", "방문완료", "결정")
                    or (cand.rating and cand.rating >= 3)
                )
                if is_positive and prop.price_krw:
                    good_prices.append(prop.price_krw)
                if is_positive and prop.area_m2:
                    good_areas.append(prop.area_m2)

            if good_prices:
                good_prices.sort()
                # 10th ~ 90th percentile
                p10 = good_prices[max(0, len(good_prices) // 10)]
                p90 = good_prices[min(len(good_prices) - 1, len(good_prices) * 9 // 10)]
                profile.price_sweet_min_krw = p10
                profile.price_sweet_max_krw = p90

            if good_areas:
                good_areas.sort()
                profile.area_preferred_m2 = round(
                    sum(good_areas) / len(good_areas), 1
                )
                profile.area_min_m2 = good_areas[max(0, len(good_areas) // 10)]
                profile.area_max_m2 = good_areas[
                    min(len(good_areas) - 1, len(good_areas) * 9 // 10)
                ]

        # ── 저장된 검색에서 학습 ──
        saved_searches = self.db.query(SavedSearch).all()
        if saved_searches:
            all_districts_from_search = []
            all_types = []
            for ss in saved_searches:
                try:
                    criteria = json.loads(ss.criteria_json)
                    ds = criteria.get("districts", [])
                    if ds:
                        all_districts_from_search.extend(ds)
                    pts = criteria.get("property_types", [])
                    if pts:
                        all_types.extend(pts)
                except (json.JSONDecodeError, AttributeError):
                    pass

            # 검색에 자주 나오는 지역 가중치 부스트
            if all_districts_from_search:
                dw = json.loads(profile.district_weights_json)
                from collections import Counter
                dist_counts = Counter(all_districts_from_search)
                max_count = max(dist_counts.values())
                for dist, count in dist_counts.items():
                    boost = 0.2 * (count / max_count)
                    current = dw.get(dist, 0.5)
                    dw[dist] = round(min(1.0, current + boost), 3)
                profile.district_weights_json = json.dumps(
                    dw, ensure_ascii=False
                )

            if all_types:
                profile.preferred_types_json = json.dumps(
                    list(set(all_types)), ensure_ascii=False
                )

        profile.last_learned_at = datetime.utcnow()
        profile.actions_count = len(candidates) if candidates else 0
        self.db.commit()
        self.db.refresh(profile)

        return self._profile_to_dict(profile)

    def update_profile_from_action(
        self, action_type: str, property_data: dict
    ) -> dict:
        """
        실시간 행동 학습.

        action_type: "candidate_add" | "rate_high" | "rate_low" | "reject" | "shortlist"
        property_data: {"district": ..., "price_krw": ..., "area_m2": ..., ...}
        """
        profile = self.get_or_create_profile()
        dw = json.loads(profile.district_weights_json)

        district = property_data.get("district")
        if district:
            current = dw.get(district, 0.5)

            # 행동별 조정 강도
            delta_map = {
                "candidate_add": 0.08,
                "rate_high": 0.12,
                "rate_low": -0.05,
                "reject": -0.15,
                "shortlist": 0.10,
            }
            delta = delta_map.get(action_type, 0.0)
            dw[district] = round(max(0, min(1.0, current + delta)), 3)
            profile.district_weights_json = json.dumps(dw, ensure_ascii=False)

        # 가격 선호도 미세 조정
        price = property_data.get("price_krw")
        if price and action_type in ("candidate_add", "rate_high", "shortlist"):
            # 선호 가격대 방향으로 점진 이동 (exponential moving average)
            alpha = 0.15
            if profile.price_sweet_min_krw and profile.price_sweet_max_krw:
                mid = (profile.price_sweet_min_krw + profile.price_sweet_max_krw) / 2
                new_mid = mid * (1 - alpha) + price * alpha
                half_range = (profile.price_sweet_max_krw - profile.price_sweet_min_krw) / 2
                profile.price_sweet_min_krw = int(new_mid - half_range)
                profile.price_sweet_max_krw = int(new_mid + half_range)

        # 면적 선호도 조정
        area = property_data.get("area_m2")
        if area and action_type in ("candidate_add", "rate_high", "shortlist"):
            if profile.area_preferred_m2:
                profile.area_preferred_m2 = round(
                    profile.area_preferred_m2 * 0.85 + area * 0.15, 1
                )
            else:
                profile.area_preferred_m2 = area

        profile.actions_count = (profile.actions_count or 0) + 1
        profile.last_learned_at = datetime.utcnow()
        self.db.commit()

        return self._profile_to_dict(profile)

    # ────────────────────────────────────────────
    # 2. 매물 매칭 스코어링
    # ────────────────────────────────────────────

    def match_property(self, prop: Property, profile: UserProfile = None) -> dict:
        """
        매물과 사용자 프로필 간의 매칭 점수 계산.
        Returns: {"score": 0-100, "breakdown": {...}, "reasons": [...]}
        """
        if profile is None:
            profile = self.get_or_create_profile()

        breakdown = {}

        # (A) Location score - 지역 선호도 매칭
        breakdown["location"] = self._score_location(prop, profile)

        # (B) Price score - 가격 적합도
        breakdown["price"] = self._score_price(prop, profile)

        # (C) Size score - 규모 적합도
        breakdown["size"] = self._score_size(prop, profile)

        # (D) Quality score - 품질 종합
        breakdown["quality"] = self._score_quality(prop, profile)

        # (E) Opportunity score - 기회 가치
        breakdown["opportunity"] = self._score_opportunity(prop)

        # (F) Urgency score - 긴급/시기 적절성
        breakdown["urgency"] = self._score_urgency(prop)

        # 가중 합산
        weights = {
            "location": profile.w_location or self.DEFAULT_WEIGHTS["location"],
            "price": profile.w_price or self.DEFAULT_WEIGHTS["price"],
            "size": profile.w_size or self.DEFAULT_WEIGHTS["size"],
            "quality": profile.w_quality or self.DEFAULT_WEIGHTS["quality"],
            "opportunity": profile.w_opportunity or self.DEFAULT_WEIGHTS["opportunity"],
            "urgency": profile.w_urgency or self.DEFAULT_WEIGHTS["urgency"],
        }
        # 가중치 정규화
        w_total = sum(weights.values())
        if w_total > 0:
            weights = {k: v / w_total for k, v in weights.items()}

        composite = sum(
            breakdown[k] * weights[k] for k in breakdown
        )

        # 보너스/페널티 적용
        bonus = self._compute_bonus(prop, profile)
        composite = max(0, min(100, composite + bonus))

        return {
            "score": round(composite, 1),
            "breakdown": {k: round(v, 1) for k, v in breakdown.items()},
            "weights": {k: round(v, 3) for k, v in weights.items()},
            "bonus": round(bonus, 1),
        }

    def _score_location(self, prop: Property, profile: UserProfile) -> float:
        """지역 선호도 + 기존 위치 점수 결합"""
        score = 50.0  # base

        # 지역 선호 가중치
        district_weights = {}
        try:
            district_weights = json.loads(profile.district_weights_json or "{}")
        except json.JSONDecodeError:
            pass

        if prop.district and prop.district in district_weights:
            pref_weight = district_weights[prop.district]
            # 0~1 -> 0~100 범위, 그중 50% 반영
            score = pref_weight * 100 * 0.5
        elif prop.district:
            # TARGET_DISTRICTS에 있으면 기본 점수
            if prop.district in settings.TARGET_DISTRICTS:
                score = 40
            else:
                score = 20

        # 기존 종합 위치 점수 반영 (나머지 50%)
        if prop.score_location:
            score += prop.score_location * 0.5
        else:
            # 지하철 거리 기반 대체
            if prop.nearest_subway_distance is not None:
                max_dist = profile.max_subway_distance or 1500
                dist_score = max(0, 1 - prop.nearest_subway_distance / max_dist) * 100
                score += dist_score * 0.3
            score += 20  # 기본 보정

        return max(0, min(100, score))

    def _score_price(self, prop: Property, profile: UserProfile) -> float:
        """가격 적합도: 예산 범위 + 스윗스팟 + 시세 대비"""
        if not prop.price_krw:
            return 30.0

        price = prop.price_krw
        score = 0.0

        # (1) 예산 범위 적합 (40%)
        p_min = profile.price_min_krw or settings.BUDGET_MIN_KRW
        p_max = profile.price_max_krw or settings.BUDGET_MAX_KRW

        if p_min <= price <= p_max:
            budget_score = 100.0
        elif price < p_min:
            # 예산 아래: 괜찮지만 약간 감점 (너무 싸면 의심)
            ratio = price / p_min if p_min > 0 else 0
            budget_score = max(40, ratio * 90)
        else:
            # 예산 초과
            over_pct = (price - p_max) / p_max * 100 if p_max > 0 else 100
            if over_pct <= 5:
                budget_score = 60
            elif over_pct <= 10:
                budget_score = 35
            elif over_pct <= 20:
                budget_score = 15
            else:
                budget_score = 5

        # (2) 스윗스팟 보너스 (30%)
        sweet_min = profile.price_sweet_min_krw or p_min
        sweet_max = profile.price_sweet_max_krw or int(
            p_min + (p_max - p_min) * 0.6
        )
        if sweet_min <= price <= sweet_max:
            sweet_score = 100.0
        else:
            # 스윗스팟에서 얼마나 벗어났나
            if price < sweet_min:
                dist_ratio = (sweet_min - price) / sweet_min if sweet_min > 0 else 1
            else:
                dist_ratio = (price - sweet_max) / sweet_max if sweet_max > 0 else 1
            sweet_score = max(20, 100 - dist_ratio * 200)

        # (3) 시세 대비 가치 (30%)
        market_score = 50.0
        if prop.price_per_m2 and prop.district:
            area_info = self._get_area_avg_price(prop.district)
            if area_info:
                ratio = prop.price_per_m2 / area_info if area_info > 0 else 1
                if ratio <= 0.85:
                    market_score = 100  # 시세보다 15%+ 저렴
                elif ratio <= 0.95:
                    market_score = 80
                elif ratio <= 1.05:
                    market_score = 65  # 시세 수준
                elif ratio <= 1.15:
                    market_score = 45
                else:
                    market_score = 25

        score = budget_score * 0.4 + sweet_score * 0.3 + market_score * 0.3
        return max(0, min(100, score))

    def _score_size(self, prop: Property, profile: UserProfile) -> float:
        """규모 적합도: 면적 선호 + 구조"""
        score = 50.0

        if prop.area_m2 and profile.area_preferred_m2:
            # 선호 면적과의 차이
            pref = profile.area_preferred_m2
            diff_ratio = abs(prop.area_m2 - pref) / pref if pref > 0 else 1

            if diff_ratio <= 0.05:
                area_score = 100  # 거의 동일
            elif diff_ratio <= 0.10:
                area_score = 90
            elif diff_ratio <= 0.20:
                area_score = 75
            elif diff_ratio <= 0.35:
                area_score = 55
            elif diff_ratio <= 0.50:
                area_score = 35
            else:
                area_score = 15
            score = area_score * 0.6 + score * 0.4

        elif prop.area_m2:
            # 선호 면적이 없으면 절대 기준 (국민평형 84m2 기준)
            if 75 <= prop.area_m2 <= 135:
                score = 80
            elif 59 <= prop.area_m2 < 75:
                score = 65
            elif 135 < prop.area_m2 <= 165:
                score = 65
            else:
                score = 40

        # 방/욕실 구조 보너스
        if prop.rooms and prop.rooms >= 3:
            score = min(100, score + 8)
        if prop.bathrooms and prop.bathrooms >= 2:
            score = min(100, score + 5)

        # 전용률 보너스
        if prop.area_m2 and prop.area_supply_m2 and prop.area_supply_m2 > 0:
            util_ratio = prop.area_m2 / prop.area_supply_m2
            if util_ratio >= 0.80:
                score = min(100, score + 7)
            elif util_ratio >= 0.75:
                score = min(100, score + 3)

        return max(0, min(100, score))

    def _score_quality(self, prop: Property, profile: UserProfile) -> float:
        """품질 종합: 연식, 층, 향, 관리비"""
        components = []

        # 연식 (30%)
        if prop.built_year:
            age = datetime.now().year - prop.built_year
            max_age = profile.max_building_age or 25
            if age <= 5:
                age_score = 100
            elif age <= 10:
                age_score = 90
            elif age <= 15:
                age_score = 75
            elif age <= max_age:
                age_score = max(30, 75 - (age - 15) * 3)
            else:
                age_score = max(10, 30 - (age - max_age) * 2)
            components.append(("age", age_score, 0.30))
        else:
            components.append(("age", 50, 0.30))

        # 층수 (25%)
        floor_score = 50
        if prop.floor:
            if prop.floor <= 0:
                floor_score = 10
            elif prop.total_floors:
                ratio = prop.floor / prop.total_floors
                if 0.3 <= ratio <= 0.8:
                    floor_score = 90
                elif ratio > 0.8:
                    floor_score = 80
                else:
                    floor_score = max(30, 50 + (ratio - 0.15) * 200)
            else:
                floor_score = min(90, max(30, 30 + prop.floor * 5))

            # 프로필 선호 층 반영
            if profile.preferred_floor_min and prop.floor < profile.preferred_floor_min:
                floor_score = max(20, floor_score - 20)
            if profile.preferred_floor_max and prop.floor > profile.preferred_floor_max:
                floor_score = max(20, floor_score - 10)

        components.append(("floor", floor_score, 0.25))

        # 향 (25%)
        dir_score = 50
        if prop.direction:
            direction_map = {
                "남향": 100, "남": 100, "남동향": 90, "남동": 90,
                "남서향": 85, "남서": 85, "동향": 70, "동": 70,
                "서향": 60, "서": 60, "북동향": 45, "북동": 45,
                "북서향": 40, "북서": 40, "북향": 30, "북": 30,
            }
            dir_score = direction_map.get(prop.direction.strip(), 50)

            # 선호 향과 일치 시 보너스
            if profile.preferred_direction and prop.direction.strip() == profile.preferred_direction:
                dir_score = min(100, dir_score + 10)

        components.append(("direction", dir_score, 0.25))

        # 관리비 (20%)
        maint_score = 50
        if prop.maintenance_fee is not None:
            if prop.maintenance_fee <= 10:
                maint_score = 100
            elif prop.maintenance_fee <= 20:
                maint_score = 80
            elif prop.maintenance_fee <= 30:
                maint_score = 65
            elif prop.maintenance_fee <= 40:
                maint_score = 50
            else:
                maint_score = max(15, 50 - (prop.maintenance_fee - 40) * 2)
        components.append(("maintenance", maint_score, 0.20))

        total = sum(s * w for _, s, w in components)
        return max(0, min(100, total))

    def _score_opportunity(self, prop: Property) -> float:
        """기회 가치: 시세 대비 할인 + 지역 가격 추세"""
        score = 50.0

        # 시세 대비 할인율
        if prop.price_per_m2 and prop.district:
            avg = self._get_area_avg_price(prop.district)
            if avg and avg > 0:
                discount = (1 - prop.price_per_m2 / avg) * 100
                if discount >= 20:
                    score = 100
                elif discount >= 10:
                    score = 85
                elif discount >= 5:
                    score = 70
                elif discount >= 0:
                    score = 55
                else:
                    score = max(20, 55 - abs(discount) * 2)

        # 지역 가격 추세 보너스
        area = (
            self.db.query(Area)
            .filter(Area.district == prop.district)
            .first()
        ) if prop.district else None

        if area and area.price_change_1y is not None:
            if area.price_change_1y >= 5:
                score = min(100, score + 10)  # 상승 지역 = 좋은 기회
            elif area.price_change_1y <= -5:
                score = min(100, score + 5)   # 하락 지역 = 저가 매수 기회

        # 경매/청약 취득 유형 보너스
        if prop.acquisition_type == "경매":
            score = min(100, score + 8)
        elif prop.acquisition_type == "청약":
            score = min(100, score + 5)

        return max(0, min(100, score))

    def _score_urgency(self, prop: Property) -> float:
        """긴급/시기: 신규 등록, 최근 가격 변동"""
        score = 50.0

        # 신규 등록 보너스 (7일 이내)
        if prop.created_at:
            days_old = (datetime.utcnow() - prop.created_at).days
            if days_old <= 1:
                score = 100  # 오늘 등록
            elif days_old <= 3:
                score = 90
            elif days_old <= 7:
                score = 75
            elif days_old <= 14:
                score = 60
            elif days_old <= 30:
                score = 45
            else:
                score = 30

        # 최근 업데이트(가격 변동 등) 시 보너스
        if prop.updated_at and prop.created_at:
            if prop.updated_at > prop.created_at + timedelta(hours=1):
                update_days = (datetime.utcnow() - prop.updated_at).days
                if update_days <= 3:
                    score = min(100, score + 15)

        return max(0, min(100, score))

    def _compute_bonus(self, prop: Property, profile: UserProfile) -> float:
        """특별 보너스/페널티"""
        bonus = 0.0

        # 이미 후보인 매물은 중복 방지를 위해 약간 감점
        existing_cand = (
            self.db.query(CandidateProperty)
            .filter(CandidateProperty.property_id == prop.id)
            .first()
        )
        if existing_cand:
            if existing_cand.decision == "탈락":
                bonus -= 30  # 탈락한 매물 강한 감점
            else:
                bonus -= 5   # 이미 관리 중이므로 약간 감점

        # 선호 매물 유형 매칭
        try:
            pref_types = json.loads(profile.preferred_types_json or "[]")
        except json.JSONDecodeError:
            pref_types = []

        if prop.property_type and pref_types:
            if prop.property_type in pref_types:
                bonus += 3
            else:
                bonus -= 5

        return bonus

    def _get_area_avg_price(self, district: str) -> Optional[int]:
        """지역 평균 평당 가격 조회"""
        area = (
            self.db.query(Area)
            .filter(Area.district == district)
            .first()
        )
        if area:
            return area.avg_price_per_m2
        return None

    # ────────────────────────────────────────────
    # 3. TOP 매칭 & 설명
    # ────────────────────────────────────────────

    def find_top_matches(self, limit: int = 20) -> List[dict]:
        """모든 활성 매물을 스코어링해서 상위 N개 반환"""
        profile = self.get_or_create_profile()

        properties = (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .all()
        )

        scored = []
        for prop in properties:
            try:
                result = self.match_property(prop, profile)
                scored.append({
                    "property_id": prop.id,
                    "property_type": prop.property_type,
                    "complex_name": prop.complex_name,
                    "district": prop.district,
                    "dong": prop.dong,
                    "address": prop.address,
                    "price_krw": prop.price_krw,
                    "area_m2": prop.area_m2,
                    "floor": prop.floor,
                    "direction": prop.direction,
                    "built_year": prop.built_year,
                    "score_composite": prop.score_composite,
                    "nearest_subway_name": prop.nearest_subway_name,
                    "nearest_subway_distance": prop.nearest_subway_distance,
                    "source_url": prop.source_url,
                    "created_at": (
                        prop.created_at.isoformat() if prop.created_at else None
                    ),
                    "match_score": result["score"],
                    "breakdown": result["breakdown"],
                    "weights": result["weights"],
                })
            except Exception as e:
                logger.error(f"Failed to match property {prop.id}: {e}")

        # 점수 내림차순 정렬
        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored[:limit]

    def explain_match(self, property_id: int) -> dict:
        """
        매칭 점수를 한국어 자연어로 설명.
        Returns: {"score": ..., "breakdown": ..., "explanation": "..."}
        """
        prop = self.db.query(Property).filter(Property.id == property_id).first()
        if not prop:
            return {"error": f"매물 ID {property_id}을(를) 찾을 수 없습니다"}

        profile = self.get_or_create_profile()
        result = self.match_property(prop, profile)

        # 한국어 설명 생성
        explanation_parts = []
        breakdown = result["breakdown"]

        name = prop.complex_name or prop.address or f"{prop.district} {prop.dong}"
        score = result["score"]

        # 종합 평가
        if score >= 90:
            grade = "최상위"
            emoji_text = "[강력 추천]"
        elif score >= 80:
            grade = "상위"
            emoji_text = "[추천]"
        elif score >= 70:
            grade = "양호"
            emoji_text = "[관심]"
        elif score >= 60:
            grade = "보통"
            emoji_text = "[참고]"
        else:
            grade = "낮음"
            emoji_text = "[참고]"

        explanation_parts.append(
            f"{emoji_text} {name} - 매칭 점수 {score:.1f}점 ({grade})"
        )

        # 각 항목별 설명
        # 위치
        loc = breakdown.get("location", 0)
        if loc >= 80:
            explanation_parts.append(
                f"- 위치({loc:.0f}점): 선호 지역에 있고 교통/환경이 우수합니다."
            )
        elif loc >= 60:
            explanation_parts.append(
                f"- 위치({loc:.0f}점): 관심 지역이며 접근성이 양호합니다."
            )
        else:
            explanation_parts.append(
                f"- 위치({loc:.0f}점): 선호도가 낮은 지역이거나 교통이 불편합니다."
            )

        # 가격
        price_s = breakdown.get("price", 0)
        if prop.price_krw:
            price_eok = prop.price_krw / 100_000_000
            if price_s >= 80:
                explanation_parts.append(
                    f"- 가격({price_s:.0f}점): {price_eok:.1f}억, 예산 내 스윗스팟에 있고 시세 대비 합리적입니다."
                )
            elif price_s >= 60:
                explanation_parts.append(
                    f"- 가격({price_s:.0f}점): {price_eok:.1f}억, 예산 범위 내에 있습니다."
                )
            else:
                explanation_parts.append(
                    f"- 가격({price_s:.0f}점): {price_eok:.1f}억, 예산 대비 다소 부담이 있습니다."
                )

        # 규모
        size_s = breakdown.get("size", 0)
        if prop.area_m2:
            pyeong = prop.area_m2 * 0.3025
            if size_s >= 80:
                explanation_parts.append(
                    f"- 규모({size_s:.0f}점): {prop.area_m2:.0f}m2({pyeong:.0f}평), 선호 크기에 잘 맞습니다."
                )
            elif size_s >= 60:
                explanation_parts.append(
                    f"- 규모({size_s:.0f}점): {prop.area_m2:.0f}m2({pyeong:.0f}평), 적정 크기입니다."
                )
            else:
                explanation_parts.append(
                    f"- 규모({size_s:.0f}점): {prop.area_m2:.0f}m2({pyeong:.0f}평), 선호 크기와 차이가 있습니다."
                )

        # 품질
        qual_s = breakdown.get("quality", 0)
        quality_details = []
        if prop.built_year:
            age = datetime.now().year - prop.built_year
            quality_details.append(f"연식 {age}년")
        if prop.direction:
            quality_details.append(prop.direction)
        if prop.floor:
            quality_details.append(f"{prop.floor}층")
        detail_str = ", ".join(quality_details) if quality_details else ""

        if qual_s >= 80:
            explanation_parts.append(
                f"- 품질({qual_s:.0f}점): {detail_str} - 매물 상태가 매우 우수합니다."
            )
        elif qual_s >= 60:
            explanation_parts.append(
                f"- 품질({qual_s:.0f}점): {detail_str} - 양호한 수준입니다."
            )
        else:
            explanation_parts.append(
                f"- 품질({qual_s:.0f}점): {detail_str} - 개선이 필요한 부분이 있습니다."
            )

        # 기회
        opp_s = breakdown.get("opportunity", 0)
        if opp_s >= 80:
            explanation_parts.append(
                f"- 기회({opp_s:.0f}점): 시세 대비 저평가되어 투자 가치가 높습니다."
            )
        elif opp_s >= 60:
            explanation_parts.append(
                f"- 기회({opp_s:.0f}점): 적정 시세 수준이며 안정적입니다."
            )

        # 긴급
        urg_s = breakdown.get("urgency", 0)
        if urg_s >= 80:
            explanation_parts.append(
                f"- 시기({urg_s:.0f}점): 최근 등록/변동이 있어 빠른 검토를 권합니다."
            )

        explanation = "\n".join(explanation_parts)

        return {
            "property_id": property_id,
            "name": name,
            "score": result["score"],
            "breakdown": result["breakdown"],
            "weights": result["weights"],
            "explanation": explanation,
        }

    # ────────────────────────────────────────────
    # 4. 신규 매물 체크 & 알림 생성
    # ────────────────────────────────────────────

    def check_new_listings(self, hours: int = 24) -> List[dict]:
        """
        최근 N시간 내 등록된 매물을 스코어링하여
        임계치 이상이면 알림을 생성.
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        new_properties = (
            self.db.query(Property)
            .filter(Property.is_active == 1)
            .filter(Property.created_at >= since)
            .all()
        )

        if not new_properties:
            return []

        profile = self.get_or_create_profile()
        alert_settings = self.db.query(AlertSettings).first()
        if not alert_settings:
            alert_settings = AlertSettings()
            self.db.add(alert_settings)
            self.db.commit()
            self.db.refresh(alert_settings)

        alerts_created = []
        dedup_cutoff = datetime.utcnow() - timedelta(
            hours=alert_settings.dedup_hours or 24
        )

        for prop in new_properties:
            try:
                result = self.match_property(prop, profile)
                score = result["score"]

                if score < (alert_settings.weekly_threshold or 70):
                    continue

                # 중복 체크
                existing_alert = (
                    self.db.query(MatchAlert)
                    .filter(
                        MatchAlert.property_id == prop.id,
                        MatchAlert.created_at >= dedup_cutoff,
                    )
                    .first()
                )
                if existing_alert:
                    continue

                # 알림 유형 결정
                if score >= (alert_settings.instant_threshold or 90):
                    alert_type = "instant"
                elif score >= (alert_settings.daily_threshold or 80):
                    alert_type = "daily_digest"
                else:
                    alert_type = "weekly"

                # 설명 생성
                explain_result = self.explain_match(prop.id)

                alert = MatchAlert(
                    property_id=prop.id,
                    match_score=score,
                    score_breakdown_json=json.dumps(
                        result["breakdown"], ensure_ascii=False
                    ),
                    explanation=explain_result.get("explanation", ""),
                    alert_type=alert_type,
                )
                self.db.add(alert)

                alerts_created.append({
                    "property_id": prop.id,
                    "match_score": score,
                    "alert_type": alert_type,
                    "breakdown": result["breakdown"],
                    "name": prop.complex_name or prop.address or f"{prop.district}",
                })

            except Exception as e:
                logger.error(f"Error checking property {prop.id}: {e}")

        self.db.commit()
        logger.info(
            f"Checked {len(new_properties)} new listings, "
            f"created {len(alerts_created)} alerts"
        )
        return alerts_created

    # ────────────────────────────────────────────
    # Utilities
    # ────────────────────────────────────────────

    def _profile_to_dict(self, profile: UserProfile) -> dict:
        """프로필을 dict로 변환"""
        try:
            district_weights = json.loads(profile.district_weights_json or "{}")
        except json.JSONDecodeError:
            district_weights = {}

        try:
            preferred_types = json.loads(profile.preferred_types_json or "[]")
        except json.JSONDecodeError:
            preferred_types = []

        return {
            "id": profile.id,
            "district_weights": district_weights,
            "price_range": {
                "min": profile.price_min_krw,
                "max": profile.price_max_krw,
                "sweet_min": profile.price_sweet_min_krw,
                "sweet_max": profile.price_sweet_max_krw,
            },
            "area_preference": {
                "min": profile.area_min_m2,
                "max": profile.area_max_m2,
                "preferred": profile.area_preferred_m2,
            },
            "weights": {
                "location": profile.w_location,
                "price": profile.w_price,
                "size": profile.w_size,
                "quality": profile.w_quality,
                "opportunity": profile.w_opportunity,
                "urgency": profile.w_urgency,
            },
            "preferences": {
                "types": preferred_types,
                "floor_min": profile.preferred_floor_min,
                "floor_max": profile.preferred_floor_max,
                "direction": profile.preferred_direction,
                "max_building_age": profile.max_building_age,
                "max_subway_distance": profile.max_subway_distance,
            },
            "meta": {
                "actions_count": profile.actions_count,
                "last_learned_at": (
                    profile.last_learned_at.isoformat()
                    if profile.last_learned_at else None
                ),
            },
        }

    def get_alert_history(
        self, limit: int = 50, offset: int = 0
    ) -> List[dict]:
        """알림 이력 조회"""
        alerts = (
            self.db.query(MatchAlert)
            .order_by(desc(MatchAlert.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for a in alerts:
            try:
                breakdown = json.loads(a.score_breakdown_json or "{}")
            except json.JSONDecodeError:
                breakdown = {}

            # 매물 정보 조회
            prop = (
                self.db.query(Property)
                .filter(Property.id == a.property_id)
                .first()
            )

            result.append({
                "id": a.id,
                "property_id": a.property_id,
                "property_name": (
                    (prop.complex_name or prop.address or f"{prop.district}")
                    if prop else "삭제된 매물"
                ),
                "property_district": prop.district if prop else None,
                "property_price_krw": prop.price_krw if prop else None,
                "match_score": a.match_score,
                "breakdown": breakdown,
                "explanation": a.explanation,
                "alert_type": a.alert_type,
                "is_sent": bool(a.is_sent),
                "is_read": bool(a.is_read),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            })

        return result

    def get_alert_settings(self) -> dict:
        """알림 설정 조회"""
        s = self.db.query(AlertSettings).first()
        if not s:
            s = AlertSettings()
            self.db.add(s)
            self.db.commit()
            self.db.refresh(s)

        return {
            "enabled": bool(s.enabled),
            "telegram_enabled": bool(s.telegram_enabled),
            "instant_threshold": s.instant_threshold,
            "daily_threshold": s.daily_threshold,
            "weekly_threshold": s.weekly_threshold,
            "quiet_start_hour": s.quiet_start_hour,
            "quiet_end_hour": s.quiet_end_hour,
            "dedup_hours": s.dedup_hours,
        }

    def update_alert_settings(self, data: dict) -> dict:
        """알림 설정 업데이트"""
        s = self.db.query(AlertSettings).first()
        if not s:
            s = AlertSettings()
            self.db.add(s)

        field_map = {
            "enabled": "enabled",
            "telegram_enabled": "telegram_enabled",
            "instant_threshold": "instant_threshold",
            "daily_threshold": "daily_threshold",
            "weekly_threshold": "weekly_threshold",
            "quiet_start_hour": "quiet_start_hour",
            "quiet_end_hour": "quiet_end_hour",
            "dedup_hours": "dedup_hours",
        }

        for key, attr in field_map.items():
            if key in data:
                val = data[key]
                if key in ("enabled", "telegram_enabled"):
                    val = 1 if val else 0
                setattr(s, attr, val)

        self.db.commit()
        self.db.refresh(s)
        return self.get_alert_settings()
