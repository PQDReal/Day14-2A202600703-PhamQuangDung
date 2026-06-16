# Individual Reflection - Pham Quang Dung

## 1. Engineering Contribution

Trong lab này, phần đóng góp chính của tôi là xây dựng một evaluation pipeline end-to-end cho domain **University Student Support Agent**. Tôi viết lại `data/synthetic_gen.py` để sinh Golden Dataset gồm 75 cases, vượt yêu cầu tối thiểu 50 cases. Mỗi case có `expected_retrieval_ids`, `expected_answer`, `context`, `metadata` và một số case có `conversation` để phục vụ multi-turn evaluation.

Tôi cũng triển khai và nâng cấp các thành phần chính của hệ thống benchmark:

- Retrieval evaluation với Hit Rate và MRR.
- Multi-judge consensus với offline heuristic judges và online OpenAI judges.
- Regression testing giữa `Agent_V1_Base`, `Agent_V2_Optimized` và `Agent_V3_TrajectoryAware`.
- Release gate dựa trên quality, retrieval, agreement, latency, cost và trajectory metrics.
- Workflow/trajectory evaluation cho V3 để đo step count, tool call count, redundant tool rate và loop rate.

## 2. Technical Depth

Tôi hiểu rằng một hệ thống RAG evaluation cần tách retrieval quality khỏi answer quality. Hit Rate cho biết tài liệu đúng có nằm trong top-k hay không, còn MRR cho biết tài liệu đúng xuất hiện sớm đến mức nào trong ranking. Nếu retrieval tốt nhưng answer fail, lỗi nhiều khả năng nằm ở prompting, generation hoặc judge calibration.

Multi-judge consensus giúp giảm rủi ro phụ thuộc vào một judge duy nhất. Trong project này, hệ thống hỗ trợ cả offline mode và online mode với hai GPT judges: `gpt-4o-mini` và `gpt-4.1-mini`. Agreement rate và conflict flag giúp phát hiện những case judge bất đồng, đặc biệt trong prompt injection hoặc goal hijacking.

Tôi cũng bổ sung trajectory evaluation để không chỉ chấm final answer mà còn quan sát workflow: agent có gọi tool quá nhiều không, có retry/backtrack không, có loop không và có tốn token/latency vô ích không.

## 3. Problem Solving

Một vấn đề ban đầu là repo chỉ có placeholder cho SDG, evaluator và judge. Tôi giải quyết bằng cách tạo deterministic SDG và offline evaluation để pipeline luôn chạy được, sau đó mở rộng thêm online judge khi có API key.

Trong Phase 3, benchmark baseline phát hiện nhiều lỗi: agent retrieve đúng nhưng trả raw context, judge lexical phạt câu trả lời tiếng Việt, và agent chưa xử lý tốt retrieval mapping/failure probe. Tôi cải thiện bằng cách thêm intent routing, guardrails, judge prompt calibration và release gate có threshold rõ ràng.

Kết quả cuối cùng cho V3:

- Tổng số cases: 75
- Hit Rate: 1.00
- MRR: 0.991
- Pass Rate: 1.00
- Offline avg score: 4.92 / 5.0
- Online GPT judge run gần nhất: V3 score khoảng 4.80 / 5.0
- Release Gate: RELEASE

## 4. Next Improvements

- Thay keyword retrieval mô phỏng bằng Vector DB thật.
- Thay faithfulness/relevancy lexical heuristic bằng semantic/RAGAS metrics thật.
- Chạy online judge nhiều lần để đo variance, standard deviation và các case có disagreement cao.
- Nếu agent dùng external tools thật, mở rộng trajectory evaluation để đo tool failure, tool overuse, retry churn và workflow thrashing.
