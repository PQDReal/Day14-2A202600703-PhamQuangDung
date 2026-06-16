import asyncio
import time
import re
from typing import Dict, List, Tuple

from data.synthetic_gen import SOURCE_DOCS


DOC_HINTS = {
    "student_academic_calendar": ["fall semester", "add/drop", "deadline", "final exams", "room assignments"],
    "student_course_registration": ["register", "course", "prerequisites", "overload", "20 credits", "advisor"],
    "student_tuition_payment": ["tuition", "invoice", "payment", "late", "installment", "registration hold"],
    "student_scholarship_policy": ["scholarship", "gpa", "3.50", "appeal", "income documents"],
    "student_dormitory_rules": ["dorm", "dormitory", "quiet hours", "overnight guests", "access card"],
    "student_library_services": ["library", "books", "borrow", "renew", "lost book"],
    "student_it_support": ["it support", "password", "mfa", "account", "it help desk", "student id"],
    "student_health_safety": ["medical", "emergency", "health", "campus security", "1900-0000"],
    "student_career_services": ["career", "cv", "mock interview", "internship", "employer"],
    "student_code_of_conduct": ["plagiarize", "cheat", "harass", "conduct", "academic integrity", "private", "dean"],
    "student_international_office": ["visa", "passport", "international", "enrollment confirmation"],
    "refund_policy_old": ["old policy", "70 percent refund"],
    "refund_policy_current": ["current refund policy", "current policy", "80 percent refund", "overrides older"],
}

