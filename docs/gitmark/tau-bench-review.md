---
node_type: reference
title: Обзор τ-bench
service: _platform
status: active
updated: 2026-10-11
links:
  relates_to: [docs/gitmark/README.md]
---

# Обзор τ-bench для сервисного агента

Проверено **29.09.2026**. Направление выбрано инициатором;
**11.10.2026** он подтвердил `banking_knowledge` основным доменом общей интеграции.
Конкретный протокол ниже остаётся предложением. Связь с исследовательским
вопросом и ограничения проекта: [постановка](research.md).

Дополнительная проверка **11.10.2026**: [ресурсная оценка](resource-assessment.md)
сопоставляет исходный τ-bench, исторический τ² и текущий τ³, закрепляет новый
commit 4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699 и оценивает собственный датасет
решений. Числа стандартных доменов ниже подтверждены и на новом commit;
500 retail train исходного τ-bench не являются train-разбиением τ³.

## Что проверено

Прочитаны первичные научные источники, документация и исходники
`sierra-research/tau2-bench`. Аудит данных и кода привязан к commit
**`5bfa7e37b36656b37dc6d022156be6563c1007f3`**, версия пакета **1.0.1**.
132 выбранных файла скачаны по этому commit; их содержимое сверено с Git
blob SHA из публичного дерева GitHub. Код бенчмарка не исполнялся,
зависимости не устанавливались, платные вызовы не выполнялись.
Это статическая проверка интеграции, а не подтверждение работающего harness.

## Семейство и состав

- Исходный τ-bench: retail и airline, диалог с LLM-пользователем,
  инструменты, политика домена и проверка результата.
- τ²-bench: добавляет telecom и взаимодействие, при котором пользователь
  тоже может менять состояние среды своими инструментами.
- τ³-bench: текущий зонтичный релиз в репозитории `tau2-bench`;
  добавляет τ-knowledge / `banking_knowledge`, голосовой трек и исправления.
  Наше предложение касается текстового режима.

Числа ниже получены из файлов указанного commit, не из старых leaderboard:

| Домен | Стандартный набор | Дополнительные разбиения |
| --- | ---: | --- |
| airline | 50 | train 30 / test 20 |
| retail | 114 | train 74 / test 40 |
| telecom | 114 | train 74 / test 40; small 20; full 2 285 |
| banking_knowledge | 97 | Отдельный train/test loader не зарегистрирован |

Итого — 375 задач в этих четырёх стандартных наборах. `mock` служит для
отладки. Разбиения первых трёх доменов взяты из `split_tasks.json`;
97 banking-задач — отдельные `tasks/task_*.json`, которые читает загрузчик.
Файл с наибольшим числом записей нельзя автоматически считать стандартным
набором: telecom `full` отличается от `base`.

В банковском корпусе **698 JSON-документов**. Статья v1 описывает 21 категорию
и 194 562 токена при `cl100k_base`. Это синтетический банковский мир:
продукты, правила и документы строились с участием LLM, задачи и эталоны
проверялись людьми. Это не выгрузка реальных клиентских обращений.
Источник статистики и процедуры создания — [статья τ-knowledge][knowledge-paper].

Агент работает с начальным состоянием БД, общими инструкциями и доступными
инструментами. Он должен искать регламенты и описания дополнительных функций,
открывать обнаруженные инструменты, согласовывать действия с пользователем
и выполнять операции. Примеры классов задач: обслуживание карт, спорные
транзакции, реферальные операции, условия счетов, передача обращения человеку.
Часть действий выполняет LLM-симулятор пользователя.

### Оценивание

Подсчёт `evaluation_criteria.reward_basis` для 97 banking-задач:

| Основание награды | Задач |
| --- | ---: |
| Только `DB` | 87 |
| Только `ACTION` | 9 |
| `DB` вместе с `NL_ASSERTION` | 1 |

