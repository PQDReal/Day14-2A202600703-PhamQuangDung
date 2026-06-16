from collections import Counter
from typing import Dict, List, Tuple


class TrajectoryEvaluator:
    def _tool_signature(self, step: Dict) -> Tuple[str, str]:
        return (str(step.get("tool", step.get("name", ""))), str(step.get("query", step.get("input", ""))))

    def score(self, response: Dict) -> Dict:
        trace: List[Dict] = response.get("trace", [])
        step_count = len(trace)
        tool_steps = [step for step in trace if step.get("type") == "tool"]
        tool_call_count = len(tool_steps)
        unique_tool_count = len({step.get("tool", step.get("name")) for step in tool_steps})

        signatures = [self._tool_signature(step) for step in tool_steps]
        signature_counts = Counter(signatures)
        repeated_tool_calls = sum(count - 1 for count in signature_counts.values() if count > 1)
        redundant_tool_call_rate = repeated_tool_calls / tool_call_count if tool_call_count else 0.0

        retry_count = sum(1 for step in trace if "retry" in str(step.get("name", "")).lower())
        backtrack_count = sum(1 for step in trace if "backtrack" in str(step.get("name", "")).lower())
        loop_detected = any(count >= 3 for count in signature_counts.values())

        total_trace_ms = sum(float(step.get("elapsed_ms", 0.0)) for step in trace)
        first_tool_index = next((i for i, step in enumerate(trace, start=1) if step.get("type") == "tool"), None)

        penalty = 0.0
        penalty += max(0, step_count - 6) * 0.05
        penalty += redundant_tool_call_rate * 0.35
        penalty += retry_count * 0.1
        penalty += backtrack_count * 0.1
        penalty += 0.25 if loop_detected else 0.0
        trajectory_efficiency_score = max(0.0, min(1.0, 1.0 - penalty))

        return {
            "step_count": step_count,
            "tool_call_count": tool_call_count,
            "unique_tool_count": unique_tool_count,
            "redundant_tool_call_rate": round(redundant_tool_call_rate, 3),
            "retry_count": retry_count,
            "backtrack_count": backtrack_count,
            "loop_detected": loop_detected,
            "time_to_first_tool_step": first_tool_index,
            "trace_elapsed_ms": round(total_trace_ms, 3),
            "trajectory_efficiency_score": round(trajectory_efficiency_score, 3),
        }
