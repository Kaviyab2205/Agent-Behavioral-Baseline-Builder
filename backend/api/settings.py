from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import MonitoringSettings
from backend.schemas import MonitoringSettingsResponse, MonitoringSettingsUpdate

router = APIRouter()

DEFAULT_SETTINGS = {
    "warning_threshold": 30.0,
    "alert_threshold": 60.0,
    "drift_threshold": 0.25,
    "drift_window": 20,
    "min_drift_sessions": 10,
    "tool_frequency_weight": 1.0,
    "sequence_weight": 1.0,
    "response_length_weight": 1.0,
    "data_access_weight": 1.5,
    "intent_weight": 0.5,
    "latency_weight": 0.8,
    "error_rate_weight": 2.0
}

@router.get("/settings", response_model=MonitoringSettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    settings = db.query(MonitoringSettings).filter(MonitoringSettings.id == "default").first()
    if not settings:
        settings = MonitoringSettings(id="default", **DEFAULT_SETTINGS)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

@router.post("/settings", response_model=MonitoringSettingsResponse)
def update_settings(payload: MonitoringSettingsUpdate, db: Session = Depends(get_db)):
    settings = db.query(MonitoringSettings).filter(MonitoringSettings.id == "default").first()
    if not settings:
        settings = MonitoringSettings(id="default", **DEFAULT_SETTINGS)
        db.add(settings)
        db.commit()
        db.refresh(settings)

    # Validate thresholds
    w_thresh = payload.warning_threshold if payload.warning_threshold is not None else settings.warning_threshold
    a_thresh = payload.alert_threshold if payload.alert_threshold is not None else settings.alert_threshold
    
    if w_thresh >= a_thresh:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid thresholds: Warning threshold ({w_thresh}) must be strictly less than Alert threshold ({a_thresh})."
        )

    # Apply updates
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
        
    db.commit()
    db.refresh(settings)
    return settings