`DB` сравнивает конечное состояние с эталоном, полученным воспроизведением
референсных действий. В banking в состоянии также есть служебные записи
о части вызовов: это шире, чем только бизнес-поля счетов. `ACTION` проверяет
наличие совпадающих вызовов по имени и проверяемым аргументам; текущий код
не требует буквального совпадения всей последовательности и порядка.
`NL_ASSERTION` использует LLM-оценку. Поэтому весь knowledge-набор нельзя
называть исключительно детерминированной проверкой конечного бизнес-состояния.
См. [документацию оценивания][evaluation] и [ActionEvaluator][action-evaluator].

`pass^k` характеризует успех во всех k повторах. Оценка для задачи с n
прогонами и s успехами: `C(s,k) / C(n,k)`, затем усреднение по задачам.
Это отличается от `pass@k`, означающего хотя бы один успех.
Источник — [реализация метрик][metrics].

В задаче есть `required_documents`, но это эталон для задачи целиком,
а не готовая разметка каждого поискового запроса, шага или вероятности.
Референсная траектория также не задаёт единственное правильное действие
во всех достижимых состояниях. Автоматическую разметку промежуточных решений
потребуется отдельно обосновать.

## Научный статус

| Компонент | Подтверждённый источник |
| --- | --- |
| τ-bench | [Статья в proceedings ICLR 2025][tau-iclr] |
| τ²-bench | Присутствует в [официальной программе ICML 2026][icml] |
| τ-knowledge | Присутствует в [официальной программе ICML 2026][icml]; доступна [статья][knowledge-paper] |
| Внешняя академическая оценка | [HAL, Princeton][hal] включает TAU-bench Airline; работа HAL — ICLR 2026 |
| Критический аудит | [SABER][saber] исследует ошибки заданий и уточняет проверку |

Вывод обзора: семейство имеет подтверждённое научное признание и подходит
как основа исследования. У нового knowledge-домена короче история применения,
чем у исходных airline/retail. Не следует переносить признание семейства
на утверждение о безошибочности конкретной версии или о полноте покрытия
реального обслуживания клиентов. Число цитирований не верифицировалось.

Поставщики моделей также используют τ-bench: например,
[Anthropic в феврале 2025][anthropic] раскрывает изменения scaffold и лимита
шагов. Это подтверждает практическое применение, но не заменяет независимые
измерения и не делает результаты с разными настройками сопоставимыми.

## Подключение собственного harness

Официально поддержан [интерфейс HalfDuplexAgent][agent-guide]:

- конструктор получает `tools` и `domain_policy`;
- `get_init_state(message_history)` создаёт состояние;
- `generate_next_message(message, state)` возвращает `AssistantMessage`
  и новое состояние;
- вход включает `UserMessage`, `ToolMessage`, `MultiToolMessage`;
- фабрика регистрируется через `registry.register_agent_factory`,
  после чего используются штатные runner и evaluator.

Внутри адаптера допустимы собственные вызовы моделей, маршрутизация,
контекст и планирование. Вызовы инструментов среды должны проходить через
стандартный цикл исполнения и попадать в траекторию. Нельзя подменять
пользователя, эталоны или проверку ради улучшения результата.
Примеры upstream: `minimal_text_agent.py`, `react_agent.py`,
`custom_agent_eval.py` в [examples/agents][examples].

Для reranking есть [BasePostprocessor][postprocessor] и реестр обработчиков:
`process(results, input_data, state)` возвращает пары ID документа и оценки.
Однако стандартный domain builder при включении reranker выбирает
`pointwise_llm_reranker` явно. Собственный обработчик нужно подключить
в построение pipeline; одного нового имени в CLI недостаточно.
См. [retrieval.py][retrieval-code].

