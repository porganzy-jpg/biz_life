"""후보 매물 파이프라인 API"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_pagination
from repositories.candidate_repo import CandidateRepository
from repositories.property_repo import PropertyRepository
from models.note import PropertyNote
from exceptions import NotFoundException
from cache import response_cache

router = APIRouter()


# --- Request Bodies ---

class CandidateAddBody(BaseModel):
    property_id: int = Field(description="매물 ID")
    priority: int = Field(default=3, ge=1, le=5, description="우선순위 (1=최고)")


class StatusUpdateBody(BaseModel):
    status: str = Field(description="새 상태 (발견, 조사, 관심, 방문예정, 방문완료, 결정)")


class RatingBody(BaseModel):
    rating: int = Field(ge=1, le=5, description="평점 (1~5)")
    notes: Optional[str] = Field(None, description="메모")


class NoteBody(BaseModel):
    note_type: str = Field(default="general", description="메모 유형 (general, visit, price, risk)")
    content: str = Field(description="메모 내용")


# --- Helpers ---

def _cand_to_dict(c):
    return {
        "id": c.id,
        "property_id": c.property_id,
        "auction_id": c.auction_id,
        "subscription_id": c.subscription_id,
        "status": c.status,
        "priority": c.priority,
        "rating": c.rating,
        "visit_date": c.visit_date.isoformat() if c.visit_date else None,
        "visit_notes": c.visit_notes,
        "decision": c.decision,
        "decision_reason": c.decision_reason,
        "tags": c.tags,
        "pros": c.pros,
        "cons": c.cons,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _prop_brief(p):
    return {
        "id": p.id,
        "property_type": p.property_type,
        "district": p.district,
        "dong": p.dong,
        "complex_name": p.complex_name,
        "price_krw": p.price_krw,
        "area_m2": p.area_m2,
        "score_composite": p.score_composite,
    }


# --- Routes ---

@router.get("/")
def get_pipeline_counts(db: Session = Depends(get_db)):
    """파이프라인 상태별 건수 요약"""
    repo = CandidateRepository(db)
    counts = repo.get_pipeline_counts()
    total = sum(counts.values())
    return {
        "total": total,
        "counts": counts,
    }


@router.get("/shortlist")
def get_shortlist(db: Session = Depends(get_db)):
    """숏리스트 (관심/방문예정/방문완료)"""
    cand_repo = CandidateRepository(db)
    prop_repo = PropertyRepository(db)
    items = cand_repo.get_shortlist()

    results = []
    for c in items:
        entry = _cand_to_dict(c)
        if c.property_id:
            prop = prop_repo.get_by_id(c.property_id)
            entry["property"] = _prop_brief(prop) if prop else None
        else:
            entry["property"] = None
        results.append(entry)

    return {"items": results, "count": len(results)}


@router.get("/compare")
def compare_candidates(
    id1: int = Query(..., description="후보 ID 1"),
    id2: int = Query(..., description="후보 ID 2"),
    db: Session = Depends(get_db),
):
    """두 후보 매물 비교"""
    cand_repo = CandidateRepository(db)
    prop_repo = PropertyRepository(db)

    c1 = cand_repo.get_by_id(id1)
    c2 = cand_repo.get_by_id(id2)

    if not c1:
        raise HTTPException(status_code=404, detail=f"후보 ID {id1}을(를) 찾을 수 없습니다")
    if not c2:
        raise HTTPException(status_code=404, detail=f"후보 ID {id2}을(를) 찾을 수 없습니다")

    def _enrich(c):
        entry = _cand_to_dict(c)
        if c.property_id:
            prop = prop_repo.get_by_id(c.property_id)
            if prop:
                entry["property"] = {
                    "id": prop.id,
                    "property_type": prop.property_type,
                    "district": prop.district,
                    "dong": prop.dong,
                    "address": prop.address,
                    "complex_name": prop.complex_name,
                    "price_krw": prop.price_krw,
                    "area_m2": prop.area_m2,
                    "floor": prop.floor,
                    "rooms": prop.rooms,
                    "built_year": prop.built_year,
                    "score_composite": prop.score_composite,
                    "score_location": prop.score_location,
                    "score_price": prop.score_price,
                    "score_property": prop.score_property,
                    "score_area": prop.score_area,
                    "nearest_subway_name": prop.nearest_subway_name,
                    "nearest_subway_distance": prop.nearest_subway_distance,
                }
            else:
                entry["property"] = None
        else:
            entry["property"] = None
        return entry

    return {
        "candidate1": _enrich(c1),
        "candidate2": _enrich(c2),
    }


@router.get("/list")
def list_candidates(
    status: Optional[str] = Query(None, description="파이프라인 상태 필터"),
    pagination: dict = Depends(get_pagination),
    db: Session = Depends(get_db),
):
    """후보 매물 목록 조회 (상태별 필터, 매물 정보 포함)"""
    cand_repo = CandidateRepository(db)
    prop_repo = PropertyRepository(db)

    if status:
        items = cand_repo.get_by_status(
            status=status,
            offset=pagination["offset"],
            limit=pagination["size"],
        )
    else:
        items = cand_repo.get_all(
            offset=pagination["offset"],
            limit=pagination["size"],
        )

    enriched = []
    for c in items:
        entry = _cand_to_dict(c)
        if c.property_id:
            prop = prop_repo.get_by_id(c.property_id)
            if prop:
                entry["address"] = prop.address
                entry["complex_name"] = prop.complex_name
                entry["district"] = prop.district
                entry["dong"] = prop.dong
                entry["price_krw"] = prop.price_krw
                entry["area_m2"] = prop.area_m2
                entry["score_composite"] = prop.score_composite
                entry["property_type"] = prop.property_type
        enriched.append(entry)

    return {
        "items": enriched,
        "count": len(enriched),
        "page": pagination["page"],
        "page_size": pagination["size"],
    }


@router.post("/")
def add_candidate(body: CandidateAddBody, db: Session = Depends(get_db)):
    """후보 매물 추가"""
    prop_repo = PropertyRepository(db)
    prop = prop_repo.get_by_id(body.property_id)
    if not prop:
        raise HTTPException(status_code=404, detail=f"매물 ID {body.property_id}을(를) 찾을 수 없습니다")

    cand_repo = CandidateRepository(db)

    # Check if already a candidate
    existing = cand_repo.get_by_property_id(body.property_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"매물 ID {body.property_id}은(는) 이미 후보에 등록되어 있습니다")

    candidate = cand_repo.create(
        property_id=body.property_id,
        priority=body.priority,
        status="발견",
    )

    # Invalidate candidate-dependent caches
    response_cache.invalidate_on_candidate_change()

    return _cand_to_dict(candidate)


@router.put("/{candidate_id}/status")
def update_candidate_status(
    candidate_id: int,
    body: StatusUpdateBody,
    db: Session = Depends(get_db),
):
    """후보 매물 상태 변경"""
    repo = CandidateRepository(db)
    candidate = repo.update_status(candidate_id, body.status)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"후보 ID {candidate_id}을(를) 찾을 수 없습니다")

    # Invalidate candidate-dependent caches
    response_cache.invalidate_on_candidate_change()

    return _cand_to_dict(candidate)


@router.put("/{candidate_id}/rate")
def rate_candidate(
    candidate_id: int,
    body: RatingBody,
    db: Session = Depends(get_db),
):
    """후보 매물 평점 부여"""
    repo = CandidateRepository(db)
    candidate = repo.get_by_id(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"후보 ID {candidate_id}을(를) 찾을 수 없습니다")

    candidate.rating = body.rating
    if body.notes:
        candidate.visit_notes = body.notes
    candidate.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(candidate)

    return _cand_to_dict(candidate)


@router.post("/{candidate_id}/notes")
def add_note(
    candidate_id: int,
    body: NoteBody,
    db: Session = Depends(get_db),
):
    """후보 매물에 메모 추가"""
    cand_repo = CandidateRepository(db)
    candidate = cand_repo.get_by_id(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"후보 ID {candidate_id}을(를) 찾을 수 없습니다")

    note = PropertyNote(
        property_id=candidate.property_id,
        candidate_id=candidate_id,
        note_type=body.note_type,
        content=body.content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    return {
        "id": note.id,
        "candidate_id": candidate_id,
        "property_id": note.property_id,
        "note_type": note.note_type,
        "content": note.content,
        "created_at": note.created_at.isoformat() if note.created_at else None,
    }
