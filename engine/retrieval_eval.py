import re
from typing import Dict, List, Set

class RetrievalEvaluator:
    def __init__(self):
        pass

    def calculate_hit_rate(self, expected_ids: List[str], retrieved_ids: List[str], top_k: int = 3) -> float:
        """
        TODO: Tính toán xem ít nhất 1 trong expected_ids có nằm trong top_k của retrieved_ids không.
        """
        top_retrieved = retrieved_ids[:top_k]
        hit = any(doc_id in top_retrieved for doc_id in expected_ids)
        return 1.0 if hit else 0.0

    def calculate_mrr(self, expected_ids: List[str], retrieved_ids: List[str]) -> float:
        """
        TODO: Tính Mean Reciprocal Rank.
        Tìm vị trí đầu tiên của một expected_id trong retrieved_ids.
        MRR = 1 / position (vị trí 1-indexed). Nếu không thấy thì là 0.
        """
        for i, doc_id in enumerate(retrieved_ids):
            if doc_id in expected_ids:
                return 1.0 / (i + 1)
        return 0.0

    async def evaluate_batch(self, dataset: List[Dict]) -> Dict:
        """
        Chạy eval cho toàn bộ bộ dữ liệu.
        Dataset cần có trường 'expected_retrieval_ids' và Agent trả về 'retrieved_ids'.
        """
        # Placeholder logic
        return {"avg_hit_rate": 0.85, "avg_mrr": 0.72}


class ExpertEvaluator:
    def __init__(self, top_k: int = 3):
        self.top_k = top_k
        self.retrieval = RetrievalEvaluator()

    def _tokens(self, text: str) -> Set[str]:
        return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))

    def _overlap_score(self, source: str, target: str) -> float:
        source_tokens = self._tokens(source)
        target_tokens = self._tokens(target)
        if not source_tokens:
            return 0.0
        return len(source_tokens & target_tokens) / len(source_tokens)

    async def score(self, case: Dict, response: Dict) -> Dict:
        expected_ids = case.get("expected_retrieval_ids", [])
        retrieved_ids = response.get("retrieved_ids") or response.get("metadata", {}).get("sources", [])
        answer = response.get("answer", "")
        contexts = "\n".join(response.get("contexts", []))

        hit_rate = self.retrieval.calculate_hit_rate(expected_ids, retrieved_ids, self.top_k)
        mrr = self.retrieval.calculate_mrr(expected_ids, retrieved_ids)

        faithfulness = self._overlap_score(answer, contexts)
        relevancy = self._overlap_score(case.get("question", ""), answer)
        completeness = self._overlap_score(case.get("expected_answer", ""), answer)

        return {
            "faithfulness": round(min(faithfulness, 1.0), 3),
            "relevancy": round(min(relevancy, 1.0), 3),
            "completeness": round(min(completeness, 1.0), 3),
            "retrieval": {
                "hit_rate": hit_rate,
                "mrr": round(mrr, 3),
                "expected_ids": expected_ids,
                "retrieved_ids": retrieved_ids,
                "top_k": self.top_k,
            },
        }
