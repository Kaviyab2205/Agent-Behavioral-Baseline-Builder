from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from backend.database import get_db
from backend.models import Agent, ProductionSession, Baseline, BaselineFingerprint, MonitoringSettings, AnomalyEvent
from backend.schemas import MonitorSummaryResponse
from backend.services.behavior_analyzer import BehaviorAnalyzer
from backend.services.drift_detector import DriftDetector

router = APIRouter()

@router.post("/monitor/analyze-all")
def reanalyze_all_sessions(db: Session = Depends(get_db)):
    # 1. Fetch current settings
    settings = db.query(MonitoringSettings).filter(MonitoringSettings.id == "default").first()
    if not settings:
        raise HTTPException(status_code=400, detail="Monitoring settings not initialized.")

    # 2. Fetch all production sessions
    sessions = db.query(ProductionSession).all()
    reanalyzed_count = 0

    for sess in sessions:
        # Load active baseline for agent
        active_bl = db.query(Baseline).filter(
            Baseline.agent_id == sess.agent_id,
            Baseline.status == "active"
        ).first()
        if not active_bl:
            continue

        # Load appropriate fingerprint (clustered by intent or global)
        fingerprints = db.query(BaselineFingerprint).filter(
            BaselineFingerprint.baseline_id == active_bl.id
        ).all()
        
        fingerprint_map = {fp.intent if fp.intent else "global": fp for fp in fingerprints}
        fp_to_compare = fingerprint_map.get(sess.intent, fingerprint_map.get("global"))
        if not fp_to_compare:
            continue

        # Map fp object to dict for BehaviorAnalyzer
        fp_dict = {
            "tool_frequency": fp_to_compare.tool_frequency,
            "avg_response_length": fp_to_compare.avg_response_length,
            "response_length_stats": fp_to_compare.response_length_stats,
            "tool_sequence_patterns": fp_to_compare.tool_sequence_patterns,
            "tool_count_stats": fp_to_compare.tool_count_stats,
            "data_access_patterns": fp_to_compare.data_access_patterns,
            "intent_distribution": fp_to_compare.intent_distribution,
            "latency_stats": fp_to_compare.latency_stats,
            "error_rate": fp_to_compare.error_rate,
            "success_rate": fp_to_compare.success_rate
        }

        # Re-score
        trace_mock = {
            "tool_calls": sess.tool_calls,
            "tool_sequence": sess.tool_sequence,
            "response_length": sess.response_length,
            "latency_ms": sess.latency_ms,
            "data_access": sess.data_access,
            "intent": sess.intent,
            "success": sess.success,
            "error_count": sess.error_count
        }
        
        score, reasons = BehaviorAnalyzer.calculate_anomaly_score(trace_mock, fp_dict, settings)

        # Update severity
        if score < settings.warning_threshold:
            new_severity = "NORMAL"
        elif score < settings.alert_threshold:
            new_severity = "WARNING"
        else:
            new_severity = "ALERT"

        # Update session
        sess.anomaly_score = score
        sess.severity = new_severity
        sess.explanation = "; ".join(reasons)

        # Sync AnomalyEvent alert status
        # If it was NORMAL but is now WARNING/ALERT, create alert
        # If it was WARNING/ALERT but is now NORMAL, delete alert or resolve it
        existing_alert = db.query(AnomalyEvent).filter(AnomalyEvent.session_id == sess.session_id).first()
        
        if new_severity in ["WARNING", "ALERT"]:
            if existing_alert:
                existing_alert.severity = new_severity
                existing_alert.anomaly_score = score
                existing_alert.reasons = reasons
            else:
                alert_id = f"evt_{uuid.uuid4().hex[:8]}"
                db_alert = AnomalyEvent(
                    event_id=alert_id,
                    agent_id=sess.agent_id,
                    session_id=sess.session_id,
                    timestamp=datetime.utcnow(),
                    severity=new_severity,
                    anomaly_score=score,
                    reasons=reasons,
                    baseline_version=active_bl.version,
                    model_version=sess.model_version,
                    prompt_version=sess.prompt_version,
                    status="OPEN"
                )
                db.add(db_alert)
        else:
            # If it became normal, delete or mark RESOLVED. We will delete it to keep alerts clean.
            if existing_alert:
                db.delete(existing_alert)

        reanalyzed_count += 1

    db.commit()
    return {"message": f"Successfully re-analyzed {reanalyzed_count} production sessions."}

@router.get("/monitor/summary/{agent_id}", response_model=MonitorSummaryResponse)
def get_monitor_summary(
    agent_id: str,
    window: int = Query(100, ge=5, le=500, description="Sliding window size of recent sessions"),
    db: Session = Depends(get_db)
):
    # Verify agent
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent with ID {agent_id} not found.")

    # Fetch last W sessions
    sessions = db.query(ProductionSession).filter(
        ProductionSession.agent_id == agent_id
    ).order_by(ProductionSession.timestamp.desc()).limit(window).all()

    total_sessions = len(sessions)
    if total_sessions == 0:
        # Check drift status even with no sessions
        drift_res = DriftDetector.detect_drift(db, agent_id)
        return {
            "total_sessions": 0,
            "normal_count": 0,
            "warning_count": 0,
            "alert_count": 0,
            "avg_anomaly_score": 0.0,
            "avg_latency": 0.0,
            "avg_response_length": 0.0,
            "error_rate": 0.0,
            "drift_status": drift_res.get("status", "NORMAL"),
            "drift_score": drift_res.get("drift_score", 0.0),
            "drift_threshold": drift_res.get("drift_threshold", 0.25),
            "reasons": drift_res.get("reasons", [])
        }

    # Calculations
    normal_count = sum(1 for s in sessions if s.severity == "NORMAL")
    warning_count = sum(1 for s in sessions if s.severity == "WARNING")
    alert_count = sum(1 for s in sessions if s.severity == "ALERT")
    
    avg_score = sum(s.anomaly_score for s in sessions) / total_sessions
    avg_latency = sum(s.latency_ms for s in sessions) / total_sessions
    avg_resp_len = sum(s.response_length for s in sessions) / total_sessions
    total_errors = sum(s.error_count for s in sessions)
    error_rate = total_errors / total_sessions

    # Run Drift Detector
    drift_res = DriftDetector.detect_drift(db, agent_id)

    return {
        "total_sessions": total_sessions,
        "normal_count": normal_count,
        "warning_count": warning_count,
        "alert_count": alert_count,
        "avg_anomaly_score": avg_score,
        "avg_latency": avg_latency,
        "avg_response_length": avg_resp_len,
        "error_rate": error_rate,
        "drift_status": drift_res["status"],
        "drift_score": drift_res["drift_score"],
        "drift_threshold": drift_res.get("drift_threshold", 0.25),
        "reasons": drift_res.get("reasons", [])
    }
