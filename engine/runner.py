import asyncio
import time
from typing import List, Dict

class BenchmarkRunner:
    def __init__(self, agent, evaluator, judge, trajectory_evaluator=None):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge
        self.trajectory_evaluator = trajectory_evaluator

    async def run_single_test(self, test_case: Dict) -> Dict:
        start_time = time.perf_counter()
        
        # 1. Gọi Agent
        response = await self.agent.query(test_case["question"])
        latency = time.perf_counter() - start_time
        
        # 2. Chạy RAGAS metrics
        ragas_scores = await self.evaluator.score(test_case, response)
        
        # 3. Chạy Multi-Judge
        judge_result = await self.judge.evaluate_multi_judge(
            test_case["question"], 
            response["answer"], 
            test_case["expected_answer"]
        )
        trajectory_scores = (
            self.trajectory_evaluator.score(response)
            if self.trajectory_evaluator is not None
            else {}
        )
        
        return {
            "id": test_case.get("id"),
            "test_case": test_case["question"],
            "case_type": test_case.get("metadata", {}).get("type"),
            "difficulty": test_case.get("metadata", {}).get("difficulty"),
            "expected_retrieval_ids": test_case.get("expected_retrieval_ids", []),
            "retrieved_ids": response.get("retrieved_ids", []),
            "agent_response": response["answer"],
            "latency": latency,
            "token_usage": response.get("metadata", {}).get("tokens_used", 0),
            "trace": response.get("trace", []),
            "trajectory": trajectory_scores,
            "ragas": ragas_scores,
            "judge": judge_result,
            "status": "fail" if judge_result["final_score"] < 3 else "pass"
        }

    async def run_all(self, dataset: List[Dict], batch_size: int = 5) -> List[Dict]:
        """
        Chạy song song bằng asyncio.gather với giới hạn batch_size để không bị Rate Limit.
        """
        results = []
        for i in range(0, len(dataset), batch_size):
            batch = dataset[i:i + batch_size]
            tasks = [self.run_single_test(case) for case in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
        return results
