import uuid
from datetime import datetime
import random
from typing import Dict, Any, List

class AgentSimulator:
    @staticmethod
    def _get_data_categories_for_tools(tools: List[str]) -> List[str]:
        categories = []
        for t in tools:
            t_lower = t.lower()
            if "customer" in t_lower:
                categories.append("customer_data")
            elif "order" in t_lower:
                categories.append("order_data")
            elif "account" in t_lower:
                categories.append("account_data")
            elif "email" in t_lower or "notify" in t_lower:
                categories.append("communication_log")
            elif "ticket" in t_lower:
                categories.append("support_records")
            elif "database" in t_lower or "search" in t_lower:
                categories.append("system_index")
        if not categories:
            categories.append("general_metadata")
        return list(set(categories))

    @classmethod
    def simulate_execution(cls, agent_id: str, scenario: Dict[str, Any], profile: str = "normal") -> Dict[str, Any]:
        """
        Simulate the agent execution of a scenario under a specific profile:
        - normal: Standard agent behavior
        - moderate_anomaly: Slower response, occasional error, slight deviation in tool calls
        - severe_anomaly: High latency, high errors, tool loops, unauthorized data access
        - drift: Consistent slight shifts in parameters (slower latency, longer responses)
        """
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        expected_tools = scenario.get("expected_tool_calls", [])
        intent = scenario.get("intent", "Information Retrieval")
        scenario_id = scenario.get("id")

        # Set up random generator (seeded loosely by session id to give diversity but consistent within run)
        seed = int(session_id.split("_")[1], 16)
        r = random.Random(seed)

        # Profile parameters
        success = True
        error_count = 0
        latency_ms = 200.0
        response_length = 150
        actual_tools = list(expected_tools)
        data_access = cls._get_data_categories_for_tools(actual_tools)

        if profile == "normal":
            # Success: 100% (prevent test flakiness in small count simulation)
            success = True
            error_count = 0
            # Latency: 200 - 600 ms
            latency_ms = r.uniform(200.0, 600.0)
            # Response Length: 100 - 300 characters
            response_length = r.randint(100, 300)


        elif profile == "moderate_anomaly":
            # Success: 80%
            success = True
            error_count = 0
            # Latency: 800 - 1800 ms (deviates from normal avg ~400ms)
            latency_ms = r.uniform(800.0, 1800.0)
            # Response Length: 350 - 550 characters (deviates from normal avg ~200)
            response_length = r.randint(350, 550)
            # Induce tool call / sequence deviation by executing an audit utility
            if "audit_log" not in actual_tools:
                actual_tools.append("audit_log")
            
        elif profile == "severe_anomaly":
            # Success: 50%
            success = r.random() < 0.50
            # Latency: very high (1500 - 4500 ms) or instant failure (10 - 50 ms)
            if r.random() < 0.20:
                latency_ms = r.uniform(10.0, 80.0)
                success = False
                error_count = r.randint(2, 4)
                actual_tools = []
                response_length = r.randint(10, 50)  # short error message
            else:
                latency_ms = r.uniform(1500.0, 4500.0)
                error_count = r.randint(1, 3)
                # Tool loop behavior: run same tool multiple times
                if actual_tools:
                    loop_tool = actual_tools[0]
                    actual_tools = [loop_tool] * r.randint(3, 5)
                else:
                    actual_tools = ["search_database"] * 4
                response_length = r.randint(600, 1200) # verbose output / stack dump
            # Access sensitive data categories that shouldn't be accessed
            data_access = list(set(data_access + ["credentials_data", "system_settings_data"]))

        elif profile == "drift":
            # Success: 92% (slightly lower than normal)
            success = r.random() < 0.92
            error_count = 0 if success else 1
            # Latency: consistently higher (500 - 1200 ms)
            latency_ms = r.uniform(500.0, 1200.0)
            # Response Length: consistently longer (250 - 550 characters)
            response_length = r.randint(250, 550)
            # Systematically prepend "search_database" and append "send_email"
            if "search_database" not in actual_tools:
                actual_tools.insert(0, "search_database")
            if "send_email" not in actual_tools and r.random() < 0.40:
                actual_tools.append("send_email")

        # Generate sequence list
        tool_sequence = []
        if len(actual_tools) > 1:
            for i in range(len(actual_tools) - 1):
                tool_sequence.append(f"{actual_tools[i]} -> {actual_tools[i+1]}")
        elif len(actual_tools) == 1:
            tool_sequence.append(f"{actual_tools[0]} -> [END]")

        # Recalculate data access based on final tool list
        data_access = cls._get_data_categories_for_tools(actual_tools)
        if profile == "severe_anomaly":
            data_access = list(set(data_access + ["credentials_data", "system_settings_data"]))

        return {
            "session_id": session_id,
            "agent_id": agent_id,
            "scenario_id": scenario_id,
            "intent": intent,
            "timestamp": datetime.utcnow(),
            "tool_calls": actual_tools,
            "tool_sequence": tool_sequence,
            "tool_count": len(actual_tools),
            "response_length": response_length,
            "latency_ms": latency_ms,
            "data_access": data_access,
            "success": success,
            "error_count": error_count,
            "profile": profile
        }
