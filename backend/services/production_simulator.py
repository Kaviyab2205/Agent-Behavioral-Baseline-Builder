import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.models import Agent, Baseline, BaselineFingerprint, ProductionSession, AnomalyEvent, MonitoringSettings
from backend.services.scenario_generator import ScenarioGenerator
from backend.services.agent_simulator import AgentSimulator
from backend.services.behavior_analyzer import BehaviorAnalyzer

class ProductionSimulator:
    @staticmethod
    def _get_default_settings() -> dict:
        return {
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

    @classmethod
    def simulate_production_traffic(
        cls, 
        db: Session, 
        agent_id: str, 
        count: int = 10, 
        profile: str = "normal"
    ) -> List[ProductionSession]:
        # 1. Fetch agent details
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ValueError(f"Agent with ID {agent_id} not found.")

        # 2. Fetch active baseline metadata
        active_baseline = db.query(Baseline).filter(
            Baseline.agent_id == agent_id,
            Baseline.status == "active"
        ).first()
        if not active_baseline:
            raise ValueError(f"Baseline creation is required first. No active baseline found for agent ID {agent_id}.")

        # 3. Load baseline fingerprints (global and intent-specific)
        fingerprints = db.query(BaselineFingerprint).filter(
            BaselineFingerprint.baseline_id == active_baseline.id
        ).all()
        
        fingerprint_map = {}
        for fp in fingerprints:
            # Map by intent name. None / "global" represents global fingerprint
            intent_key = fp.intent if fp.intent else "global"
            fingerprint_map[intent_key] = {
                "tool_frequency": fp.tool_frequency,
                "avg_response_length": fp.avg_response_length,
                "response_length_stats": fp.response_length_stats,
                "tool_sequence_patterns": fp.tool_sequence_patterns,
                "tool_count_stats": fp.tool_count_stats,
                "data_access_patterns": fp.data_access_patterns,
                "intent_distribution": fp.intent_distribution,
                "latency_stats": fp.latency_stats,
                "error_rate": fp.error_rate,
                "success_rate": fp.success_rate
            }

        global_fp = fingerprint_map.get("global")
        if not global_fp:
            raise ValueError(f"Global baseline fingerprint not found for baseline ID {active_baseline.id}")

        # 4. Fetch monitoring settings or load defaults
        settings = db.query(MonitoringSettings).filter(
            MonitoringSettings.id == "default"
        ).first()
        if not settings:
            # Create default settings row if it doesn't exist
            defaults = cls._get_default_settings()
            settings = MonitoringSettings(id="default", **defaults)
            db.add(settings)
            db.commit()
            db.refresh(settings)

        # 5. Generate fresh scenarios for this simulation run
        scenarios = ScenarioGenerator.generate_scenarios(
            agent_id=agent_id,
            system_prompt=agent.system_prompt,
            tools=agent.tools,
            count=count
        )

        # 6. Simulate executions and analyze
        sessions_created = []
        for sc in scenarios:
            # Determine metadata versions: Model updates are simulated in "drift" profile
            if profile == "drift":
                model_ver = "agent-model-v2"
                prompt_ver = "v2"
            else:
                model_ver = "agent-model-v1"
                prompt_ver = "v1"

            # Execute simulation
            trace = AgentSimulator.simulate_execution(agent_id, sc, profile=profile)

            # Match scenario intent to clustered baseline if possible, else fallback to global
            session_intent = trace["intent"]
            fp_to_compare = fingerprint_map.get(session_intent, global_fp)

            # Score behavioral deviation
            anomaly_score, reasons = BehaviorAnalyzer.calculate_anomaly_score(
                trace=trace,
                baseline_fp=fp_to_compare,
                settings=settings
            )

            # Classify severity
            if anomaly_score < settings.warning_threshold:
                severity = "NORMAL"
            elif anomaly_score < settings.alert_threshold:
                severity = "WARNING"
            else:
                severity = "ALERT"

            # Create production session model
            session_id = f"PROD-{uuid.uuid4().hex[:6].upper()}"
            db_session = ProductionSession(
                session_id=session_id,
                agent_id=agent_id,
                timestamp=datetime.utcnow(),
                user_request=sc["user_request"],
                intent=session_intent,
                tool_calls=trace["tool_calls"],
                tool_sequence=trace["tool_sequence"],
                response_length=trace["response_length"],
                latency_ms=trace["latency_ms"],
                data_access=trace["data_access"],
                success=trace["success"],
                error_count=trace["error_count"],
                model_version=model_ver,
                prompt_version=prompt_ver,
                anomaly_score=anomaly_score,
                severity=severity,
                explanation="; ".join(reasons)
            )
            db.add(db_session)
            sessions_created.append(db_session)

            # Log persistent alerts for warnings & alerts
            if severity in ["WARNING", "ALERT"]:
                alert_id = f"evt_{uuid.uuid4().hex[:8]}"
                db_alert = AnomalyEvent(
                    event_id=alert_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    timestamp=datetime.utcnow(),
                    severity=severity,
                    anomaly_score=anomaly_score,
                    reasons=reasons,
                    baseline_version=active_baseline.version,
                    model_version=model_ver,
                    prompt_version=prompt_ver,
                    status="OPEN"
                )
                db.add(db_alert)

        db.commit()
        
        # Refresh session attributes
        for s in sessions_created:
            db.refresh(s)

        return sessions_created
