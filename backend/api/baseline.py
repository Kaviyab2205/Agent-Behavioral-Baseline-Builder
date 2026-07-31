from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Agent, Baseline, BaselineFingerprint
from backend.schemas import BaselineResponse, FingerprintResponse
from backend.services.baseline_recorder import BaselineRecorder

router = APIRouter()

@router.post("/baseline/create/{agent_id}", response_model=BaselineResponse, status_code=status.HTTP_201_CREATED)
def create_baseline(agent_id: str, db: Session = Depends(get_db)):
    try:
        baseline = BaselineRecorder.create_baseline(db, agent_id)
        return baseline
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)

@router.get("/baseline/{agent_id}", response_model=BaselineResponse)
def get_active_baseline(agent_id: str, db: Session = Depends(get_db)):
    # Check if agent exists
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent with ID {agent_id} not found.")

    # Fetch active baseline
    baseline = db.query(Baseline).filter(
        Baseline.agent_id == agent_id,
        Baseline.status == "active"
    ).first()
    
    if not baseline:
        raise HTTPException(status_code=404, detail=f"No active baseline found for agent ID {agent_id}.")
    
    return baseline

@router.get("/baseline/{agent_id}/fingerprint", response_model=FingerprintResponse)
def get_active_baseline_fingerprint(agent_id: str, db: Session = Depends(get_db)):
    # Check if agent exists
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent with ID {agent_id} not found.")

    # Fetch active baseline
    baseline = db.query(Baseline).filter(
        Baseline.agent_id == agent_id,
        Baseline.status == "active"
    ).first()
    
    if not baseline:
        raise HTTPException(status_code=404, detail=f"No active baseline found for agent ID {agent_id}.")
        
    fingerprint = db.query(BaselineFingerprint).filter(
        BaselineFingerprint.baseline_id == baseline.id
    ).first()
    
    if not fingerprint:
        raise HTTPException(status_code=404, detail=f"No fingerprint found for the active baseline of agent ID {agent_id}.")
        
    return fingerprint
