# Первый пакет расширения данных и групповой KEV

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.

**Goal:** реализовать дневной API-предел$1, многокандидатную оценку KEV и
выполнить первую train-only ступень до200 новых пар в доступном бюджете.
**Architecture:** расширить существующий SQLite PaidClient атомарным общим
дневным резервом, сохранив прежние series caps. Новый grouped scorer использует
native Noul branches и общий state. Сбор/разметка используют существующие
collector, extract, rubric/schema и trusted policy с новым namespace/лимитами.
**Tech Stack:** Python unittest, SQLite, zoneinfo, pinned KEV MLX, native τ-bench.
**Spec:** [согласованные цели и бюджет](../../gitmark/system-one-next-stage.md),
[выбор формата](../../gitmark/README.md#wayfinder-multi-candidate).

## Global Constraints

- Поручение перейти к реализации27.10.2026; действующее разрешение на расширение
  данных/прежний маршрут API и бюджет$1 в сутки. Повторного разрешения не требуется.
- Все API роли суммарно$1/календарные сутки Asia/Novosibirsk. Actual неизвестен —
  весь максимум удержан; нерешённый исход блокирует новые вызовы. No auto retries.
- Старые ответы, метки, протоколы, caps и failed attempts не переписывать.
- Первый пакет только train, target200, без нового обучения/online сравнения/test.
  Кандидаты новых train-семейств имеют приоритет; кеш дополняет недостающий объём.
- Отдельные caps первого пакета collection$.20/annotation$.75, вместе≤$.95;
  дневной$1 включает все старые и новые роли, запас$.05 не расходуется намеренно.
- DeepSeek/Qwen независимо, schema-v2/rubric-v1; consensus и арбитраж по прежней
  политике; unknown/uncertain/defect не превращать в hard gold.
- Исследовательский holdout и тема статьи остаются вопросами карты; train-пакет
  не объявляется финальным научным протоколом или новым validation.
- Продолжить в текущей codex/rlcd-research: необходимые исходники и артефакты
  не закоммичены, новый чистый worktree их не содержит. No commit/push/reset.

## Review Focus

- Конкурентные резервирования разных ролей обязаны делить общий дневной предел.
- Переход даты/перезапуск не освобождает неизвестные расходы и старые caps.
- Повторные ID/изменённые payloads не приводят к повторной оплате.
- Пять Noul — пять независимых выходов, не softmax между документами; переполнение
  никогда не приводит к незаметной усечённой обработке.
- Перемещение документа в ветку — новая сериализация, отдельно от эффекта batching.

## Task 1: Атомарный дневной бюджет

Files: `scripts/system_one_pilot/live_api.py`, `tests/test_system_one_daily_budget.py`.
Interfaces: `configure_daily_budget(path, limit_nusd, timezone_name)`,
`authorize_series(path, series, limit_nusd)`, `daily_summary(path, now=None)`;
PaidClient.complete сохраняет прежний контракт.

- [x] RED: общий cap разных серий/ролей, граница даты UTC+7, unknown держит максимум,
  конкурентный reserve, immutable authorization, replay завершённого вызова.
- [x] GREEN: долговечная budget policy/новые series authorizations; проверять
  все роли и вставлять reserve в одной BEGIN IMMEDIATE до HTTP.
- [x] Проверить новые тесты и прежние BudgetTests в live-venv.

## Task 2: Native grouped scorer и локальная проверка

Files: `scripts/system_one_pilot/grouped.py`, `tests/test_system_one_grouped.py`,
минимальная совместимая точка подключения в `online.py`.
Interfaces: `group_payload(state, candidates)`, `GroupedKev.score_many(state,pool)`;
вызов нескольких независимых вопросов из одного state, группы до5.

- [x] RED: ID uniqueness, пустой пул, несколько полезных, хвост неполной группы,
  контроль числа выходов/NaN; прежний scalar selector остаётся совместим.
- [x] GREEN: формировать Noul с документом в инструкции ветки, без labels/gold;
  strict encode8192/8192, полный набор выходов, явно помеченная сериализация.
- [x] Локально сравнить старый scalar, новую сериализацию поодиночке и grouped
  на сохранённых train-группах; измерить token admission, секунды, MLX peak,
  probability delta. Не смешивать serialization drift и batch drift.

## Task 3: Замороженный первый пакет и поставка

Files: `scripts/system_one_pilot/expansion.py`, минимальные параметры series в
`live.py`, `tests/test_system_one_expansion.py`, README эксперимента/каноническая wiki.
Interfaces: deterministic train task plan/queue, old130 exclusion, state/pool
group provenance, новый protocol/результаты в expansion-20261027 и ignored artifacts.

- [x] RED: stable family-first train-only selection, исключение прежних id/input/
  snapshot-document; ни одной test body read; budget errors не проглатываются.
- [x] GREEN: выбрать сначала по одной задаче train-семейств вне прежнего dataset;
  сохранить protocol/task order до вызовов. Сбор до$.20, затем extract и до200
  карточек с family/snapshot балансом; дополнить сохранёнными train-кандидатами.
- [x] Перепроверить тарифы GET-preflight, включить дневную политику и новые
  caps; выполнить ограниченный сбор/двойную разметку с create-only receipts.
- [x] Сохранить все valid/technical/остановленные результаты, доверенные метки
  по прежней политике, итоговый бюджет и исходные hashes. Не обещать200при cap/stop.
- [x] Целевые+полные тесты, UI, GitMark/MkDocs; fresh read-only review новых seams,
  результат и ограничения в wiki. Полный набор может воспроизвести прежнее
  падение фиксированного списка PPTX — его не исправлять в этой задаче.

## Rulings / progress

Прогресс и отклонения: `experiments/system-one-pilot/results/expansion-20261027/work-log.md`.
Сохранить журнал и кодовые snapshots, не удалять после review: это исследовательские
артефакты, требуемые AGENTS.md. Реализация выполняется inline, один final review.

Первоначальное состояние27.10: инфраструктура и проверки завершены; первый API-пакет остановлен после provider504 без usage. Двойнаяразметка не запускалась, target200 не достигнут. См. paused-provider-504.json и work-log.md.

Продолжение27.10: инициатор явно разрешил учитывать эти504 полным максимумом,
без повторов, в пределах$1/сутки. provider-504-approval.json — дополнение к
неизменному протоколу. Узкий append-only helper и continuation driver проверены
6fake-тестами,97целевых проходят; freshreview0замечаний. Первый504 учтён без
изменения api_calls, повторовнет; выполняются только8не начатых задач и разметка.

Итог27.10: первый пакет завершён.400 ответов (389 valid/11 technical),200
доверенных меток (168 consensus/32 agent arbitration),181 пригодная для
бинарного обучения; новый dataset330 строк. Train8→15 семейств, old130 и
calibration/validation неизменны. Known$.448283146 / held$.467319346 с первым
504 по полному максимуму; новых provider504/платных повторов0. Экспорт и его
проверки выполнены, общий ledger backup integrity_ok.99/99целевых тестов,
полный129/130 с прежним PPTX failure; fresh export review0замечаний.
Ориентир1–3тыс., квоты и независимый holdout остаются в открытой карте;
обучение/новое сравнение качества не запускались. См. dataset-summary.json,
annotation-summary.json, budget-final.json и канонический отчёт wiki.
