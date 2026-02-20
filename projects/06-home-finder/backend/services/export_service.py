"""내보내기 서비스 - CSV 및 HTML 보고서 생성"""
import csv
import io
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from models.property import Property
from models.candidate import CandidateProperty
from models.note import PropertyNote
from repositories.candidate_repo import CandidateRepository
from repositories.property_repo import PropertyRepository


def _format_price_krw(price_krw: Optional[int]) -> str:
    """가격을 한국식 억/만 단위로 포맷"""
    if not price_krw:
        return ""
    eok = price_krw // 100_000_000
    man = (price_krw % 100_000_000) // 10_000
    if eok > 0 and man > 0:
        return f"{eok}억 {man:,}만"
    if eok > 0:
        return f"{eok}억"
    if man > 0:
        return f"{man:,}만"
    return str(price_krw)


def _format_area(area_m2: Optional[float]) -> str:
    """면적 포맷 (m2 + 평)"""
    if not area_m2:
        return ""
    pyeong = area_m2 / 3.3058
    return f"{area_m2:.1f}m2 ({pyeong:.1f}평)"


def _get_latest_note(db: Session, candidate_id: int) -> str:
    """후보의 가장 최근 메모 조회"""
    note = (
        db.query(PropertyNote)
        .filter(PropertyNote.candidate_id == candidate_id)
        .order_by(desc(PropertyNote.created_at))
        .first()
    )
    return note.content if note else ""


