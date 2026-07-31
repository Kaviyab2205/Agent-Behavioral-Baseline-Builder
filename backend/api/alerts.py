from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.models import AnomalyEvent
from backend.schemas import AnomalyEventResponse

router = APIRouter()

@router.get("/alerts", response_model=List[AnomalyEventResponse])
def get_alerts(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: OPEN, RESOLVED"),
    severity_filter: Optional[str] = Query(None, alias="severity", description="Filter by severity: WARNING, ALERT"),
    db: Session = Depends(get_db)
):
    query = db.query(AnomalyEvent)
    if status_filter:
        query = query.filter(AnomalyEvent.status == status_filter.upper())
    if severity_filter:
        query = query.filter(AnomalyEvent.severity == severity_filter.upper())
    
    return query.order_by(AnomalyEvent.timestamp.desc()).all()

@router.get("/alerts/{agent_id}", response_model=List[AnomalyEventResponse])
def get_agent_alerts(
    agent_id: str,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: OPEN, RESOLVED"),
    severity_filter: Optional[str] = Query(None, alias="severity", description="Filter by severity: WARNING, ALERT"),
    db: Session = Depends(get_db)
):
    query = db.query(AnomalyEvent).filter(AnomalyEvent.agent_id == agent_id)
    if status_filter:
        query = query.filter(AnomalyEvent.status == status_filter.upper())
    if severity_filter:
        query = query.filter(AnomalyEvent.severity == severity_filter.upper())
        
    return query.order_by(AnomalyEvent.timestamp.desc()).all()

@router.post("/alerts/{event_id}/resolve", response_model=AnomalyEventResponse)
def resolve_alert(event_id: str, db: Session = Depends(get_db)):
    alert = db.query(AnomalyEvent).filter(AnomalyEvent.event_id == event_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Anomaly alert event with ID '{event_id}' not found.")
    
    alert.status = "RESOLVED"
    db.commit()
    db.refresh(alert)
    return alert
