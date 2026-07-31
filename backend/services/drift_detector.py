from sqlalchemy.orm import Session
from typing import Dict, Any, List
from datetime import datetime
import uuid

from backend.models import Agent, Baseline, BaselineFingerprint, ProductionSession, DriftEvent, MonitoringSettings
from backend.services.behavior_analyzer import BehaviorAnalyzer

class DriftDetector:
    @staticmethod
    def _calculate_tvd(dist1: Dict[str, float], dist2: Dict[str, float]) -> float:
        """
        Calculates Total Variation Distance (TVD) between two relative distributions.
        TVD = 0.5 * sum(|P(x) - Q(x)|)
        Ranges from 0.0 (identical) to 1.0 (completely disjoint).
        """
        all_keys = set(dist1.keys()).union(set(dist2.keys()))
        tvd_sum = 0.0
        for k in all_keys:
            v1 = dist1.get(k, 0.0)
            v2 = dist2.get(k, 0.0)
            tvd_sum += abs(v1 - v2)
        return 0.5 * tvd_sum

    @classmethod
    def detect_drift(cls, db: Session, agent_id: str) -> Dict[str, Any]:
        # 1. Load active baseline
        baseline = db.query(Baseline).filter(
            Baseline.agent_id == agent_id,
            Baseline.status == "active"
        ).first()
        if not baseline:
            return {
                "drift_detected": False,
                "drift_score": 0.0,
                "status": "NO_ACTIVE_BASELINE",
                "reasons": ["No active baseline found for this agent."]
            }

        # Load global baseline fingerprint
        baseline_fp = db.query(BaselineFingerprint).filter(
            BaselineFingerprint.baseline_id == baseline.id,
            BaselineFingerprint.intent == None
        ).first()
        if not baseline_fp:
            return {
                "drift_detected": False,
                "drift_score": 0.0,
                "status": "NO_FINGERPRINT",
                "reasons": ["Baseline fingerprint missing."]
            }

        # 2. Fetch monitoring settings
        settings = db.query(MonitoringSettings).filter(
            MonitoringSettings.id == "default"
        ).first()
        window_size = settings.drift_window if settings else 20
        min_sessions = settings.min_drift_sessions if settings else 10
        drift_threshold = settings.drift_threshold if settings else 0.25

        # 3. Query the last N production sessions
        sessions = db.query(ProductionSession).filter(
            ProductionSession.agent_id == agent_id
        ).order_by(ProductionSession.timestamp.desc()).limit(window_size).all()

        if len(sessions) < min_sessions:
            return {
                "drift_detected": False,
                "drift_score": 0.0,
                "status": "INSUFFICIENT_DATA",
                "reasons": [f"Insufficient production sessions to evaluate drift (need at least {min_sessions}, have {len(sessions)})"]
            }

        # 4. Map DB sessions back to traces for BehaviorAnalyzer
        prod_traces = []
        model_versions_in_window = set()
        prompt_versions_in_window = set()
        for s in sessions:
            prod_traces.append({
                "tool_calls": s.tool_calls,
                "tool_sequence": s.tool_sequence,
                "response_length": s.response_length,
                "latency_ms": s.latency_ms,
                "data_access": s.data_access,
                "intent": s.intent,
                "success": s.success,
                "error_count": s.error_count
            })
            model_versions_in_window.add(s.model_version)
            prompt_versions_in_window.add(s.prompt_version)

        # 5. Compute running production fingerprint over the window
        prod_fp = BehaviorAnalyzer.calculate_fingerprint(prod_traces)

        # 6. Compare distributions and calculate shifts
        # A. Tool frequency shift (TVD)
        tvd_tool = cls._calculate_tvd(baseline_fp.tool_frequency, prod_fp["tool_frequency"])
        
        # B. Sequence transition shift (TVD)
        tvd_seq = cls._calculate_tvd(baseline_fp.tool_sequence_patterns, prod_fp["tool_sequence_patterns"])
        
        # C. Response length shift (using median to prevent outlier skewing)
        import numpy as np
        base_len = baseline_fp.avg_response_length
        prod_len = float(np.median([t["response_length"] for t in prod_traces]))
        len_shift = min(1.0, abs(prod_len - base_len) / max(1.0, base_len))
        
        # D. Data access shift (TVD)
        tvd_data = cls._calculate_tvd(baseline_fp.data_access_patterns, prod_fp["data_access_patterns"])
        
        # E. Intent distribution shift (TVD)
        tvd_intent = cls._calculate_tvd(baseline_fp.intent_distribution, prod_fp["intent_distribution"])
        
        # F. Latency shift (using median to prevent outlier skewing)
        base_lat = baseline_fp.latency_stats.get("avg", 0.0)
        prod_lat = float(np.median([t["latency_ms"] for t in prod_traces]))
        lat_shift = min(1.0, abs(prod_lat - base_lat) / max(1.0, base_lat))
        
        # G. Error rate shift (absolute difference capped at 1.0)
        err_shift = min(1.0, abs(prod_fp["error_rate"] - baseline_fp.error_rate))

        # Overall Drift Score: simple average of shifts
        drift_score = (tvd_tool + tvd_seq + len_shift + tvd_data + tvd_intent + lat_shift + err_shift) / 7.0
        
        # Evaluate drift trigger
        drift_detected = drift_score > drift_threshold
        
        reasons = []
        if drift_detected:
            if tvd_tool > 0.15:
                reasons.append(f"Tool frequency distribution shifted significantly (TVD: {tvd_tool:.1%})")
            if tvd_seq > 0.15:
                reasons.append(f"Tool sequence execution sequence patterns shifted (TVD: {tvd_seq:.1%})")
            if len_shift > 0.20:
                reasons.append(f"Average response length shifted by {len_shift:.1%} ({int(prod_len)} vs {int(base_len)} chars)")
            if tvd_data > 0.15:
                reasons.append(f"Data access category patterns shifted (TVD: {tvd_data:.1%})")
            if lat_shift > 0.20:
                reasons.append(f"Average latency shifted by {lat_shift:.1%} ({prod_lat:.1f}ms vs {base_lat:.1f}ms)")
            
            if not reasons:
                reasons.append(f"Consistently elevated behavioral shift across metrics (Drift Score: {drift_score:.2f})")

            # Check if we should log a DriftEvent (prevent duplicate logging on same timestamp)
            # Log a drift event if no active unresolved drift event is logged recently
            existing_event = db.query(DriftEvent).filter(
                DriftEvent.agent_id == agent_id,
                DriftEvent.baseline_id == baseline.id,
                DriftEvent.drift_score == drift_score
            ).first()
            
            if not existing_event:
                drift_evt_id = f"drft_{uuid.uuid4().hex[:8]}"
                # Extract most common model/prompt in the window
                current_model = max(model_versions_in_window) if model_versions_in_window else "unknown"
                current_prompt = max(prompt_versions_in_window) if prompt_versions_in_window else "unknown"
                
                db_drift = DriftEvent(
                    id=drift_evt_id,
                    agent_id=agent_id,
                    timestamp=datetime.utcnow(),
                    baseline_id=baseline.id,
                    model_version=current_model,
                    prompt_version=current_prompt,
                    drift_score=drift_score,
                    reasons=reasons
                )
                db.add(db_drift)
                db.commit()

        return {
            "drift_detected": drift_detected,
            "drift_score": drift_score,
            "drift_threshold": drift_threshold,
            "baseline_version": baseline.version,
            "model_versions": list(model_versions_in_window),
            "prompt_versions": list(prompt_versions_in_window),
            "reasons": reasons if drift_detected else ["Production behavior matches baseline bounds."],
            "status": "DRIFT_DETECTED" if drift_detected else "NORMAL",
            "shifts": {
                "tool_frequency": tvd_tool,
                "tool_sequence": tvd_seq,
                "response_length": len_shift,
                "data_access": tvd_data,
                "intent_distribution": tvd_intent,
                "latency": lat_shift,
                "error_rate": err_shift
            }
        }