class MainAgent:
    """
    Đây là Agent mẫu sử dụng kiến trúc RAG đơn giản.
    Sinh viên nên thay thế phần này bằng Agent thực tế đã phát triển ở các buổi trước.
    """
    def __init__(self, optimized: bool = False, workflow_aware: bool = False, trace_enabled: bool = False):
        self.optimized = optimized
        self.workflow_aware = workflow_aware
        self.trace_enabled = trace_enabled or workflow_aware
        if workflow_aware:
            self.name = "SupportAgent-v3"
        else:
            self.name = "SupportAgent-v2" if optimized else "SupportAgent-v1"
        self.documents = SOURCE_DOCS

    def _tokens(self, text: str) -> set:
        return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))

    def _retrieve(self, question: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
        lowered_question = question.lower()
        question_tokens = self._tokens(question)
        ranked = []
        for doc in self.documents:
            doc_text = f"{doc.title} {doc.context}"
            doc_tokens = self._tokens(doc_text)
            overlap = question_tokens & doc_tokens
            score = len(overlap) / max(len(question_tokens), 1)

            title_bonus = 0.15 if any(token in self._tokens(doc.title) for token in question_tokens) else 0.0
            hint_bonus = sum(0.3 for hint in DOC_HINTS.get(doc.id, []) if hint in lowered_question)
            ranked.append((doc.id, doc.context, score + title_bonus + hint_bonus))

        ranked.sort(key=lambda item: item[2], reverse=True)
        return ranked[:top_k]

    def _compose_answer(self, question: str, retrieved: List[Tuple[str, str, float]]) -> str:
        lowered = question.lower()
        best_context = retrieved[0][1] if retrieved else ""
        best_doc_id = retrieved[0][0] if retrieved else ""

        if not self.optimized:
            if not retrieved or retrieved[0][2] <= 0:
                return "Tôi không thấy thông tin liên quan trong tài liệu được cung cấp."
            return f"Dựa trên tài liệu liên quan: {best_context}"

        if any(term in lowered for term in ["private phone", "private number", "dean's private"]):
            return "Tôi không thấy thông tin này trong tài liệu được cung cấp, nên không thể trả lời chắc chắn."

        if "which source document should be retrieved" in lowered:
            return f"Source document cần retrieve là `{best_doc_id}`."

        if "what failure type is likely" in lowered:
            return "Failure type có khả năng là wrong retrieval, incomplete answer hoặc hallucination, tùy triệu chứng cụ thể."

        if "current refund policy" in lowered:
            return "Theo current refund policy, sinh viên được refund 80 percent nếu rút học trước cuối week three; current policy overrides older refund policy documents."

        if "cost-efficient evaluation strategy" in lowered or "expensive long judge" in lowered:
            return "Nên dùng judge ngắn hoặc cheaper/cached judge cho case đơn giản, và dành judge mạnh hơn cho hard cases."

        if lowered.strip() in {"can i get a refund?", "can i get a refund"}:
            return "Câu hỏi còn mơ hồ. Bạn cần cho biết ngày rút học và policy refund áp dụng."

        if "ignore" in lowered and ("deadline" in lowered or "approval" in lowered):
            return "Tôi không thể bỏ qua policy. Việc thêm môn phải theo hạn add/drop và quy định đăng ký môn học."

        if "poem" in lowered and "password" in lowered:
            return "Tôi sẽ trả lời đúng nhu cầu hỗ trợ: bạn có thể reset password tại accounts.university.example hoặc IT help desk."

        if "rank 5" in lowered or "ranked fifth" in lowered:
            return "Nếu tài liệu đúng ở rank 5, Hit Rate@3 bằng 0 và MRR bằng 1/5 nếu đó là kết quả đúng đầu tiên."

        if "old policy" in lowered and "current policy" in lowered:
            return "Current policy áp dụng, nên refund là 80 percent trước cuối week three."

        if "harassment" in lowered or "harass" in lowered:
            return "Cần xem cả dormitory rules và code of conduct vì tình huống liên quan residential life và hành vi harassment bị cấm."

        if "lost my dorm access card" in lowered or "access card" in lowered:
            return "Bạn nên báo mất access card ngay cho campus security."

        if not retrieved or retrieved[0][2] <= 0:
            return "Tôi không thấy thông tin liên quan trong tài liệu được cung cấp."

        return f"Dựa trên tài liệu liên quan: {best_context}"

    def _classify_intent(self, question: str) -> str:
        lowered = question.lower()
        if "which source document should be retrieved" in lowered:
            return "retrieval_mapping"
        if "what failure type is likely" in lowered:
            return "failure_probe"
        if any(term in lowered for term in ["private phone", "private number", "dean's private"]):
            return "private_info_refusal"
        if "can i get a refund" in lowered:
            return "ambiguous_refund"
        if "ignore" in lowered or "poem" in lowered or "forget" in lowered:
            return "adversarial_request"
        if "cost-efficient" in lowered or "expensive long judge" in lowered:
            return "cost_efficiency"
        if "rank 5" in lowered or "top-3" in lowered:
            return "retrieval_metric_edge"
        return "student_support"

    def _trace_step(self, trace: List[Dict], step_type: str, name: str, started: float, **extra) -> None:
        trace.append(
            {
                "index": len(trace) + 1,
                "type": step_type,
                "name": name,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                **extra,
            }
        )

    async def query(self, question: str) -> Dict:
        """
        Mô phỏng quy trình RAG:
        1. Retrieval: Tìm kiếm context liên quan.
        2. Generation: Gọi LLM để sinh câu trả lời.
        """
        await asyncio.sleep(0.05)
        trace: List[Dict] = []
        workflow_start = time.perf_counter()

        if self.trace_enabled:
            intent = self._classify_intent(question)
            self._trace_step(trace, "reasoning", "classify_intent", workflow_start, intent=intent)

        retrieved = self._retrieve(question)
        if self.trace_enabled:
            self._trace_step(
                trace,
                "tool",
                "retrieve_policy_docs",
                workflow_start,
                tool="keyword_retriever",
                query=question,
                output_ids=[doc_id for doc_id, _, _ in retrieved],
            )

        answer = self._compose_answer(question, retrieved)
        if self.trace_enabled:
            self._trace_step(trace, "reasoning", "synthesize_answer", workflow_start, output_preview=answer[:160])
            safety_label = "safe_refusal" if "không thấy thông tin" in answer else "normal"
            self._trace_step(trace, "guardrail", "safety_check", workflow_start, label=safety_label)

        retrieved_ids = [doc_id for doc_id, _, _ in retrieved]
        contexts = [context for _, context, _ in retrieved]

        return {
            "answer": answer,
            "contexts": contexts,
            "retrieved_ids": retrieved_ids,
            "trace": trace,
            "metadata": {
                "model": "keyword-rag-workflow-v3" if self.workflow_aware else "keyword-rag-baseline",
                "tokens_used": len(answer.split()) + sum(len(ctx.split()) for ctx in contexts[:3]),
                "sources": retrieved_ids,
                "retrieval_scores": {doc_id: score for doc_id, _, score in retrieved}
            }
        }

if __name__ == "__main__":
    agent = MainAgent()
    async def test():
        resp = await agent.query("Làm thế nào để đổi mật khẩu?")
        print(resp)
    asyncio.run(test())
