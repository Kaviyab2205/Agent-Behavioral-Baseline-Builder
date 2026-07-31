import math
from typing import List, Dict, Any

def calculate_mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)

def calculate_std_dev(values: List[float]) -> float:
    if len(values) <= 1:
        return 0.0
    avg = calculate_mean(values)
    variance = sum((x - avg) ** 2 for x in values) / len(values)  # population standard deviation
    return math.sqrt(variance)

def calculate_frequency(items: List[Any]) -> Dict[str, float]:
    """
    Calculates the relative frequency of items.
    Returns a dictionary mapping stringified item to its proportion (0.0 to 1.0).
    """
    if not items:
        return {}
    counts = {}
    for item in items:
        key = str(item)
        counts[key] = counts.get(key, 0) + 1
    total = len(items)
    return {k: v / total for k, v in counts.items()}

def calculate_sequence_patterns(sequences_list: List[List[str]]) -> Dict[str, float]:
    """
    Given a list of tool call lists (e.g. [['search', 'get'], ['search']]),
    calculates the distribution of sequence transitions.
    For ['A', 'B', 'C'], transitions are "A -> B" and "B -> C".
    """
    transitions = []
    for seq in sequences_list:
        if len(seq) > 1:
            for i in range(len(seq) - 1):
                transitions.append(f"{seq[i]} -> {seq[i+1]}")
        elif len(seq) == 1:
            # Optionally record single tool call as self-transition or special pattern
            transitions.append(f"{seq[0]} -> [END]")
            
    if not transitions:
        return {}
        
    return calculate_frequency(transitions)

def get_stats_summary(values: List[float]) -> Dict[str, float]:
    """
    Helper to calculate avg, min, max, std_dev for a list of numbers.
    """
    if not values:
        return {"avg": 0.0, "min": 0.0, "max": 0.0, "std_dev": 0.0}
    return {
        "avg": calculate_mean(values),
        "min": float(min(values)),
        "max": float(max(values)),
        "std_dev": calculate_std_dev(values)
    }
