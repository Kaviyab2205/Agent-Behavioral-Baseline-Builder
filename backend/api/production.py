from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.models import ProductionSession, Agent
from backend.schemas import ProductionSimulateRequest, ProductionSessionResponse
from backend.services.production_simulator import ProductionSimulator

router = APIRouter()

@router.post("/production/simulate", response_model=List[ProductionSessionResponse], status_code=status.HTTP_201_CREATED)
def simulate_traffic(payload: ProductionSimulateRequest, db: Session = Depends(get_db)):
    try:
        sessions = ProductionSimulator.simulate_production_traffic(
            db=db,
            agent_id=payload.agent_id,
            count=payload.count,
            profile=payload.profile
        )
        return sessions
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)

@router.get("/production/sessions", response_model=List[ProductionSessionResponse])
def get_production_sessions(
    agent_id: Optional[str] = Query(None, description="Filter sessions by agent ID"),
    severity: Optional[str] = Query(None, description="Filter by severity: NORMAL, WARNING, ALERT"),
    limit: int = Query(100, ge=1, le=500, description="Limit result set size"),
    db: Session = Depends(get_db)
):
    query = db.query(ProductionSession)
    if agent_id:
        query = query.filter(ProductionSession.agent_id == agent_id)
    if severity:
        query = query.filter(ProductionSession.severity == severity.upper())
    
    # Return sorted by timestamp desc (newest first)
    return query.order_by(ProductionSession.timestamp.desc()).limit(limit).all()

@router.get("/production/sessions/{session_id}", response_model=ProductionSessionResponse)
def get_production_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ProductionSession).filter(ProductionSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Production session with ID '{session_id}' not found.")
    return session