class ExportService:
    def __init__(self, db: Session):
        self.db = db
        self.candidate_repo = CandidateRepository(db)
        self.property_repo = PropertyRepository(db)

    def _get_filtered_candidates(
        self,
        status: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        min_score: Optional[float] = None,
        district: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
    ) -> list:
        """필터 조건에 맞는 후보 + 매물 정보 조회"""
        query = (
            self.db.query(CandidateProperty, Property)
            .outerjoin(Property, CandidateProperty.property_id == Property.id)
        )

        # 상태 필터 (단일)
        if status:
            query = query.filter(CandidateProperty.status == status)

        # 상태 필터 (복수)
        if statuses:
            query = query.filter(CandidateProperty.status.in_(statuses))

        # 최소 점수 필터
        if min_score is not None:
            query = query.filter(Property.score_composite >= min_score)

        # 구 필터
        if district:
            query = query.filter(Property.district == district)

        # 가격 범위 필터
        if price_min is not None:
            query = query.filter(Property.price_krw >= price_min)
        if price_max is not None:
            query = query.filter(Property.price_krw <= price_max)

        query = query.order_by(
            CandidateProperty.priority.asc(),
            Property.score_composite.desc().nullslast(),
        )

        return query.all()

    def export_candidates_csv(
        self,
        status: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        min_score: Optional[float] = None,
        district: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
    ) -> str:
        """후보 매물 CSV 내보내기 (UTF-8 BOM 포함, 엑셀 호환)"""
        rows = self._get_filtered_candidates(
            status=status,
            statuses=statuses,
            min_score=min_score,
            district=district,
            price_min=price_min,
            price_max=price_max,
        )

        output = io.StringIO()
        # UTF-8 BOM for Excel compatibility
        output.write("\ufeff")

        writer = csv.writer(output)

        # 헤더
        writer.writerow([
            "단지명",
            "구",
            "동",
            "주소",
            "가격",
            "면적",
            "층",
            "점수",
            "상태(파이프라인)",
            "우선순위",
            "평가",
            "장점",
            "단점",
            "메모",
        ])

        for cand, prop in rows:
            # 가장 최근 메모 가져오기
            latest_note = _get_latest_note(self.db, cand.id)

            writer.writerow([
                prop.complex_name if prop else "",
                prop.district if prop else "",
                prop.dong if prop else "",
                prop.address if prop else "",
                _format_price_krw(prop.price_krw if prop else None),
                _format_area(prop.area_m2 if prop else None),
                f"{prop.floor}층/{prop.total_floors}층" if prop and prop.floor else "",
                f"{prop.score_composite:.1f}" if prop and prop.score_composite else "",
                cand.status or "",
                cand.priority or "",
                f"{cand.rating}/5" if cand.rating else "",
                cand.pros or "",
                cand.cons or "",
                latest_note or cand.visit_notes or "",
            ])

        return output.getvalue()

    def export_properties_csv(
        self,
        district: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        score_min: Optional[float] = None,
        property_type: Optional[str] = None,
    ) -> str:
        """매물 검색 결과 CSV 내보내기 (UTF-8 BOM 포함, 엑셀 호환)"""
        query = self.db.query(Property).filter(Property.is_active == 1)

        if district:
            query = query.filter(Property.district == district)
        if price_min is not None:
            query = query.filter(Property.price_krw >= price_min)
        if price_max is not None:
            query = query.filter(Property.price_krw <= price_max)
        if score_min is not None:
            query = query.filter(Property.score_composite >= score_min)
        if property_type:
            query = query.filter(Property.property_type == property_type)

        query = query.order_by(Property.score_composite.desc().nullslast())
        properties = query.all()

        output = io.StringIO()
        # UTF-8 BOM for Excel compatibility
        output.write("\ufeff")

        writer = csv.writer(output)

        # 헤더
        writer.writerow([
            "단지명",
            "유형",
            "구",
            "동",
            "주소",
            "가격",
            "면적",
            "층",
            "방수",
            "향",
            "건축년도",
            "종합점수",
            "위치점수",
            "가격점수",
            "매물점수",
            "지역점수",
            "가장가까운역",
            "역거리(m)",
            "출처",
        ])

        for p in properties:
            writer.writerow([
                p.complex_name or "",
                p.property_type or "",
                p.district or "",
                p.dong or "",
                p.address or "",
                _format_price_krw(p.price_krw),
                _format_area(p.area_m2),
                f"{p.floor}층/{p.total_floors}층" if p.floor else "",
                p.rooms or "",
                p.direction or "",
                p.built_year or "",
                f"{p.score_composite:.1f}" if p.score_composite else "",
                f"{p.score_location:.1f}" if p.score_location else "",
                f"{p.score_price:.1f}" if p.score_price else "",
                f"{p.score_property:.1f}" if p.score_property else "",
                f"{p.score_area:.1f}" if p.score_area else "",
                p.nearest_subway_name or "",
                f"{p.nearest_subway_distance:.0f}" if p.nearest_subway_distance else "",
                p.source or "",
            ])

        return output.getvalue()

    def export_candidates_report(
        self,
        status: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        min_score: Optional[float] = None,
        district: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
    ) -> str:
        """후보 매물 인쇄용 HTML 보고서 생성"""
        rows = self._get_filtered_candidates(
            status=status,
            statuses=statuses,
            min_score=min_score,
            district=district,
            price_min=price_min,
            price_max=price_max,
        )

        # --- 통계 계산 ---
        total_count = len(rows)
        scores = [
            prop.score_composite
            for cand, prop in rows
            if prop and prop.score_composite is not None
        ]
        avg_score = sum(scores) / len(scores) if scores else 0
        prices = [
            prop.price_krw
            for cand, prop in rows
            if prop and prop.price_krw is not None
        ]
        price_min_val = min(prices) if prices else 0
        price_max_val = max(prices) if prices else 0

        # 상태별 건수
        status_counts = {}
        for cand, prop in rows:
            s = cand.status or "미정"
            status_counts[s] = status_counts.get(s, 0) + 1

        # 상위 후보 (점수 기준)
        top_candidates = sorted(
            [(c, p) for c, p in rows if p and p.score_composite is not None],
            key=lambda x: x[1].score_composite,
            reverse=True,
        )[:10]

        # --- HTML 생성 ---
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 후보 카드 생성
        candidate_cards_html = ""
        for cand, prop in rows:
            if not prop:
                continue
            latest_note = _get_latest_note(self.db, cand.id)

            score_color = "#198754" if (prop.score_composite or 0) >= 70 else (
                "#0d6efd" if (prop.score_composite or 0) >= 50 else "#6c757d"
            )
            priority_label = {1: "최우선", 2: "높음", 3: "보통", 4: "낮음", 5: "최하"}.get(
                cand.priority, "보통"
            )
            rating_stars = ("*" * (cand.rating or 0)) if cand.rating else "-"

            # 점수 분석 바
            def score_bar(label, value):
                v = value or 0
                return f"""
                <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">
                    <span style="width:40px;font-size:0.75rem;color:#666;">{label}</span>
                    <div style="flex:1;background:#e9ecef;height:8px;border-radius:4px;overflow:hidden;">
                        <div style="width:{v}%;height:100%;background:{score_color};border-radius:4px;"></div>
                    </div>
                    <span style="width:30px;font-size:0.75rem;color:#333;text-align:right;">{v:.0f}</span>
                </div>"""

            candidate_cards_html += f"""
            <div style="border:1px solid #dee2e6;border-radius:8px;padding:16px;margin-bottom:12px;page-break-inside:avoid;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
                    <div>
                        <div style="font-size:1.1rem;font-weight:bold;">{prop.complex_name or prop.address or '매물 ' + str(prop.id)}</div>
                        <div style="font-size:0.85rem;color:#666;">{prop.district or ''} {prop.dong or ''} | {prop.address or ''}</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="width:56px;height:56px;border-radius:50%;background:{score_color};color:white;display:flex;align-items:center;justify-content:center;font-size:1.3rem;font-weight:bold;">
                            {prop.score_composite:.0f if prop.score_composite else '-'}
                        </div>
                        <div style="font-size:0.7rem;color:#888;margin-top:2px;">종합점수</div>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;margin-bottom:10px;">
                    <div><span style="color:#666;font-size:0.8rem;">가격:</span> <strong style="color:#0d6efd;">{_format_price_krw(prop.price_krw)}</strong></div>
                    <div><span style="color:#666;font-size:0.8rem;">면적:</span> <strong>{_format_area(prop.area_m2)}</strong></div>
                    <div><span style="color:#666;font-size:0.8rem;">층:</span> {prop.floor or '-'}층/{prop.total_floors or '-'}층</div>
                    <div><span style="color:#666;font-size:0.8rem;">상태:</span> <span style="background:#e9ecef;padding:2px 8px;border-radius:4px;font-size:0.8rem;">{cand.status}</span></div>
                    <div><span style="color:#666;font-size:0.8rem;">우선순위:</span> {priority_label} ({cand.priority})</div>
                    <div><span style="color:#666;font-size:0.8rem;">평가:</span> {rating_stars}</div>
                </div>
                <div style="margin-bottom:8px;">
                    {score_bar("위치", prop.score_location)}
                    {score_bar("가격", prop.score_price)}
                    {score_bar("매물", prop.score_property)}
                    {score_bar("지역", prop.score_area)}
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;font-size:0.85rem;">
                    <div><span style="color:#198754;font-weight:600;">장점:</span> {cand.pros or '-'}</div>
                    <div><span style="color:#dc3545;font-weight:600;">단점:</span> {cand.cons or '-'}</div>
                </div>
                {'<div style="margin-top:6px;font-size:0.82rem;background:#f8f9fa;padding:6px 10px;border-radius:4px;"><span style="color:#666;">메모:</span> ' + (latest_note or cand.visit_notes) + '</div>' if (latest_note or cand.visit_notes) else ''}
            </div>"""

        # 비교 테이블 (상위 후보)
        comparison_rows_html = ""
        for cand, prop in top_candidates:
            comparison_rows_html += f"""
                <tr>
                    <td style="font-weight:600;">{prop.complex_name or prop.address or '-'}</td>
                    <td>{prop.district or ''}</td>
                    <td style="color:#0d6efd;font-weight:600;">{_format_price_krw(prop.price_krw)}</td>
                    <td>{_format_area(prop.area_m2)}</td>
                    <td>{prop.floor or '-'}</td>
                    <td style="font-weight:bold;">{prop.score_composite:.1f if prop.score_composite else '-'}</td>
                    <td>{prop.score_location:.0f if prop.score_location else '-'}</td>
                    <td>{prop.score_price:.0f if prop.score_price else '-'}</td>
                    <td>{prop.score_property:.0f if prop.score_property else '-'}</td>
                    <td>{prop.score_area:.0f if prop.score_area else '-'}</td>
                    <td>{cand.status}</td>
                    <td>{cand.priority}</td>
                    <td>{cand.rating or '-'}</td>
                </tr>"""

        # 상태별 통계 HTML
        status_items_html = ""
        for s, cnt in status_counts.items():
            status_items_html += f"""
                <div style="text-align:center;padding:8px 16px;">
                    <div style="font-size:1.5rem;font-weight:bold;">{cnt}</div>
                    <div style="font-size:0.8rem;color:#666;">{s}</div>
                </div>"""

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HomeFinder 후보 매물 보고서</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Malgun Gothic', '맑은 고딕', sans-serif; color: #333; padding: 20px; max-width: 1100px; margin: 0 auto; }}
        @media print {{
            body {{ padding: 10px; }}
            .no-print {{ display: none !important; }}
            .page-break {{ page-break-before: always; }}
        }}
        h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
        h2 {{ font-size: 1.15rem; margin: 24px 0 12px 0; padding-bottom: 6px; border-bottom: 2px solid #0d6efd; color: #0d6efd; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
        th {{ background: #f8f9fa; padding: 8px 6px; text-align: left; border-bottom: 2px solid #dee2e6; font-weight: 600; white-space: nowrap; }}
        td {{ padding: 6px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f8f9fa; }}
        .summary-box {{ background: #f8f9fa; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
        .summary-grid {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .summary-card {{ background: white; border-radius: 8px; padding: 16px; text-align: center; min-width: 150px; flex: 1; border: 1px solid #e9ecef; }}
        .summary-card .value {{ font-size: 1.6rem; font-weight: bold; color: #0d6efd; }}
        .summary-card .label {{ font-size: 0.8rem; color: #666; margin-top: 4px; }}
        .btn-print {{ background: #0d6efd; color: white; border: none; padding: 8px 20px; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }}
        .btn-print:hover {{ background: #0b5ed7; }}
    </style>
</head>
<body>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <div>
            <h1>HomeFinder 후보 매물 보고서</h1>
            <div style="font-size:0.85rem;color:#666;">생성일시: {now_str}</div>
        </div>
        <button class="btn-print no-print" onclick="window.print()">인쇄하기</button>
    </div>

    <!-- 요약 통계 -->
    <div class="summary-box">
        <div class="summary-grid">
            <div class="summary-card">
                <div class="value">{total_count}</div>
                <div class="label">전체 후보</div>
            </div>
            <div class="summary-card">
                <div class="value">{avg_score:.1f}</div>
                <div class="label">평균 점수</div>
            </div>
            <div class="summary-card">
                <div class="value">{_format_price_krw(price_min_val)}</div>
                <div class="label">최저 가격</div>
            </div>
            <div class="summary-card">
                <div class="value">{_format_price_krw(price_max_val)}</div>
                <div class="label">최고 가격</div>
            </div>
        </div>
    </div>

    <!-- 상태별 분포 -->
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px;background:#f8f9fa;border-radius:8px;padding:12px;justify-content:center;">
        {status_items_html}
    </div>

    <!-- 후보 카드 -->
    <h2>후보 매물 상세</h2>
    {candidate_cards_html if candidate_cards_html else '<p style="color:#999;text-align:center;padding:40px;">조건에 맞는 후보가 없습니다.</p>'}

    <!-- 비교 테이블 -->
    <div class="page-break"></div>
    <h2>상위 후보 비교표 (점수순 최대 10건)</h2>
    <div style="overflow-x:auto;">
        <table>
            <thead>
                <tr>
                    <th>단지명</th>
                    <th>구</th>
                    <th>가격</th>
                    <th>면적</th>
                    <th>층</th>
                    <th>종합</th>
                    <th>위치</th>
                    <th>가격</th>
                    <th>매물</th>
                    <th>지역</th>
                    <th>상태</th>
                    <th>우선순위</th>
                    <th>평가</th>
                </tr>
            </thead>
            <tbody>
                {comparison_rows_html if comparison_rows_html else '<tr><td colspan="13" style="text-align:center;color:#999;padding:20px;">데이터 없음</td></tr>'}
            </tbody>
        </table>
    </div>

    <div style="margin-top:30px;text-align:center;font-size:0.75rem;color:#aaa;">
        HomeFinder - 마지막 집 찾기 | {now_str} 생성
    </div>
</body>
</html>"""

        return html