**Граница после уточнения 11.10.2026:** механизм BasePostprocessor выше описывает
возможность upstream, а не разрешение менять native retrieval в основной серии.
Для текущего предложения сохранить штатные tools, среду и оценивание, обернуть
наш контроллер в HalfDuplexAgent и отбирать уже полученные доказательства
внутри agent harness, сохраняя исходные наблюдения. KEV/Laya — кандидаты для
выбранных узлов; Jev исключён. Одного изменения имени `agent-llm` недостаточно
для превращения типизированной модели в полноценного диалогового агента.
[Карта общей интеграции](README.md#wayfinder-system-one).

### Практические ограничения

1. **Стоимость.** `get_cost` складывает стоимость сообщений траектории
   и пропускает `ToolMessage`. Внутренний router, reranker, embeddings,
   повторные и отброшенные вызовы автоматически не покрываются этим счётчиком.
   В примере ReAct стоимость THINK не переносится в возвращаемый ACT.
   Для наших выводов нужен полный журнал вызовов и отдельный учёт агента,
   симулятора и оценивания. См. [код стоимости][cost-code].
2. **Задержка.** Полная `SimulationRun.duration` включает работу симулятора.
   Нужны отдельно время агента с инструментами и длительность всей симуляции;
   режим параллелизма фиксируется.
3. **Утечка эталона.** [build_agent][build-code] передаёт фабрике объект `task`
   для специальных режимов. Наш обычный harness не должен получать из него
   скрытые цели, `required_documents`, референсные действия или критерии.
4. **Разбиение.** Banking-загрузчик пока не использует `task_split_name`.
   Разделение настройки/калибровки и тестирования нужно задавать явными ID,
   желательно с группировкой похожих workflow. Повторы не заменяют новые задачи.
5. **Версия.** [Релиз 1.0.1 от 15.07.2026][changelog] изменил banking-оценивание;
   результаты до и после релиза напрямую несопоставимы.
6. **Leaderboard.** В текстовом треке собственный router, planner или
   изменённый scaffold относится к `custom`. Такая категория предусмотрена,
   требуется раскрыть методику и реализацию. Для локальной научной оценки
   предварительное согласование с авторами не нужно. Публикация результатов
   и внешняя отправка пока не поручены. См. [правила подачи][submission].

Python — `>=3.12,<3.14`; пакет и репозиторий объявляют MIT.
Для текстового BM25-варианта поиска не нужны embeddings API или shell sandbox;
LLM агента и пользователя при этом всё равно должны быть доступны.
`alltools` добавляет BM25, dense retrieval и sandboxed shell, поэтому требует
дополнительной настройки. Совместимость всего набора на нашем Mac ещё не
проверена запуском. См. [варианты retrieval][retrieval-guide].

<a id="native-context-pipeline-audit"></a>

## Проверка готовой системы retrieval и контекста — 11.10.2026

**Версия и метод.** Этот раздел — новая статическая проверка **только commit
`4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699`**, а не перенос выводов с `main`
или прежнего commit обзора. Закреплённая ревизия доступна по сети; 44 выбранных
файла retrieval, интерфейса агента и примеров документов скачаны во временный
каталог и сверены с Git blob SHA дерева этой ревизии. Проверка стандартного
LLMAgent выполнена параллельно; её первичные ссылки приведены ниже. Upstream,
модели и платные API не запускались, скрытые test-задачи не анализировались.
Источник вопроса и область работы — [Что уже делает native система retrieval и контекста?](README.md#wayfinder-native-context-pipeline).

**Короткий ответ:** готовая система есть. Она загружает отдельные KB-документы,
индексирует их, ищет и при выбранной конфигурации переранжирует. Поэтому Q3
«как нам самостоятельно нарезать документы по разделам/абзацам?» **преждевременно
предполагает необходимость нового splitter**. Но штатный retrieval не равен
выбранному нами отбору из накопленного наблюдаемого пула и упаковке под бюджет
KEV/Laya. Ниже отделены факты кода от предложения об интеграции.

### Native единица: подготовленный документ, не автоматически выделенный chunk

- `Document` содержит ровно поля `id`, `title`, `content`; `KnowledgeBase.load`
  читает отдельные `*.json`, создаёт один `Document` из каждого и кладёт его
  в словарь по ID. В этой схеме и загрузчике **нет parent/child chunks,
  offsets или runtime-разбиения текста**. Среда вызывает именно этот загрузчик:
  [schema/loader:10–52](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/data_model.py#L10-L52>),
  [environment:31–33](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/environment.py#L31-L33>).
- Это уже подготовленные тематические KB-единицы, но **не гарантированно короткие
  или равномерные фрагменты для любой модели**. Три публичных примера одной группы
  показывают и короткую инструкцию, и многораздельные процедуры. Локально посчитана
  длина декодированного `content` в символах Python `len(str)`, **не токенах**:

  | Пример native документа | Символов `content` | Наблюдение |
  | --- | ---: | --- |
  | [Opening Personal Checking Accounts:2–4](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/documents/doc_bank_accounts_bank_accounts_%28general%29_001.json#L2-L4>) | 677 | Условия допуска и процедура в одной единице |
  | [Opening Personal Savings Accounts:2–4](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/documents/doc_bank_accounts_bank_accounts_%28general%29_002.json#L2-L4>) | 4 737 | Несколько разделов, checklist и шаги |
  | [PIN Lock Investigation Protocol:2–4](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/documents/doc_bank_accounts_bank_accounts_%28general%29_041.json#L2-L4>) | 7 814 | Флаги, пороги, исключения и действия после проверки |

  Это иллюстрации неоднородности, не репрезентативная выборка и не измерение
  вместимости KEV/Laya. Нельзя объявлять весь корпус слишком длинным по этим
  примерам или считать любую native единицу готовым 512-токенным входом.
- Абстрактный `BaseDocumentPreprocessor` действительно **допускает** chunking
  как расширение. Однако зарегистрированы BM25- и embedding-indexers; в
  банковских builders подключены именно они, и оба возвращают исходный список
  документов. Наличие extension point не означает наличия готового splitter:
  [base:5–35](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/document_preprocessors/base.py#L5-L35>),
  [registration:15–23](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/__init__.py#L15-L23>),
  [builders:164–235](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py#L164-L235>).

### Что реально индексируется, оценивается и выдаётся

1. **Индексируемая запись:** `{"id": doc.id, "text": doc.content, "title": doc.title}`.
   BM25 берёт `text`, делает `lower().split()` и строит `BM25Okapi`; это
   токенизация целого документа, **не нарезка на новые единицы**. Заголовок хранится,
   но отдельно к индексируемому `content` не дописывается:
   [mapping:145–156](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py#L145-L156>),
   [BM25Indexer:27–45](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/document_preprocessors/bm25_indexer.py#L27-L45>).
2. **Dense:** тот же `content` отправляется на embedding целиком, с сохранением
   соответствия ID → вектор; batch означает группу документов, не chunks одного
   документа. Cosine retriever возвращает пары `(doc_id, score)`. Индексация не
   выделяет предложения и не создаёт короткие excerpts:
   [EmbeddingIndexer:69–125](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/document_preprocessors/embedding_indexer.py#L69-L125>),
   [CosineRetriever:28–45](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/retrievers/cosine_retriever.py#L28-L45>).
3. **Pipeline:** preprocessors → retriever(s) → объединение результатов по ID
   с максимальной оценкой → сортировка/необязательный срез → postprocessors.
   `doc_content_map` хранит полный текст. Объединение по ID действует **в одном
   retrieval-вызове**, а не является дедупликацией KB-наблюдений всего диалога:
   [index/maps:91–107](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/pipeline.py#L91-L107>),
   [retrieve:109–173](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/pipeline.py#L109-L173>).
4. **Ответ KB tool — строка, не список structured Document.** Formatter берёт
   найденные ID и печатает номер, title, ID, score, **полный `content`** и timing.
   Слово `excerpts` в docstring `KB_search` не подтверждает extraction: тело
   функции использует общий formatter без sentence/chunk selection. Отдельный
   native `grep` ранжирует документы по числу regex-совпадений и также печатает
   полное содержимое, а не только совпавшие строки:
   [formatter/KB_search:15–74](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_mixins.py#L15-L74>),
   [grep output:83–111](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_mixins.py#L83-L111>),
   [grep scoring:30–54](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/retrievers/grep_retriever.py#L30-L54>).

### Варианты и лимиты: `bm25` не тождественен default `alltools`

| Конфигурация | Штатное поведение на проверенной ревизии |
| --- | --- |
| `bm25` | Banking tools + `KB_search(query)`, без dense, shell и reranker; [registry:562–575](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py#L562-L575>), [toolkit:43–51](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_toolkits.py#L43-L51>) |
| `alltools` / `alltools-qwen` | Два независимых поисковых tool (`KB_search_bm25`, `KB_search_dense`) + read-only `shell`, не автоматическое слияние BM25+dense на каждом запросе. Первый — default; dense backend соответственно OpenAI `text-embedding-3-large` / OpenRouter `qwen3-embedding-8b`: [defaults:58–62](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py#L58-L62>), [factory:408–427](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py#L408-L427>), [variants:595–604](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py#L595-L604>) |
| `*_reranker` | Builder явно включает `pointwise_llm_reranker`, не BGE/Qwen: [builder:691–718](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py#L691-L718>). Дополнительный LLM оценивает целые найденные документы, затем фильтрует/сортирует их; новый текст или snippets не возвращает |
| `*_grep` | Добавляется отдельный tool `grep`; это не chunking и не обязательная стадия каждого KB-поиска: [toolkit:65–80](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_toolkits.py#L65-L80>) |

**Число документов, не токенный бюджет.** Banking `PipelineSpec.top_k=10`.
У `bm25` tool принимает только `query`, лимит задаётся конфигурацией pipeline;
`resolve_variant(top_k=...)` позволяет его переопределить. BM25 и cosine
ограничивают его сверху числом документов. BM25 без reranker не отбрасывает
нулевые оценки: непустой запрос может вернуть top-k даже без полезного совпадения.
[PipelineSpec:297–306](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py#L297-L306>),
[overrides:639–681](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py#L639-L681>),
[BM25:29–49](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/retrievers/bm25_retriever.py#L29-L49>),
[cosine:28–45](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/retrievers/cosine_retriever.py#L28-L45>).

**Нюанс `alltools.k`:** оба tools имеют `k=10`, но передают его в
`pipeline.retrieve(top_k=k)`, где срез делается **после** retrieval, не расширяя
его внутренний `top_k`. При настройках по умолчанию `k=20` не извлечёт 20
документов из retriever с лимитом 10. В проверенной цепочке нет нижнего clamp
для отрицательного `k`: применяется обычный Python slice. Это статический
вывод, не результат runtime-теста; в будущем пилоте надо проверять фактическое
число candidates, а не полагаться только на имя аргумента.
[AllTools mixins:114–145](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_mixins.py#L114-L145>),
[pipeline:126–147](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/pipeline.py#L126-L147>).

**Reranker — уже готовый doc scorer, не context packer.** Pointwise-класс
по умолчанию использует `gpt-5.2`, prompt «query + document», оценку 0–10 и
фильтрацию по порогу. Порог класса — 7, но banking builder передаёт
`PipelineSpec.reranker_min_score=5`; исключения отдельной оценки исключают
документ из результата. Сохранившимся ID formatter снова выдаёт полный текст.
Есть также зарегистрированные BGE/Qwen postprocessors с `top_k=5` по умолчанию;
они работают с теми же ID и полными текстами, просят API о правом усечении
входа (`truncate=True`) и возвращают doc scores. **Усечение входа scorer не
является извлечением snippets для action LLM.** Эти классы не выбираются одним
лишь суффиксом `*_reranker`:
[pointwise:13–125](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/postprocessors/pointwise_llm_reranker.py#L13-L125>),
[banking threshold:297–306](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py#L297-L306>),
[BGE:24–167](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/postprocessors/bge_reranker.py#L24-L167>),
[Qwen defaults:45–68](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/postprocessors/qwen_reranker.py#L45-L68>),
[Qwen scoring:123–221](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/postprocessors/qwen_reranker.py#L123-L221>).

**Shell — отдельный случай.** Sandbox экспортирует один полный файл на документ
и индекс имён; `shell` возвращает stdout команды. Поэтому агент может получить
только строки/часть файла, если такова команда. Это agent-driven доступ, не
скрытый native splitter: нельзя считать ID из списка файлов наблюдением полного
содержимого документа.
[export:323–387](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/sandbox_manager.py#L323-L387>),
[shell return:154–180](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_mixins.py#L154-L180>).

### История стандартного агента — не готовая упаковка накопленного KB-пула

У стандартного `LLMAgentState` есть `system_messages` и `messages`. На шаге
агент добавляет полученные сообщения tools (в том числе разворачивает
`MultiToolMessage`) и вызывает `generate` с `system_messages + messages`.
`generate` сериализует историю для LiteLLM и вызывает completion. В этой
проверенной цепочке **не найден автоматический KB-pooling, dedup, splitter или
токенный packer/evictor**. Это утверждение о стандартном пути этой ревизии, не
обо всех возможных custom agents и внешнем поведении провайдера:
[state:44–48](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/agent/llm_agent.py#L44-L48>),
[append/generate:105–135](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/agent/llm_agent.py#L105-L135>),
[serialization/completion:355–415](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/utils/llm_utils.py#L355-L415>).

Обнаруженный `RewriteContextMixin` не доказывает обратного: его тело только
возвращает `"Context updated:\n\n{new_context}"`; конкретные банковские toolkits
не включают этот mixin. Он не реализует замену истории стандартного агента.
[rewrite_context:183–199](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_mixins.py#L183-L199>),
[toolkit composition:19–112](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_toolkits.py#L19-L112>).

### Следствие для варианта А и переформулировка Q3 — предложение, не новый выбор

**Последующее согласование 11.10.2026:** инициатор подтвердил принцип Q3 —
переиспользовать native записи, измерить полный вход и дополнительно делить
только при обоснованной необходимости. [Запись согласования](README.md#wayfinder-context-contract).
Ниже сохранены выводы и предложения аудита; конкретный splitter и остальные
инженерные детали не стали утверждёнными автоматически.

**Переиспользуем native retrieval как есть.** Возможность вставить собственный
`BasePostprocessor` существует, но это вмешательство внутрь retrieval среды,
а не выбранная граница. Для неизменных tools/corpus/evaluator логичный узел —
собственный `HalfDuplexAgent`: он получает `ToolMessage`/`MultiToolMessage`,
ведёт состояние и выдаёт обычный `AssistantMessage`.
[postprocessor contract:16–33](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/knowledge/postprocessors/base.py#L16-L33>),
[agent interface:28–73](<https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/agent/base_agent.py#L28-L73>).

Предлагаемая организация harness, **не утверждённая реализация**:

1. Не менять ответы среды и исходную траекторию; отдельно накапливать **только
   реально увиденный** KB-текст текущего диалога с provenance: сообщение/tool,
   native document ID, при необходимости границы видимого фрагмента. Ранее
   не выбранные наблюдения остаются в пуле; недоступные части по ID не дочитываются
   напрямую из corpus. Для `shell` нужен отдельный контракт provenance.
2. Native короткую KB-единицу можно рассматривать как готовый фрагмент-кандидат
   без обязательного дополнительного разреза. Если полный вход конкретного
   scorer не помещается, отдельно проверить обоснованную сегментацию наблюдаемого
   текста, сохраняя заголовок, ID и связанные условия/исключения. В частности,
   разрыв eligibility и procedure из примеров выше способен потерять условие,
   даже если каждый кусок короче. Метод/размер splitter ещё не согласован.
3. System One scorer → context packer → accept/defer **того же отбора** LLM
   над тем же разрешённым пулом → обычный action LLM. Для scorer, селектора
   и action LLM зафиксировать разные входные бюджеты и overflow. Native `top_k`
   ограничивает число извлечённых документов, но не решает эти бюджетные задачи.
4. Сохранять **raw transcript отдельно от производного model view**. Если просто
   дописать отобранные chunks к истории, оставив в модельном входе все исходные
   KB tool results, контекст не уменьшится. Проекция должна исключать повторную
   передачу невыбранного KB-текста, не искажая policy, наблюдаемые бизнес-факты,
   подтверждения пользователя и структуру tool-call/result сообщений. Это
   инженерное следствие описанного выше пути LLMAgent, а не готовая native функция.

**Q3 лучше сформулировать так:** «Какие уже полученные native KB-единицы можно
переиспользовать без дополнительной нарезки как кандидаты накопленного пула?
Для каких единиц подтверждён overflow полного входа выбранного KEV/Laya и нужна
дополнительная сегментация — с какими границами, provenance и сохранением
зависимых условий? Как отобранный набор заменяет KB-часть model view, не меняя
native tools, корпус и evaluator?» Это сохраняет
[выбор фрагментов и накопленного пула](README.md#wayfinder-context-contract),
но не подменяет его ещё не принятым решением «режем всё по абзацам».

**Что остаётся неизвестным:** реальные длины полного входа с tokenizer каждой
модели, доля overflow, пригодность конкретных native единиц и дополнительного
splitter, частота дублей/повторного использования, схема выделения KB из строковых
tool returns, достаточность наборов, качество/стоимость/latency и runtime-поведение
лимитов. Это будущий малый пилот, не вывод из среднего размера корпуса.
Наличие retrieval/reranker инфраструктуры подтверждено; преимущество нового
packer/scorer и экономия варианта А пока **не измерены**. Native `*_reranker`
оценивает текущую выдачу поиска; для честного сравнения с нашим селектором
накопленного пула нужны одинаковые наблюдаемые candidates и бюджет, а не только
одинаковое название scorer. Если для пилота выбирается `bm25`, его следует явно
отличать от upstream-default `alltools`; конфигурацию фиксируют, не меняют между ветвями.

## Рекомендация и следующий этап

Оценка сложности: адаптер агента — небольшая инженерная задача; собственный
retrieval — умеренная; корректный сравнительный эксперимент — основная работа.
Начать с короткой проверки стандартного агента и адаптера на retail, затем
пилота `banking_knowledge` с одним фиксированным retrieval. Выделять основной
узел после проверки его доли в ошибках и затратах. Для сравнения методов
reranking сохранять исходного кандидатообразователя и одинаковый бюджет.

Основной стенд `banking_knowledge` подтверждён инициатором 11.10.2026;
retail остаётся вспомогательным доменом для отладки и возможной проверки переноса.
Порядок baseline → один узел → расширения пока рекомендован, не выполнен.
Полная серия из четырёх вариантов на 97 задачах с четырьмя повторами —
1 552 диалога, не 1 552 модельных вызова. Денежную оценку можно получить
из малого пилота; бюджет API пока не определён.

Самопроверка обзора: научные статусы сверены с первичными площадками,
числа задач и основания награды пересчитаны, скачанные файлы сверены с Git
blob SHA. Независимого человеческого review и проверки runtime ещё не было.

[tau-iclr]: https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html
[icml]: https://icml.cc/Downloads/2026
[knowledge-paper]: https://arxiv.org/html/2603.04370v1
[hal]: https://hal.cs.princeton.edu/
[saber]: https://assets.amazon.science/74/ec/867848fa44bda73d6237dfd6183d/saber-tau-bench-verified.pdf
[anthropic]: https://www.anthropic.com/news/claude-3-7-sonnet
[evaluation]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/docs/evaluation.md
[action-evaluator]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/src/tau2/evaluator/evaluator_action.py
[metrics]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/src/tau2/metrics/agent_metrics.py
[agent-guide]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/src/tau2/agent/README.md
[examples]: https://github.com/sierra-research/tau2-bench/tree/5bfa7e37b36656b37dc6d022156be6563c1007f3/examples/agents
[postprocessor]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/src/tau2/knowledge/postprocessors/base.py
[retrieval-code]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/src/tau2/domains/banking_knowledge/retrieval.py
[cost-code]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/src/tau2/utils/llm_utils.py
[build-code]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/src/tau2/runner/build.py
[changelog]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/CHANGELOG.md
[submission]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/docs/leaderboard-submission.md
[retrieval-guide]: https://github.com/sierra-research/tau2-bench/blob/5bfa7e37b36656b37dc6d022156be6563c1007f3/src/tau2/knowledge/README.md
