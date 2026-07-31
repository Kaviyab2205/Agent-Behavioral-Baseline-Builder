import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models import Agent, Scenario, ExecutionTrace, Baseline, BaselineFingerprint
from backend.services.agent_simulator import AgentSimulator
from backend.services.behavior_analyzer import BehaviorAnalyzer

class BaselineRecorder:
    @staticmethod
    def create_baseline(db: Session, agent_id: str) -> Baseline:
        # 1. Fetch agent
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise ValueError(f"Agent with ID {agent_id} not found.")

        # 2. Fetch scenarios
        scenarios = db.query(Scenario).filter(Scenario.agent_id == agent_id).all()
        if not scenarios:
            raise ValueError("Baseline creation failed: No scenarios found for this agent. Generate scenarios first.")

        # 3. Simulate execution for all scenarios under "normal" profile
        traces_data = []
        db_traces = []
        for sc in scenarios:
            # Convert scenario model to dict for simulator
            sc_dict = {
                "id": sc.id,
                "intent": sc.intent,
                "expected_tool_calls": sc.expected_tool_calls,
                "data_sensitivity": sc.data_sensitivity,
                "difficulty": sc.difficulty
            }
            trace_dict = AgentSimulator.simulate_execution(agent_id, sc_dict, profile="normal")
            traces_data.append(trace_dict)

            # Map to DB model
            db_trace = ExecutionTrace(
                session_id=trace_dict["session_id"],
                agent_id=trace_dict["agent_id"],
                scenario_id=trace_dict["scenario_id"],
                intent=trace_dict["intent"],
                timestamp=trace_dict["timestamp"],
                tool_calls=trace_dict["tool_calls"],
                tool_sequence=trace_dict["tool_sequence"],
                tool_count=trace_dict["tool_count"],
                response_length=trace_dict["response_length"],
                latency_ms=trace_dict["latency_ms"],
                data_access=trace_dict["data_access"],
                success=trace_dict["success"],
                error_count=trace_dict["error_count"],
                profile=trace_dict["profile"]
            )
            db.add(db_trace)
            db_traces.append(db_trace)

        # Commit traces so they are written
        db.commit()

        # 4. Calculate behavioral fingerprint
        fingerprint_data = BehaviorAnalyzer.calculate_fingerprint(traces_data)

        # 5. Determine baseline version (incrementing version count)
        existing_baseline_count = db.query(Baseline).filter(Baseline.agent_id == agent_id).count()
        new_version = f"v{existing_baseline_count + 1}"

        # 6. Deactivate all existing baselines for this agent
        db.query(Baseline).filter(
            Baseline.agent_id == agent_id,
            Baseline.status == "active"
        ).update({"status": "inactive"})
        db.commit()

        # 7. Create Baseline & BaselineFingerprint
        baseline_id = f"bl_{uuid.uuid4().hex[:8]}"
        new_baseline = Baseline(
            id=baseline_id,
            agent_id=agent_id,
            agent_version=agent.version,
            scenario_count=len(scenarios),
            created_at=datetime.utcnow(),
            status="active",
            version=new_version
        )
        db.add(new_baseline)
        db.commit()

        db_fingerprint = BaselineFingerprint(
            baseline_id=baseline_id,
            intent=None,  # None stands for the global baseline
            tool_frequency=fingerprint_data["tool_frequency"],
            avg_response_length=fingerprint_data["avg_response_length"],
            response_length_stats=fingerprint_data["response_length_stats"],
            tool_sequence_patterns=fingerprint_data["tool_sequence_patterns"],
            tool_count_stats=fingerprint_data["tool_count_stats"],
            data_access_patterns=fingerprint_data["data_access_patterns"],
            intent_distribution=fingerprint_data["intent_distribution"],
            latency_stats=fingerprint_data["latency_stats"],
            error_rate=fingerprint_data["error_rate"],
            success_rate=fingerprint_data["success_rate"]
        )
        db.add(db_fingerprint)
        db.commit()

        # 8. Create Intent-based clustered fingerprints (Bonus feature)
        for intent_cat in ["Information Retrieval", "Data Modification", "Communication"]:
            intent_traces = [t for t in traces_data if t["intent"] == intent_cat]
            if intent_traces:
                intent_fp_data = BehaviorAnalyzer.calculate_fingerprint(intent_traces)
                db_intent_fp = BaselineFingerprint(
                    baseline_id=baseline_id,
                    intent=intent_cat,
                    tool_frequency=intent_fp_data["tool_frequency"],
                    avg_response_length=intent_fp_data["avg_response_length"],
                    response_length_stats=intent_fp_data["response_length_stats"],
                    tool_sequence_patterns=intent_fp_data["tool_sequence_patterns"],
                    tool_count_stats=intent_fp_data["tool_count_stats"],
                    data_access_patterns=intent_fp_data["data_access_patterns"],
                    intent_distribution=intent_fp_data["intent_distribution"],
                    latency_stats=intent_fp_data["latency_stats"],
                    error_rate=intent_fp_data["error_rate"],
                    success_rate=intent_fp_data["success_rate"]
                )
                db.add(db_intent_fp)
        db.commit()

        db.refresh(new_baseline)
        return new_baseline
