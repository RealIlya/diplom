# KEV–Laya comparison implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.

**Goal:** локально сравнить frozen KEV0.8B/4B/Laya на прежних30 карточках.
**Architecture:** один CLI сравнения, native adapters, отдельные процессы и pinned
локальные веса; existing binary_metrics/input_text переиспользуются.
**Tech Stack:** Python, PyTorch/MPS (Laya), MLX+PyTorch CPUhead (KEV), JSONL.
**Spec:** поручение инициатора25.10 и experiments/system-one-pilot/results/kev-comparison-20261025/protocol.json.

## Проверяемые шаги

- [x] Закрепить cohort/hashes, primarymetrics, repeats/calibration/denominators до прогнозов.
- [x] Проверить официальные веса/версии/SHA и отдельное окружение, offline load.
- [x] RED→GREEN для cohort validation, metrics/ties/missing rows, common admission.
- [x] scripts/system_one_pilot/compare.py: prepare/run/summarize; exact serialized input, raw timings/probs/RSS/backend memory.
- [x] Последовательно выполнить все3 модели; failures/retries версионировать, training не запускать.
- [x] Независимое review, Python checks, GitMark lint/index, MkDocs strict, diff check.
- [x] Сохранить таблицу результата/ограничения и исходные измерения, обновить wiki.

## Review focus

Никаких label-dependent prompts/порогов; uncertainty не0; no silent truncation;
KEV temperature уже вhead; синхронизация конкретного backend; одинаковые источники
и semantic question; cold load и warm latency отдельно; память unified не складывать;
никогда не держать4B идругие модели одновременно. Чужая рабочая копия сохраняется,
push/commit/платныеAPI/GPU не входят в поручение.
