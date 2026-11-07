---
node_type: reference
title: Атлас System One — архитектура стенда и потоки данных
service: _platform
status: draft
updated: 2026-10-19
links:
  depends_on: [docs/gitmark/architecture.md, docs/gitmark/research.md]
  relates_to: [docs/gitmark/tau-bench-review.md, docs/gitmark/GLOSSARY.md, docs/gitmark/resource-assessment.md, docs/gitmark/system-one-training-review.md]
---

# Атлас System One — архитектура стенда и потоки данных

**Статус на 19.10.2026:** технический проект для реализации и review, не работающий
стенд. Принятая граница исследования и определения остаются в
[общей архитектуре](architecture.md#shared-context-integration) и
[словаре](GLOSSARY.md). Здесь описаны размещение кода, контракты, точки подключения
к upstream и проверяемые границы данных. Этот документ конкретизирует
[контекстный контракт v0](architecture.md#context-contract-v0), не заменяет его
новым списком согласований. Метод обучения, окончательные модели и численные
параметры остаются параметрами протокола.

Главная замена — **оценщик полезности наблюдаемого KB-контекста**. Один и тот же
основной LLM-агент выполняет действия и отвечает пользователю во всех трёх
основных условиях. Компактная модель не получает ответственность за аргументы
банковских tools. Научный вклад адаптации проверяется прежде всего парой
исходная/дообученная компактная модель с одинаковым packer и состоянием.

## 1. Что существует сейчас

Последующее состояние 19.10.2026: реализован [локальный offline стенд](system-one-pilot.md)
в `scripts/system_one_pilot/`, с manifests/labels/results в
`experiments/system-one-pilot/`. Таблица ниже описывает состояние при подготовке
атласа; native adapter/runner пока не реализованы и не проверены эпизодом.

| Объект | Проверенный статус | Что из этого не следует |
| --- | --- | --- |
| [Каноническая архитектура](architecture.md) и [аудит native retrieval](tau-bench-review.md#native-context-pipeline-audit) | Документированы принятая граница и инженерный контракт | Реализация tau-агента ещё не готова |
| `scripts/measure_tau_history_context.py` | Анализирует закреплённый публичный префикс траекторий tokenizer Qwen; проверяет SHA-256; не вызывает модель | Это не измерение качества KEV, не обучающий корпус и не репрезентативная оценка всего benchmark |
| `tests/test_agent_evaluator.py`, `tests/test_agent_planner.py`, `tests/test_vendor_examples.py` | Проверяют импортированный навык `agent-designer`, его CLI и примеры | Слово evaluator в имени не означает native evaluator τ-bench |
| [Ресурсная оценка](resource-assessment.md) | Содержит зафиксированные измерения длины опубликованных историй и ограничения их интерпретации | Сквозное преимущество System One не измерено |
| Локальный `artifacts/` | Найдены граф wiki, PDF/превью презентаций и их служебные результаты | Не найдены экспериментальные run manifests, обученные веса или таблица результатов трёх условий |
| Предлагаемые ниже `src/system_one_tau/`, `configs/atlas/`, `data/manifests/` | **Ещё не созданы** | Дерево ниже — схема будущих файлов, не команда запуска |

Не импортировать vendor planner/evaluator как основу научного harness: они решают
другую задачу. Проверки документации также не подтверждают работоспособность
будущего агента.

## 2. Проверенная версия τ и точки расширения

Повторная статическая проверка исходников выполнена **19.10.2026** на commit
`4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699` репозитория
`sierra-research/tau2-bench`. Это закреплённая опора существующего аудита, а не
утверждение, что commit — последний upstream или уже окончательно выбранная
версия итоговой серии. В `pyproject.toml` этого commit пакет называется `tau2`,
версия `1.0.1`, Python `>=3.12,<3.14`; для воспроизводимости commit важнее одного
номера пакета. Перед запуском надо отдельно закрепить разрешённые зависимости
и данные. [Первичный manifest][up-project].

| Путь upstream | Реальный контракт на этом commit | Как использовать |
| --- | --- | --- |
| `agent/base_agent.py` | `HalfDuplexAgent`, вход `UserMessage \| ToolMessage \| MultiToolMessage` | Базовый интерфейс текстового адаптера; поддержать целый batch результатов |
| `agent/base/participant.py` | `get_init_state(message_history=None)` и `generate_next_message(message, state) -> (message, state)` | Реализовать собственный state с raw-наблюдениями и производной view |
| `agent/llm_agent.py` | `LLMAgent` добавляет вход в state и передаёт `system_messages + messages` в `generate` | Native контроль; пример одной actor LLM. Его `_generate_next_message` не является готовым селектором |
| `registry.py` | `register_agent_factory(factory, name, task_filter=None, metadata=None)` | Зарегистрировать фабрики условий до создания runner; имя фабрики и config входят в manifest |
| `runner/build.py` | `build_agent` берёт tools/policy из среды и вызывает factory; `build_text_orchestrator` связывает agent/user/environment/task | Переиспользовать native wiring, сохраняя текстовый режим и обычного user simulator |
| `runner/simulation.py` | `run_simulation(orchestrator, evaluation_type=ALL, env_kwargs=None)` выполняет эпизод и оценивание | Минимальный путь для smoke-test и одного эпизода |
| `runner/batch.py` | `run_single_task`, `run_tasks`, `run_domain` | Пакетная серия после проверки одного эпизода; помнить о retries и побочных расходах |
| `evaluator/evaluator.py` | `evaluate_simulation(simulation, task, evaluation_type, solo_mode, domain, …)` | Оставить native критерии; отдельно присоединить наши измерения селектора |

Первичные источники: [текстовый agent][up-base], [participant][up-participant],
[LLMAgent][up-llm], [registry][up-registry], [builder][up-build],
[simulation][up-simulation], [batch][up-batch], [evaluator][up-evaluator].
В этом commit `BaseAgent`/`LocalAgent` — совместимые устаревшие имена
`HalfDuplexAgent`; в новом коде использовать актуальное имя.
`src/tau2/runner/run.py` отсутствует: модуль runner разбит на перечисленные слои.
[Экспорты и aliases][up-init], [экспорты runner][up-runner].

**Важная граница factory.** `build_agent` передаёт `task=task` даже обычным
фабрикам. Наш factory допускает этот keyword ради совместимости, но не передаёт
объект `Task` в agent/scorer и не сохраняет его в state. Содержимое `Task`, включая
evaluation criteria, необходимо orchestrator и evaluator, но не является
наблюдением селектора. Не использовать `LLMGTAgent`: его назначение — доступ
к ожидаемым действиям, а не честный baseline. [Builder][up-build], [GT-класс][up-llm].

Для `banking_knowledge` builder также вычисляет из эталонных действий
`read_log_allowlist`, влияющий на журналирование read-tools в среде. Его надо
сохранить в native wiring, включая одинаковые `env_kwargs` при оценивании;
переносить этот список в признаки модели нельзя. Это подтверждённая особенность
закреплённого upstream, а не наш источник supervision. [Реализация][up-build].

## 3. Условия сравнения и неизменная часть

| ID | Кто отбирает контекст | Что получает actor LLM | Назначение |
| --- | --- | --- | --- |
| `NATIVE` | Отдельного селектора нет | Штатную накопленную историю native `LLMAgent` | Исходная точка полной стоимости и качества |
| `RECENCY` | Последние уникальные наблюдаемые KB-единицы + общий packer | Общую защищённую историю и выбранный блок | Дешёвый контроль необходимости модели |
| `LEXICAL` | BM25-переранжирование только наблюдаемого пула + общий packer | Ту же форму проекции | Дешёвый содержательный контроль |
| `LLM_SELECT` | LLM выбирает упорядоченные ID из всего snapshot | Ту же форму проекции | Запрошенный LLM baseline для узла отбора |
| `S1_FROZEN` | Исходные веса C дают pointwise scores + общий packer | Ту же форму проекции | Дефолтная System One |
| `S1_ADAPTED` | Дообученные веса той же C + тот же packer | Ту же форму проекции | Эффект адаптации на данных выбранной области |

`LLM_SELECT`, `S1_FROZEN`, `S1_ADAPTED` — три основные группы; `NATIVE`,
`RECENCY`, `LEXICAL` нужны, чтобы не доказывать экономию только относительно
заведомо дополнительного LLM-вызова. Joint LLM selection и pointwise C+packer
различаются алгоритмом: дополнительный `LLM_POINTWISE` с тем же packer допустим
как диагностическое условие, если нужно отделить модель от алгоритма упаковки.

Во всех модифицированных условиях фиксируются actor model/revision, policy,
tools, native retrieval, user simulator, evaluator, state extraction,
допустимое разбиение, бюджет и обработка ошибок. При replay сравнивается один
snapshot; в живых эпизодах действия и будущие наблюдения могут расходиться.
Это часть end-to-end эффекта, а не нарушение парного назначения задач.

Первый профиль — `banking_knowledge + bm25`. Upstream default retrieval нельзя
оставлять неявным: в проверенном коде есть более дорогой `alltools` с другим
набором возможностей. `KB_search` форматирует найденные записи с полным content;
native top-k не ограничивает всю историю. [Formatter][up-retrieval-mixins],
[варианты retrieval][up-retrieval], [подробный аудит](tau-bench-review.md#native-context-pipeline-audit).

DeepSeek V4.1 Flash из запроса пользователя — существующий кандидат: подтверждены
релизы V4.1-Flash и V4.1-Flash-1017, текущий alias `deepseek-flash`.
[Версия, API и ограничения режимов](system-one-atlas-evidence.md#5-deepseek-v41-flash-подтверждён-alias-меняется)
проверены по официальным источникам. Доступ аккаунта и совместимость нашего
τ-адаптера ещё не проверены запуском. В manifest необходимы точный model ID,
provider, revision/дата, reasoning mode, применимые sampling parameters, output
limit и тариф; actor и selector обозначаются разными ролями даже при одном model ID.

## 4. Один цикл агентного шага

```text
native orchestrator доставляет видимое сообщение / batch
  → append-only raw_history
  → deterministic state extractor + парсер полученного KB
  → observed_pool: все версии ранее наблюдавшихся доказательств
  → immutable snapshot до текущего cutoff
  → admission по полному сериализованному входу
  → LLM_SELECT ИЛИ C_frozen/C_adapted → одинаковый packer
  → техническая проверка результата / разрешённый fallback
  → model_view: защищённая история + выбранный evidence block
  → одна actor LLM
  → native AssistantMessage: ответ ИЛИ вызов tools
  → native environment/user → следующее наблюдение

После эпизода, за отдельной границей:
  native trajectory + Task + environment replay → native evaluator
  traces + native result → отчёт по качеству, стоимости, задержке
```

Селектор запускается перед очередным actor-вызовом, если семантический snapshot
изменился и есть наблюдаемый KB-пул. До первого KB-наблюдения он не вызывается.
Нельзя переоценивать промежуточное состояние, пока получен только кусок
`MultiToolMessage`: в snapshot должны войти все доставленные результаты.

### 4.1. Raw history и состояние

`raw_history` хранит только видимую агенту последовательность. Полная native
trajectory может содержать также приватные tool calls симулятора; её нельзя
целиком подавать extractor. В upstream есть
`is_valid_agent_history_message`: assistant messages, пользовательские сообщения
без user tool calls и результаты tools с `requestor == "assistant"`.
[Проверка видимости][up-base].

`state` строится по [контракту v0](architecture.md#context-contract-v0): все
пользовательские реплики до cutoff; связанные предшествующие речевые
assistant-сообщения; последняя наблюдаемая query с исходом; все non-KB tool events
с именами, аргументами, ответами и provenance. Это извлечение наблюдений, не
LLM-summary и не вычисление «истинного банковского состояния». Старые поправки,
отзыв согласия и повторные исполнения tools не схлопываются.

### 4.2. Observed pool и кандидаты

Parser принимает только реально доставленный body известного retrieval tool.
Один ID с тем же content hash объединяет provenance; изменившийся content
создаёт новую версию. Не найденные документы, ошибки и timing footer не становятся
доказательствами. Недостоверный разбор означает `KB_PARSE_ERROR`, не чтение
полного документа из корпуса по ID. Текст с похожим на разделитель content должен
либо однозначно разбираться, либо отвергаться; одной наивной regex недостаточно.

В пуле остаётся весь наблюдённый материал. Для конкретного snapshot сначала
пробуется целая native запись; дополнительное разбиение одинаково для условий
и оправдывается admission. Сохраняются source spans, заголовки и версия splitter.
Нельзя незаметно ограничить пул последними top-M документами ради скорости.

### 4.3. C, packer и LLM-селектор

Скорер C обрабатывает `(state, candidate)` и выдаёт конечное `p_useful ∈ [0,1]`.
Все кандидаты snapshot получают оценки. Packer сортирует по оценке и стабильному
ID, добавляет целые единицы, которые помещаются, и пропускает слишком длинные;
порог `p ≥ 0.5` в baseline отсутствует. Token budget относится к готовому
evidence block с оформлением. Вероятность полезности одного фрагмента не равна
вероятности достаточности набора.

LLM-селектор видит тот же state, весь тот же candidate pool и бюджет; возвращает
только IDs. Ему не передают compact scores, предварительный shortlist или
дополнительную историю. Один форматный repair допустим по контракту v0;
исходный snapshot неизменен, расходы repair сохраняются. Если совместный вход
не помещается, результат `SELECTOR_OVERFLOW`; постраничный алгоритм — отдельное
будущее условие, а не скрытый fallback.

### 4.4. Проекция actor-входа

Проекция каждый раз строится заново из raw. Policy, tool schemas, диалог и
non-KB tools сохраняются. Только KB-body в retrieval messages заменяется
квитанцией; tool-call IDs, порядок и роли остаются прежними. Один выбранный
evidence block вставляется в последний существующий retrieval result и явно
обозначается как agent-side projection накопленных наблюдений, а не оригинальная
выдача последней query. Ошибка последнего поиска остаётся ошибкой.

Объекты upstream сообщений нельзя изменять по общей ссылке: projection строит
отдельные значения для модели. Иначе испортится native trajectory и strict replay
evaluator сравнит изменённый ответ tool с оригинальным. В доказательствах могут
быть инструкции — они остаются недоверенным содержимым, не system messages.
Факты, уже процитированные в защищённых assistant-репликах, могут сохраниться;
их токены входят в полную стоимость.

## 5. Контракты полезной нагрузки

Ниже **предлагаемые схемы**, не существующие upstream-типы. Nullable поле
означает неизвестное, а не нулевое значение.

| Тип | Обязательные поля и инвариант |
| --- | --- |
| `VisibleEvent` | `event_id`, `role`, `content`, `tool_call_id?`, `tool_name?`, `arguments?`, `requestor?`; исходный порядок; отдельно сохранить исходный serialized hash |
| `EvidenceUnit` | `unit_id`, `native_id?`, `content_hash`, `title`, `text`, `source_event_ids`, `source_spans`, `representation_version`; каждый span указывает на реально полученный текст |
| `SelectionState` | `dialogue`, `search_context`, `tool_events`, `included_event_ids`, `excluded_event_ids`, `extractor_version`; без Task/gold |
| `SelectionSnapshot` | `snapshot_id`, `cutoff_event_id`, `state`, `candidates`, `effective_kb_budget`, `representation_version`, `semantic_hash`; immutable |
| `ScoreBatch` | `snapshot_hash`, `scorer_id`, `scores[{unit_id,p_useful}]`, `status`, `request_ids`; ровно одна валидная оценка каждой единицы либо явный отказ |
| `SelectionResult` | `snapshot_hash`, `method_id`, `ordered_unit_ids`, `rendered_tokens`, `status`, `fallback_reason?`; все IDs принадлежат snapshot и уникальны |
| `ActorProjection` | `snapshot_hash`, `messages`, `tools_hash`, `policy_hash`, `actor_token_count`, `reserved_output_tokens`, `selected_ids`, `projection_hash`; raw не меняется |
| `TrialOutcome` | `run_id`, `task_id`, `trial`, `attempt_id`, `native_simulation_id?`, `native_reward?`, `native_termination?`, `technical_status`, `ledger_ref`; отсутствие native reward не заменяется выдуманным reward |

Предлагаемые чистые функции: `extract_state(visible_events)`,
`update_observed_pool(pool, visible_events)`, `make_snapshot(state, pool, profile)`,
`score(snapshot, scorer)`, `pack(snapshot, scores)`,
`validate_selection(snapshot, result)`, `project(raw, snapshot, result)`.
Побочные эффекты ограничены model adapters, native tools и записью traces.
Новый оркестратор агентов или шина сообщений для этого не нужны.

Семантический hash не включает model ID/веса/prompt конкретного метода, иначе
равные сведения будут иметь разные hashes. Request/cache key, наоборот, включает
model, tokenizer, prompt, inference config и content versions. Детерминированная
канонизация JSON и правила float/Unicode должны иметь собственную версию.

## 6. Бюджеты, отказы и будущий R

Стартовые `B_KB=2048` и профиль `4096` для полного compact input уже описаны
как **предложение** в [контракте v0](architecture.md#context-contract-v0).
Они не гарантируют admission; окончательные пределы задаются после длинового
аудита и не меняются по результатам test. Считать надо весь serialized input
каждого tokenizer, включая state, wrappers, варианты ответа и reserved output.
Нельзя разрешать runtime молча обрезать запрос.

| Событие | Предложенное поведение |
| --- | --- |
| Нет KB-пула | Native actor-вызов, без искусственного retrieval message |
| `STATE_OVERFLOW`, `CANDIDATE_OVERFLOW`, `SCORER_ERROR` | Техническая передача того же snapshot LLM, если он помещается; отдельно считать это событие |
| `KB_PARSE_ERROR` | Остановить этот эпизод с диагностикой; отсутствующий текст не восстанавливать через corpus |
| `SELECTOR_ERROR`, `SELECTOR_OVERFLOW` после разрешённого repair | Явная техническая неудача; не возвращаться к ранее отвергнутому набору |
| `MAIN_OVERFLOW` | Явная техническая неудача; policy/согласие пользователя не удаляются ради продолжения |

**Технический terminal path требует реализации.** В закреплённом orchestrator
вызов agent может бросить исключение наружу; обработчик communication errors не
оборачивает любое исключение scorer. В batch `run_with_retry` повторяет исключения
и при исчерпании создаёт `INFRASTRUCTURE_ERROR` с пустыми messages и нулевой
duration. Поэтому нельзя просто бросить `AgentError` и считать, что получен
полный native failure record. Нужен минимальный внешний ledger: записать raw и
причину до исключения, сохранить каждую попытку, задать явный retry policy,
включить неудачу в общий знаменатель. Native evaluator/его reward при этом не
подменяется. [Orchestrator][up-orchestrator], [retry implementation][up-progress].

В native `evaluate_simulation` большинство преждевременных termination дают
reward 0; режим `ALL` учитывает `reward_basis` конкретной задачи. Это не означает,
что любой невозвращённый из runner эпизод автоматически получил проверенный
native reward. В отчёте различаются возвращённый native ноль, отсутствие
native оценки и заранее определённый нулевой end-to-end success технического
срыва. [Критерии][up-evaluator], [поля SimulationRun][up-simulation-model].

System One R остаётся отдельным модельным узлом для риска принятия **набора**.
В первой серии адаптации применяется `always_accept` после технической валидации;
R не обучается одновременно с C и не маскирует эффект C. Позже R получает
state, выбранный набор и зафиксированные признаки наблюдаемого пула; событие
ошибки, метки и отдельный calibration split задаются заранее. Нельзя получать
`q_risk` как «автоматическую калибровку» минимума/среднего C scores. Ошибка
исполнения R — технический fallback, а не откалиброванная передача. В сравнении
адаптированного R фиксируются C, packer и actor; это другая экспериментальная серия.

## 7. Предлагаемая структура реализации

Создавать файлы по мере появления содержимого; пустые каталоги сейчас не нужны.
Это минимальное разбиение ответственности, не требование написать отдельный
framework или отдельный класс на каждую строку.

```text
src/system_one_tau/
  contracts.py       # snapshot/result/config, инварианты и версии
  tau_agent.py       # HalfDuplexAgent + factory; одна actor LLM
  observations.py    # visible-event filter, state, observed pool/parser
  selection.py       # recency/BM25, common packer, validation/admission
  model_adapters.py  # LLM selector и compact scorer; frozen/adapted = config
  projection.py      # detached model_view, tool-call protocol
  telemetry.py       # request/decision/attempt ledger и расходы
  dataset.py         # split-filtered snapshots, labels, lineage
  training.py        # реализуется только для выбранного первого метода
  evaluation.py      # join native outcomes + node metrics; без смены evaluator
configs/atlas/
  banking_pilot.yaml # роли моделей, arm, бюджеты, seeds, retry policy
data/manifests/
  sources.json       # URI, revision, hash, license, область использования
  splits.json       # task/group IDs, rationale, версия и hash
tests/
  test_tau_contract.py
  test_observations.py
  test_projection.py
  test_dataset_boundaries.py
  test_failure_ledger.py
artifacts/           # локальные ignored runs/данные/веса; не сырой Git-архив
```

`model_adapters.py` содержит только реально выбранный compact backend. Не нужны
заранее три параллельные обёртки и новая абстракция для неопределённых моделей.
Frozen/adapted отличаются weight revision и, при необходимости, обученной головой,
а не копией всей программы. Training entry point появляется после проверки
лицензии, native train API и возможности честно считать выбранный loss.

## 8. Поток материала для обучения и оценки

```text
закреплённые задачи/семейства τ + KB + policy + code revision
  → manifest источников и группировка до генерации данных
  → train / dev_tune / dev_cal для C и при наличии R / locked test
  → collection runs ТОЛЬКО разрешённых задач нужного split
  → native trajectory → фильтр видимых префиксов по cutoff
  → тот же extractor/parser/snapshot, что в runtime
  → отдельная разметка candidate usefulness / set sufficiency / outcome
  → train examples + provenance → обучение C → checkpoint manifest
  → validation: выбор checkpoint/настроек; затем freeze
  → locked snapshot test и отдельные живые эпизоды всех arms
  → native evaluator + traces → анализ с интервалами неопределённости
```

Training на данных того же benchmark означает обучение на выделенных задачах
и/или независимых группах этой области, не reuse закрытого test. Все префиксы,
повторы, teacher continuations, синтетические варианты и sibling tasks одной
группы остаются в одном split. Простого random split строк недостаточно.

Наличие общего банковского KB допустимо для опыта «новые задачи в знакомой
области», но не доказывает перенос на новые policy. Для такого заявления нужен
отдельный holdout документов/семейств и анализ пересечений. Публичные trajectory
с известными решениями test не превращаются в разрешённый train только потому,
что их можно скачать. Уже прочитанные публичные примеры отмечаются в contamination
ledger. Конкретные доли и число задач закрепляются после аудита достаточности.

| Материал | Доступ runtime C/actor | Доступ offline pipeline | Правило |
| --- | --- | --- | --- |
| Policy, доступные схемы tools | По обычному native контракту | Да | Версии и hashes фиксируются |
| Реально полученные agent-visible сообщения до cutoff | Да | Да | Единственный источник состояния и observed pool |
| KB-запись, ещё не полученная агентом | Нет прямого доступа селектора | Для аудита/разметки в разрешённом split | Не подставлять текст в snapshot по известному ID |
| Приватные инструкции/действия user simulator | Нет | Закрытый evaluator/аудит | Не переносить в модельные признаки |
| `Task.evaluation_criteria`, эталонные действия, DB state | Нет | Native evaluator; train-only проверка меток при обоснованном протоколе | Offline join после cutoff, без проникновения gold в input |
| Будущие сообщения/финальный reward | Нет | Метки/анализ после завершения | Нельзя использовать их для извлечения потребности текущего шага |
| Teacher rationales | Не обязательны; основной inference может быть без них | Отдельный training artifact | Не считать автоматически gold; provenance и доступ к данным фиксируются |

Разметка отделяется от features физически: `snapshot_id → labels` соединяется
после формирования immutable snapshots. Датасет для C содержит
`(snapshot_id, unit_id, target, label_source, confidence/ambiguity, label_version)`.
Native reward — label эпизода; без дополнительного анализа он не становится
правильной меткой каждого входившего в эпизод документа. Метки weak teacher,
ручные проверки и контрфактические продолжения должны различаться.

Калибровочный `dev_cal` нужен и без R: после выбора checkpoint на `dev_tune`
сравниваются raw C и C после одинакового temperature-scaling протокола для
frozen, adapted-CE и adapted-Brier. Штатная температура default checkpoint
сохраняется отдельным условием `published default`, а не незаметно заменяется.
Отчёт различает эффект обучения весов и post-hoc calibration; её параметры
не выбираются по test. Калибровка `p(useful)` не калибрует `q(error_accept)`
будущего R: это разные целевые события.
[Matched raw/TS протокол](system-one-atlas-protocol.md#7-обучение-от-дешёвого-контроля-к-адаптации).

Обучение CE/Brier на одинаковых метках и обучение с рассуждением/дистилляцией —
разные факторы. Для них используются те же splits и snapshot contracts, но
отдельные manifests. Возможность учить CE/Brier именно native вероятностную
голову выбранной модели проверяется до реализации; текстовое «0.82» генеративной
модели не подменяет calibrated probability. Подробности методов — в
[обзоре обучения](system-one-training-review.md).

## 9. Журналирование и воспроизводимость

Одна строка `decision_trace` соответствует одному cutoff, одна строка
`request_ledger` — каждой попытке вызова любого backend, включая repair/fallback.
Данные хранятся локально с разрешениями; в Git — schemas, manifests, checksums,
команды воспроизведения и разрешённые агрегаты.

| Таблица/артефакт | Минимальные поля |
| --- | --- |
| `run_manifest` | protocol ID, repo dirty state/commit, upstream/data hashes, split hash, arm, actor/selector/user/judge/C/R versions, prompts/tokenizers, retrieval, projection, training checkpoint, hardware/runtime, precision, seeds, limits, retries, tariff date |
| `decision_trace` | run/task/trial/attempt, cutoff, semantic hash, candidate count/versions, input admissions, per-unit scores, selected IDs, rendered tokens, fallback class, component durations, projection hash |
| `request_ledger` | request/parent IDs, role, backend, attempt, start/end, input/output/cache/reasoning tokens если доступны, reported cost, estimated cost и метод оценки, timeout/error, cache hit |
| `dataset_manifest` | source/split/group IDs, extraction and label versions, author/checker, contradictions/ambiguity, row hashes, licenses, known overlaps, excluded reasons |
| `checkpoint_manifest` | base revision, adapter/head revision, training rows hash, loss definition, seed, optimizer/schedule, precision, trainable parameters, selected checkpoint rule, compute/cost |
| `trial_outcome` | все назначенные эпизоды и попытки, native reward/termination если получены, technical status, actor quality metrics, общий ledger reference |

LLM latency отделяется от загрузки весов, tokenization, scoring, упаковки, native
retrieval и judge. Сумма длительностей компонентов не всегда равна wall-clock
при batching/overlap; оба значения хранятся отдельно. Actor cost, полная online
стоимость, расходы генерации/разметки/обучения и амортизация — отдельные величины.
Если данные о токенах/цене не получены, записывается `null` и причина. Кеш для
воспроизведения и production cache могут давать разные оценки задержки: режим
кеша обязан быть одинаковым в сравнении и явно указанным.

Нельзя полагаться только на `SimulationRun.agent_cost`: отдельные вызовы C,
LLM-селектора, repairs и потерянные при исключении попытки требуют собственного
ledger. Суммирование не должно повторно учитывать actor cost из двух источников.
Цена native simulator/judge относится к полной стоимости экспериментального
стенда; отдельно показывается стоимость пользовательского agent service.

## 10. Минимальные проверки при реализации

Это **план meaningful tests**, не сообщение о пройденных runtime-тестах.
Сначала синтетические fixtures без API, затем один явно ограниченный smoke-run
после выполнения ресурсных условий проекта.

| Проверка | Ошибка, которую обязана обнаруживать |
| --- | --- |
| Factory и visibility boundary | В `task`/приватный user tool result помещён sentinel; ни snapshot, ни scorer/actor request его не содержат |
| Старое исправление/отзыв согласия | После десятков retrieval старый запрет не потерян; короткое «да» связано с правильной предыдущей репликой |
| KB parsing и версии | Повтор той же записи сохраняет provenance; изменённый content получает новую версию; неоднозначный разделитель даёт отказ, не выдуманный документ |
| Mixed batch и detached projection | Для KB+business tool batch сохранены все IDs/results; raw до/после идентичен; выбранный блок ровно один, невыбранный sentinel исчез только из KB-body |
| Information parity | LLM/frozen/adapted получают один semantic hash; LLM не видит compact scores или лишнюю историю; все candidate IDs учтены |
| Полный token admission | Точный предел принимается, превышение на один токен отвергается для state/C/selector/main; runtime не выполняет truncation |
| Ошибки и ledger | NaN, неполный score batch, чужой ID, timeout, исчерпанный repair дают различные статусы; потраченные запросы и все попытки остаются в итогах |
| Split isolation | Перенос одного sibling task/trajectory prefix между splits ломает проверку; future reward не входит в snapshot input |
| No-op native equivalence | При отключённом отборе на mocked LLM сохраняются исходные messages/tools/policy; native evaluator получает исходные tool outputs |
| Frozen/adapted reproducibility | При одном checkpoint/config получаются те же scores в детерминированном режиме; изменение только checkpoint отражается в manifests, не в state/packer |
| Metric denominator | Technical failures и повторные попытки нельзя потерять join-операцией; success rate и cost считаются по заранее определённым единицам |

До paid pilot нужны: воспроизводимый один эпизод, проверенные input lengths,
неизменённый native evaluator, работающий ledger и согласованный предел затрат
с условием остановки. Наличие такой схемы не разрешает запуск платной серии.

## 11. Риски и открытые технические решения

1. **State extraction может потерять смысл.** Тот же плохой state получат все
   селекторы; LLM fallback не восстановит невидимый факт. Нужен отдельный аудит
   представления, включая ссылки на более ранние assistant-объяснения.
2. **Формат retrieval текстовый.** Parser зависит от закреплённого formatter;
   upstream update требует fixtures и повторной проверки. Подмена tool output
   структурированным JSON без отдельного условия изменит среду.
3. **Размер state растёт.** Даже splitting всех KB не исправит state overflow.
   Сжатие state — дополнительное изменение протокола, которое нельзя вводить
   незаметно только для одной модели.
4. **Стоимость pointwise C масштабируется с пулом.** Обработка каждой пары
   state/candidate может повторять длинный state и оказаться дороже одного joint
   LLM selection. Измерять throughput, batching и cache, не выводить экономию
   из числа параметров.
5. **Нет гарантии переносимости loss.** KEV/Laya имеют разные train/runtime
   интерфейсы; нельзя обещать идентичный CE/Brier/RLCD pipeline до проверки
   доступного кода, trainable head и ограничений лицензии.
6. **Мало независимых задач.** Тысячи candidate rows из десятков задач не дают
   тысячи независимых испытаний. Необходимы task/group-level интервалы и анализ
   overlap; размер split определяется доступными группами.
7. **Native failure handling может скрывать расходы.** Пустой placeholder после
   retries не заменяет attempt ledger. Реализация terminal path обязательна
   до сквозного измерения.
8. **Изменчивые backend и upstream.** Закрепить revision, список задач, исправления
   evaluator, provider mode и тариф; при изменении — новая серия, не незаметное
   продолжение старой таблицы.

## Первичные источники и область проверки

Все ссылки ниже закреплены на `4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699`,
исходники прочитаны 19.10.2026. Это статическая проверка интерфейсов и control
flow: upstream, модели и платные API в рамках подготовки документа не запускались.
Локальные наблюдения о наличии файлов не являются результатами эксперимента.

[up-project]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/pyproject.toml
[up-base]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/agent/base_agent.py
[up-participant]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/agent/base/participant.py
[up-llm]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/agent/llm_agent.py
[up-registry]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/registry.py
[up-build]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/runner/build.py
[up-simulation]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/runner/simulation.py
[up-batch]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/runner/batch.py
[up-evaluator]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/evaluator/evaluator.py
[up-init]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/__init__.py
[up-runner]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/runner/__init__.py
[up-retrieval-mixins]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_mixins.py
[up-retrieval]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py
[up-orchestrator]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/orchestrator/orchestrator.py
[up-progress]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/runner/progress.py
[up-simulation-model]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/data_model/simulation.py
