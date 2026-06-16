import asyncio
import json
import os
import time
from engine.runner import BenchmarkRunner
from engine.retrieval_eval import ExpertEvaluator
from engine.llm_judge import LLMJudge
from engine.trajectory_eval import TrajectoryEvaluator
from agent.main_agent import MainAgent

QUALITY_THRESHOLD = 3.5
HIT_RATE_THRESHOLD = 0.9
AGREEMENT_THRESHOLD = 0.75
MAX_AVG_LATENCY = 0.2
MAX_ESTIMATED_COST_USD = 0.01
MIN_TRAJECTORY_EFFICIENCY = 0.85
MAX_LOOP_RATE = 0.0


async def run_benchmark_with_results(
    agent_version: str,
    optimized_agent: bool = False,
    workflow_aware: bool = False,
    trace_enabled: bool = True,
):
    print(f"🚀 Khởi động Benchmark cho {agent_version}...")

    if not os.path.exists("data/golden_set.jsonl"):
        print("❌ Thiếu data/golden_set.jsonl. Hãy chạy 'python data/synthetic_gen.py' trước.")
        return None, None

    with open("data/golden_set.jsonl", "r", encoding="utf-8") as f:
        dataset = [json.loads(line) for line in f if line.strip()]

    if not dataset:
        print("❌ File data/golden_set.jsonl rỗng. Hãy tạo ít nhất 1 test case.")
        return None, None

    runner = BenchmarkRunner(
        MainAgent(optimized=optimized_agent, workflow_aware=workflow_aware, trace_enabled=trace_enabled),
        ExpertEvaluator(top_k=3),
        LLMJudge(),
        TrajectoryEvaluator() if trace_enabled or workflow_aware else None,
    )
    results = await runner.run_all(dataset)

    total = len(results)
    avg_latency = sum(r["latency"] for r in results) / total
    total_tokens = sum(r.get("token_usage", 0) for r in results)
    avg_mrr = sum(r["ragas"]["retrieval"]["mrr"] for r in results) / total
    avg_faithfulness = sum(r["ragas"]["faithfulness"] for r in results) / total
    avg_relevancy = sum(r["ragas"]["relevancy"] for r in results) / total
    pass_rate = sum(1 for r in results if r["status"] == "pass") / total
    trajectory_results = [r.get("trajectory", {}) for r in results if r.get("trajectory")]
    if trajectory_results:
        avg_trajectory_efficiency = sum(r["trajectory_efficiency_score"] for r in trajectory_results) / len(trajectory_results)
        avg_step_count = sum(r["step_count"] for r in trajectory_results) / len(trajectory_results)
        avg_tool_call_count = sum(r["tool_call_count"] for r in trajectory_results) / len(trajectory_results)
        avg_redundant_tool_rate = sum(r["redundant_tool_call_rate"] for r in trajectory_results) / len(trajectory_results)
        loop_rate = sum(1 for r in trajectory_results if r["loop_detected"]) / len(trajectory_results)
    else:
        avg_trajectory_efficiency = None
        avg_step_count = None
        avg_tool_call_count = None
        avg_redundant_tool_rate = None
        loop_rate = None
    summary = {
        "metadata": {"version": agent_version, "total": total, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")},
        "metrics": {
            "avg_score": sum(r["judge"]["final_score"] for r in results) / total,
            "hit_rate": sum(r["ragas"]["retrieval"]["hit_rate"] for r in results) / total,
            "mrr": avg_mrr,
            "faithfulness": avg_faithfulness,
            "relevancy": avg_relevancy,
            "agreement_rate": sum(r["judge"]["agreement_rate"] for r in results) / total,
            "pass_rate": pass_rate,
            "avg_latency": avg_latency,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round((total_tokens / 1_000_000) * 0.15, 6),
            "avg_trajectory_efficiency": avg_trajectory_efficiency,
            "avg_step_count": avg_step_count,
            "avg_tool_call_count": avg_tool_call_count,
            "avg_redundant_tool_call_rate": avg_redundant_tool_rate,
            "loop_rate": loop_rate,
        }
    }
    return results, summary

async def run_benchmark(version, optimized_agent: bool = False, workflow_aware: bool = False, trace_enabled: bool = True):
    _, summary = await run_benchmark_with_results(version, optimized_agent, workflow_aware, trace_enabled)
    return summary


def evaluate_release_gate(baseline_summary, candidate_summary):
    metrics = candidate_summary["metrics"]
    delta = metrics["avg_score"] - baseline_summary["metrics"]["avg_score"]
    checks = {
        "quality_not_regressed": delta >= 0,
        "quality_threshold": metrics["avg_score"] >= QUALITY_THRESHOLD,
        "retrieval_threshold": metrics["hit_rate"] >= HIT_RATE_THRESHOLD,
        "agreement_threshold": metrics["agreement_rate"] >= AGREEMENT_THRESHOLD,
        "latency_threshold": metrics["avg_latency"] <= MAX_AVG_LATENCY,
        "cost_threshold": metrics["estimated_cost_usd"] <= MAX_ESTIMATED_COST_USD,
    }
    if metrics.get("avg_trajectory_efficiency") is not None:
        checks["trajectory_efficiency_threshold"] = metrics["avg_trajectory_efficiency"] >= MIN_TRAJECTORY_EFFICIENCY
    if metrics.get("loop_rate") is not None:
        checks["loop_rate_threshold"] = metrics["loop_rate"] <= MAX_LOOP_RATE
    decision = "RELEASE" if all(checks.values()) else "ROLLBACK"
    return {
        "decision": decision,
        "delta_avg_score": delta,
        "thresholds": {
            "quality": QUALITY_THRESHOLD,
            "hit_rate": HIT_RATE_THRESHOLD,
            "agreement_rate": AGREEMENT_THRESHOLD,
            "max_avg_latency": MAX_AVG_LATENCY,
            "max_estimated_cost_usd": MAX_ESTIMATED_COST_USD,
            "min_trajectory_efficiency": MIN_TRAJECTORY_EFFICIENCY,
            "max_loop_rate": MAX_LOOP_RATE,
        },
        "checks": checks,
    }

async def main():
    v1_summary = await run_benchmark("Agent_V1_Base", optimized_agent=False)
    v2_summary = await run_benchmark("Agent_V2_Optimized", optimized_agent=True)
    v3_results, v3_summary = await run_benchmark_with_results(
        "Agent_V3_TrajectoryAware",
        optimized_agent=True,
        workflow_aware=True,
    )
    
    if not v1_summary or not v2_summary or not v3_summary:
        print("❌ Không thể chạy Benchmark. Kiểm tra lại data/golden_set.jsonl.")
        return

    print("\n📊 --- KẾT QUẢ SO SÁNH (REGRESSION) ---")
    delta_v2 = v2_summary["metrics"]["avg_score"] - v1_summary["metrics"]["avg_score"]
    delta_v3 = v3_summary["metrics"]["avg_score"] - v1_summary["metrics"]["avg_score"]
    print(f"V1 Score: {v1_summary['metrics']['avg_score']}")
    print(f"V2 Score: {v2_summary['metrics']['avg_score']}")
    print(f"V3 Score: {v3_summary['metrics']['avg_score']}")
    print(f"Delta V2: {'+' if delta_v2 >= 0 else ''}{delta_v2:.2f}")
    print(f"Delta V3: {'+' if delta_v3 >= 0 else ''}{delta_v3:.2f}")

    release_gate = evaluate_release_gate(v1_summary, v3_summary)
    v3_summary["release_gate"] = release_gate
    v3_summary["regression_comparison"] = {
        "baseline": v1_summary,
        "previous_candidate": v2_summary,
        "candidate": "Agent_V3_TrajectoryAware",
    }

    os.makedirs("reports", exist_ok=True)
    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(v3_summary, f, ensure_ascii=False, indent=2)
    with open("reports/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(v3_results, f, ensure_ascii=False, indent=2)

    if release_gate["decision"] == "RELEASE":
        print("✅ QUYẾT ĐỊNH: RELEASE")
    else:
        print("❌ QUYẾT ĐỊNH: ROLLBACK / BLOCK RELEASE")
        print(f"Gate checks: {release_gate['checks']}")

if __name__ == "__main__":
    asyncio.run(main())
