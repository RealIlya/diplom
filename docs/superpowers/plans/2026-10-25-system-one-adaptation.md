# Независимая dev-проверка и head-only адаптация KEV-0.8B

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.

**Goal:** расширить существующие train данные, получить независимые dev семейства,
сравнить frozen/CE/Brier одной модели и выполнить небольшой парный native pilot.
**Architecture:** существующие PaidClient/native collector/annotation/review остаются
основой. Один модуль задаёт split/selection/dataset gates; второй кеширует native
KEV features и обучает только CPU FP32 head; отдельный online runner подключает
общий packer к штатному actor. Исходные30 карточек и frozen benchmark неизменны.
**Tech Stack:** Python unittest, SQLite, pinned τ-bench, MLX + torch CPU head.
**Spec:** поручение инициатора25.10 после списка следующих шагов; frozen
`experiments/system-one-pilot/results/adaptation-20261025/protocol.json`.

## Границы

- Использовать manifests-v3; test тела/метки/эпизоды не читать и не запускать.
- В split только5dev семейств:2 calibration (включая ранее изученное task_023
  семейство),3 validation, зафиксировать ДО новых меток/предсказаний.
- 5 новых train семейств, исключая все прежние попытки; до2tasks/dev family.
  Выбор стабильным hash, без замены задач по удаче эпизода/метке.
- Collection/annotation используют ПРЕЖНИЕ общие ledger caps$1/$0.50, включая
  уже списанное/удержанное. Перед платными действиями — estimate/preflight;
  unknown outcome или cap останавливает серию. Не повышать лимиты.
- До100 новых карточек, до10 на family, та же рубрика и доверенная политика
  DeepSeek/Qwen/арбитраж агента; без ручного gate и без новых labels старых30.
- Граница научного вывода — небольшой dev pilot; seed25 один, без HPO и test.
- Head-only KEV0.8B, original LoRA/backbone fixed; AdamW1e-4, wd.01,
  batch16,20epochs,seed25; CE и scalar binary Brier независимо от одного init.
- Temperature grid [.5,1,2,published,3,4,6,8] только calibration families;
  last epoch fixed, threshold.5; validation не выбирает epoch/LR/threshold.
- Native online ALL evaluator, те же tasks/seed/actor/simulator; результаты
  ENV-only не называть полным успехом. Сохранить ошибки/цены всех ролей.
- Существующая грязная ветка сохраняется; no commit/push/publish/reset.

## Task 1: Данные и деньги

Files: scripts/system_one_pilot/adaptation.py, live.py, live_data.py;
tests/test_system_one_adaptation.py.

- [x] RED: deterministic family plan, immutable split, no test, no old family reuse;
  семейный sampling, старые train labels не попадают в dev.
- [x] GREEN: prepare protocol; коллекция по explicit verified plan и новым call IDs;
  extract train/dev с family cap; baseline команда v1 остаётся совместимой.
- [x] 49 прежних System One tests + новые; фактический preflight и сбор,
  strict-schema разметка, agent adjudication, export и dataset gates.

## Task 2: Frozen / CE / Brier

Files: scripts/system_one_pilot/adapt_head.py; tests/test_system_one_adapt_head.py.
Consumes: dataset.jsonl+manifest, checked KEV source/weights, training protocol.

- [x] RED: labels не в encoder, train-only optimizer, fixed epochs, group split
  calibration/validation, temperature fit не смотрит validation, scalar Brier.
- [x] GREEN: native feature hook/cache с input/model hashes; CPU head optimizer,
  обе независимые ветви, manifests/curves, frozen controls.
- [x] Выполнить локальные feature/train/evaluate, сохранить raw predictions и
  sample+group метрики/coverage/ошибки; held-out test не запускать.

## Task 3: Native pilot

Files: scripts/system_one_pilot/online.py; tests/test_system_one_online.py.
Consumes: Task1 protocol/split, Task2 heads/temperature; тот же PaidClient.

- [x] RED: общий packer не превышает бюджет, только observed evidence IDs,
  non-KB tools/system policy сохраняются, model failure вызывает учтённый fallback;
  evaluator NL never leaks into actor, все роли/стоимости записаны.
- [x] GREEN: native + packed BM25 + LLM selector + frozen + CE + Brier, один
  preselected validation task/family, seed25. Common pack4096, stale KB receipts.
- [x] Выполнить парные episodes в остатке ledger, ALL evaluator с DeepSeek
  вместо неизвестного default judge; неполные/ошибки не отбрасывать.

## Task 4: Поставка

- [x] Независимый read-only review новых seams; fixes RED→GREEN.
- [x] Проверки, логи всех попыток, ссылки/hashes/затраты и canonical wiki report.
- [x] Решение о RLCD: перейти только при обосновании после простых методов;
  иначе зафиксировать отрицательный/неопределённый результат без запуска RL.

## Review focus

Family leakage; unseen validation not HPO; labels/hidden Task not actor/encoder;
archive metadata не выдаётся за новый результат; shared persistent dollar caps;
MPS/MLX/swap/CPU head timing; native evaluator полнота; no silent paid retries.
