# Evaluation results

Dataset: 60 queries (39 dev / 21 held-out). Embedding model: all-MiniLM-L6-v2 (fastembed). Retrieval top-k = 3. Threshold chosen on dev only; held-out evaluated once.

## Retrieval (queries with an answer in the KB)

| split | n | hit@1 (95% CI) | hit@3 (95% CI) | MRR |
|---|---|---|---|---|
| dev | 24 | 79% [60-91] | 88% [69-96] | 0.83 |
| heldout | 13 | 77% [50-92] | 92% [67-99] | 0.83 |

## Escalation: shipped threshold vs dev-chosen threshold

| split | threshold | precision | recall | F1 | auto-resolved | wrong auto-resolutions |
|---|---|---|---|---|---|---|
| dev | 0.75 (shipped) | 50% | 100% | 67% | 3/39 | 0 |
| dev | 0.50 (chosen) | 78% | 100% | 88% | 16/39 | 0 |
| heldout | 0.75 (shipped) | 48% | 100% | 65% | 0/21 | 0 |
| heldout | 0.50 (chosen) | 60% | 90% | 72% | 6/21 | 1 |

Held-out F1 at the chosen threshold, bootstrap 95% CI: [47-89]

## Dev threshold sweep

| threshold | precision | recall | F1 | auto-resolved | wrong auto |
|---|---|---|---|---|---|
| 0.30 | 100% | 56% | 71% | 29 | 8 |
| 0.35 | 92% | 67% | 77% | 26 | 6 |
| 0.40 | 81% | 72% | 76% | 23 | 5 |
| 0.45 | 78% | 100% | 88% | 16 | 0 |
| 0.50 | 78% | 100% | 88% | 16 | 0 |
| 0.55 | 69% | 100% | 82% | 13 | 0 |
| 0.60 | 67% | 100% | 80% | 12 | 0 |
| 0.65 | 62% | 100% | 77% | 10 | 0 |
| 0.70 | 55% | 100% | 71% | 6 | 0 |
| 0.75 | 50% | 100% | 67% | 3 | 0 |
| 0.80 | 46% | 100% | 63% | 0 | 0 |
| 0.85 | 46% | 100% | 63% | 0 | 0 |
| 0.90 | 46% | 100% | 63% | 0 | 0 |

## Does the raw score separate good from bad? (AUROC, 0.5 = chance)

- **dev**: answerable vs should-escalate AUROC = 0.93 (n=21/15); top-1 correct vs wrong AUROC = 0.93 (n=18/3)
- **heldout**: answerable vs should-escalate AUROC = 0.82 (n=11/9); top-1 correct vs wrong AUROC = 0.75 (n=10/2)
- **all**: answerable vs should-escalate AUROC = 0.91 (n=32/24); top-1 correct vs wrong AUROC = 0.86 (n=28/5)

## Top-1 cosine score by category (all queries)

| category | n | mean | min | max |
|---|---|---|---|---|
| adversarial | 6 | 0.44 | 0.31 | 0.64 |
| ambiguous | 8 | 0.32 | 0.17 | 0.46 |
| in_kb_direct | 18 | 0.65 | 0.42 | 0.80 |
| in_kb_hard | 8 | 0.51 | 0.38 | 0.67 |
| out_of_kb | 10 | 0.27 | 0.12 | 0.48 |
| refund_eligible | 4 | 0.47 | 0.35 | 0.58 |
| refund_ineligible | 6 | 0.45 | 0.32 | 0.56 |

## LLM-judged reply quality

Generator: openai/gpt-oss-120b. Judge: qwen/qwen3.8-27b (a different model family). An LLM judge is imperfect; treat these as indicative, not ground truth.

- Faithful to context: 98% [91-100] of 60 replies
- Replies that would be auto-sent at threshold 0.50: 22, of which faithful: 100%
- Adversarial prompts followed: 0/6
