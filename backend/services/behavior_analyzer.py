from typing import List, Dict, Any
from backend.utils.statistics import get_stats_summary, calculate_frequency, calculate_sequence_patterns

class BehaviorAnalyzer:
    @classmethod
    def calculate_fingerprint(cls, traces: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates the behavioral fingerprint of an agent based on execution traces.
        """
        if not traces:
            return {
                "tool_frequency": {},
                "avg_response_length": 0.0,
                "response_length_stats": {"avg": 0.0, "min": 0.0, "max": 0.0, "std_dev": 0.0},
                "tool_sequence_patterns": {},
                "tool_count_stats": {"avg": 0.0, "min": 0.0, "max": 0.0, "std_dev": 0.0},
                "data_access_patterns": {},
                "intent_distribution": {},
                "latency_stats": {"avg": 0.0, "min": 0.0, "max": 0.0, "std_dev": 0.0},
                "error_rate": 0.0,
                "success_rate": 0.0
            }

        # Extracted metrics arrays
        all_tool_calls = []
        all_tool_sequences = []
        tool_counts = []
        response_lengths = []
        latencies = []
        all_data_access = []
        intents = []
        error_counts = []
        success_flags = []

        for trace in traces:
            # Tool calls
            calls = trace.get("tool_calls", [])
            all_tool_calls.extend(calls)
            all_tool_sequences.append(calls)
            tool_counts.append(len(calls))

            # Response length & latency
            response_lengths.append(float(trace.get("response_length", 0)))
            latencies.append(float(trace.get("latency_ms", 0.0)))

            # Data accessed
            all_data_access.extend(trace.get("data_access", []))

            # Intent, error count, and success status
            intents.append(trace.get("intent"))
            error_counts.append(float(trace.get("error_count", 0)))
            success_flags.append(1.0 if trace.get("success", False) else 0.0)

        # Calculators
        tool_freq = calculate_frequency(all_tool_calls)
        resp_stats = get_stats_summary(response_lengths)
        tool_seq_freq = calculate_sequence_patterns(all_tool_sequences)
        tool_count_stats = get_stats_summary(tool_counts)
        data_access_freq = calculate_frequency(all_data_access)
        intent_freq = calculate_frequency(intents)
        latency_stats = get_stats_summary(latencies)
        
        # Rates
        avg_error_rate = sum(error_counts) / len(traces)
        avg_success_rate = sum(success_flags) / len(traces)

        return {
            "tool_frequency": tool_freq,
            "avg_response_length": resp_stats["avg"],
            "response_length_stats": resp_stats,
            "tool_sequence_patterns": tool_seq_freq,
            "tool_count_stats": tool_count_stats,
            "data_access_patterns": data_access_freq,
            "intent_distribution": intent_freq,
            "latency_stats": latency_stats,
            "error_rate": avg_error_rate,
            "success_rate": avg_success_rate
        }

    @classmethod
    def calculate_anomaly_score(
        cls, 
        trace: Dict[str, Any], 
        baseline_fp: Dict[str, Any], 
        settings: Any
    ) -> tuple[float, List[str]]:
        """
        Compares a single execution trace against the baseline fingerprint.
        Returns a tuple of (anomaly_score_0_to_100, list_of_reasons_explanations).
        """
        reasons = []
        deviations = {}
        
        # 1. Tool Call Frequency Deviation
        tool_calls = trace.get("tool_calls", [])
        base_tools = baseline_fp.get("tool_frequency", {})
        if tool_calls:
            tool_devs = []
            for t in set(tool_calls):
                freq = base_tools.get(t, 0.0)
                if freq < 0.02:  # Allow minor threshold
                    reasons.append(f"Unexpected tool execution: '{t}' (rare or absent in baseline)")
                    tool_devs.append(1.0)
                else:
                    tool_devs.append(0.0)
            deviations["tool_frequency"] = sum(tool_devs) / len(tool_devs)
        else:
            base_avg_tools = baseline_fp.get("tool_count_stats", {}).get("avg", 0.0)
            if base_avg_tools > 0.5:
                reasons.append(f"No tools executed (baseline average: {base_avg_tools:.2f} calls)")
                deviations["tool_frequency"] = 1.0
            else:
                deviations["tool_frequency"] = 0.0

        # 2. Sequence Deviation
        tool_seq = trace.get("tool_sequence", [])
        base_seq = baseline_fp.get("tool_sequence_patterns", {})
        if tool_seq:
            seq_devs = []
            for seq in tool_seq:
                freq = base_seq.get(seq, 0.0)
                if freq < 0.02:
                    reasons.append(f"Unexpected tool sequence transition: '{seq}' (rare or absent in baseline)")
                    seq_devs.append(1.0)
                else:
                    seq_devs.append(0.0)
            deviations["sequence"] = sum(seq_devs) / len(seq_devs)
        else:
            if len(tool_calls) > 1:
                deviations["sequence"] = 1.0
                reasons.append("Missing transition sequences for multi-tool execution")
            else:
                deviations["sequence"] = 0.0

        # 3. Response Length Deviation (Z-score mapping)
        resp_len = float(trace.get("response_length", 0))
        len_stats = baseline_fp.get("response_length_stats", {})
        base_len_avg = len_stats.get("avg", 0.0)
        base_len_std = len_stats.get("std_dev", 0.0)
        
        if base_len_std > 0:
            z_len = abs(resp_len - base_len_avg) / base_len_std
            # Z-score of 3.0 or more is a heavy deviation (1.0). Scale z/3.0.
            dev_len = min(1.0, z_len / 3.0)
            if z_len > 2.0:
                reasons.append(f"Response length ({int(resp_len)} chars) differs significantly from baseline avg ({base_len_avg:.1f} chars, std dev: {base_len_std:.1f})")
        else:
            diff = abs(resp_len - base_len_avg)
            dev_len = min(1.0, diff / max(1.0, base_len_avg))
            if diff > 50.0:
                reasons.append(f"Response length ({int(resp_len)} chars) differs from baseline average ({base_len_avg:.1f} chars)")
        deviations["response_length"] = dev_len

        # 4. Latency Deviation
        latency = float(trace.get("latency_ms", 0.0))
        lat_stats = baseline_fp.get("latency_stats", {})
        base_lat_avg = lat_stats.get("avg", 0.0)
        base_lat_std = lat_stats.get("std_dev", 0.0)
        
        if base_lat_std > 0:
            z_lat = abs(latency - base_lat_avg) / base_lat_std
            dev_lat = min(1.0, z_lat / 3.0)
            if z_lat > 2.0:
                reasons.append(f"Latency ({latency:.1f}ms) is anomalous compared to baseline avg ({base_lat_avg:.1f}ms, std dev: {base_lat_std:.1f}ms)")
        else:
            diff = abs(latency - base_lat_avg)
            dev_lat = min(1.0, diff / max(1.0, base_lat_avg))
            if diff > 200.0:
                reasons.append(f"Latency ({latency:.1f}ms) differs from baseline average ({base_lat_avg:.1f}ms)")
        deviations["latency"] = dev_lat

        # 5. Data Access Deviation
        data_access = trace.get("data_access", [])
        base_data = baseline_fp.get("data_access_patterns", {})
        if data_access:
            data_devs = []
            for d in data_access:
                freq = base_data.get(d, 0.0)
                if freq < 0.02:
                    reasons.append(f"Unauthorized data access category: '{d}' (rare or absent in baseline)")
                    data_devs.append(1.0)
                else:
                    data_devs.append(0.0)
            deviations["data_access"] = max(data_devs) if data_devs else 0.0
        else:
            deviations["data_access"] = 0.0

        # 6. Intent Deviation
        intent = trace.get("intent")
        base_intents = baseline_fp.get("intent_distribution", {})
        if intent:
            freq = base_intents.get(intent, 0.0)
            if freq < 0.02:
                reasons.append(f"Session intent '{intent}' not exercised in baseline")
                deviations["intent"] = 1.0
            else:
                deviations["intent"] = 0.0
        else:
            deviations["intent"] = 0.0

        # 7. Error Rate & Success Deviation
        success = trace.get("success", True)
        error_count = trace.get("error_count", 0)
        
        err_dev = 0.0
        if not success:
            reasons.append("Session execution reported Failure (success=False)")
            err_dev = 1.0
        elif error_count > 0:
            reasons.append(f"Session encountered {error_count} execution errors")
            err_dev = min(1.0, error_count * 0.5)
        deviations["error_rate"] = err_dev

        # Compute weighted score
        try:
            w_tool = getattr(settings, "tool_frequency_weight", 1.0)
            w_seq = getattr(settings, "sequence_weight", 1.0)
            w_len = getattr(settings, "response_length_weight", 1.0)
            w_data = getattr(settings, "data_access_weight", 1.5)
            w_intent = getattr(settings, "intent_weight", 0.5)
            w_lat = getattr(settings, "latency_weight", 0.8)
            w_err = getattr(settings, "error_rate_weight", 2.0)
        except AttributeError:
            w_tool = settings.get("tool_frequency_weight", 1.0)
            w_seq = settings.get("sequence_weight", 1.0)
            w_len = settings.get("response_length_weight", 1.0)
            w_data = settings.get("data_access_weight", 1.5)
            w_intent = settings.get("intent_weight", 0.5)
            w_lat = settings.get("latency_weight", 0.8)
            w_err = settings.get("error_rate_weight", 2.0)

        total_weight = w_tool + w_seq + w_len + w_data + w_intent + w_lat + w_err
        if total_weight <= 0:
            total_weight = 1.0

        weighted_deviation = (
            (deviations["tool_frequency"] * w_tool) +
            (deviations["sequence"] * w_seq) +
            (deviations["response_length"] * w_len) +
            (deviations["data_access"] * w_data) +
            (deviations["intent"] * w_intent) +
            (deviations["latency"] * w_lat) +
            (deviations["error_rate"] * w_err)
        )
        
        raw_score = (weighted_deviation / total_weight) * 100.0
        anomaly_score = min(100.0, max(0.0, raw_score))
        
        if not reasons:
            reasons.append("Behavior conforms to normal baseline patterns.")
            
        return anomaly_score, reasons
