---
node_type: reference
title: Выбор действий в τ-bench при ограниченном контексте
service: _platform
status: draft
updated: 2026-10-11
links:
  relates_to: [docs/gitmark/architecture.md, docs/gitmark/resource-assessment.md, docs/gitmark/rlcd-study-plan.md]
---

# Выбор действий в τ-bench при ограниченном контексте

**Статус:** статический аудит первичных исходников и собственное измерение
токенизации policy; не inference/training benchmark и не утверждённая тема ВКР.
Проверен `sierra-research/tau2-bench`, текущий τ³, commit
`4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699`; дата проверки — 11.10.2026.
Область: текстовый half-duplex агент, прежде всего `banking_knowledge`.
Веса не скачивались, зависимости не устанавливались, upstream и платные
вызовы не запускались. Скрытые цели задач не использованы для примеров: ниже
нет реконструкции банковских test-сценариев.

Контекст: [T-node и E2](<architecture.md>),
[ресурсные ограничения](<resource-assessment.md>),
[план исследования](<rlcd-study-plan.md>). Это уточнение контрактов стенда;
выбор моделей и подробный план обучения здесь не утверждаются.

## 1. Что является следующим действием

В обычном `LLMAgent.generate_next_message` модель получает policy, доступные
схемы tools и историю, после чего **одним генеративным вызовом** возвращает
`AssistantMessage`. Вызов `generate` получает одновременно `messages` и
`tools`: upstream не выделяет отдельный обязательный классификатор имени.
Возвращённое сообщение добавляется в историю. [LLMAgent][agent]

| Уровень | Фактический контракт |
| --- | --- |
| Реплика | `AssistantMessage.content`: текст пользователю, без tool calls |
| Один вызов | `AssistantMessage.tool_calls = [ToolCall(name, arguments, id, requestor)]`; `arguments` — словарь |
| Несколько вызовов | Тот же `AssistantMessage`, но список из нескольких `ToolCall`; это не отдельный тип выходного `MultiToolMessage` |
| Результаты | Один `ToolMessage` либо входной `MultiToolMessage(tool_messages=[...])`; агент разворачивает пакет в историю |

Правила half-duplex оркестратора требуют **текст или tool calls**, не оба
одновременно. Он поддерживает несколько вызовов в одном сообщении, но
`_execute_tool_calls` исполняет их **последовательно циклом**, а не обещает
параллельный runtime. Поэтому единственный class ID имени не описывает всё
пространство native next-message. [Схемы сообщений][messages],
[оркестратор][orchestrator]

Следствия для постановки:

- Выбор `respond` не генерирует правильный ответ: нужна отдельная генерация
  реплики, включая уточнение, объяснение, отказ или завершение обращения.
- Выбор имени не определяет аргументы, необходимые наблюдения и соблюдение
  policy. JSON-validity также не доказывает правильность действия.
- Multi-tool нельзя молча удалить только у исследуемого метода. Для узкого
  опыта допустим общий single-call режим, явно отличный от native режима;
  либо общий `defer` к native агенту для сложного решения.
- В `banking_knowledge` solo-режим не поддерживается; убрать диалог с
  пользователем — не штатный способ упростить этот домен. [Environment][environment]

## 2. Что видно агенту: banking tools

`ToolKitBase.get_tools()` исключает `@is_discoverable_tool`. Такие функции
существуют в среде, но их определения не включаются в исходный список
схем агента. Это **discoverable**, а не секретные функции вне области задачи:
агент должен узнать о них через KB. [Toolkit][toolkit]

В `KnowledgeTools` проверенного commit **14 обычных tools**:

- `transfer_to_human_agents`, `get_current_time`;
- `get_user_information_by_id`, `get_user_information_by_name`,
  `get_user_information_by_email`, `change_user_email`;
- `get_referrals_by_user`, `get_credit_card_transactions_by_user`,
  `get_credit_card_accounts_by_user`, `log_verification`;
- `give_discoverable_user_tool`, `unlock_discoverable_agent_tool`,
  `call_discoverable_agent_tool`, `list_discoverable_agent_tools`.

Отдельно объявлены **44 discoverable agent tools**, включая учебный
`example_agent_tool_0000`: операции с транзакциями, спорами, счетами,
кредитными лимитами и картами. Это инвентаризация реализации, **не 44
дополнительных кандидата, разрешённых селектору с первого шага**. В отдельном
`KnowledgeUserTools` — 6 обычных и 4 discoverable функции пользователя;
они не становятся прямыми инструментами agent-роли. [Banking tools][tools]

Retrieval добавляет схемы к этим 14, а не заменяет их:

| Вариант | Дополнительные видимые tools | Всего исходно |
| --- | --- | ---: |
| `bm25` | `KB_search(query)` | 15 |
| `bm25_grep` | `KB_search(query)`, `grep(pattern)` | 16 |
| `terminal_use` | `shell(command)` | 15 |
| default `alltools` | `KB_search_bm25(query, k=10)`, `KB_search_dense(query, k=10)`, `shell(command)` | 17 |

Default `alltools` использует OpenAI `text-embedding-3-large`; `bm25` —
отдельное объявленное условие без этого dense backend. Не путать «все
retrieval tools» с раскрытием всех discoverable domain tools.
[Registry][retrieval], [состав toolkit][composed], [retrieval tools][mixins]

## 3. Поиск, открытие описания и исполнение — разные шаги

1. **Найти сведения в KB.** `KB_search` возвращает title, document ID, score
   и **полный content** найденного документа: слово excerpts в docstring
   не означает, что реализация отдаёт только короткий snippet. `grep` тоже
   возвращает полное содержимое. В shell-варианте есть отдельное чтение
   найденного файла и индекс документов; это не универсальный `open_tool`.
   [Retrieval mixins][mixins], [shell policy][shell-policy]
2. **Открыть agent tool.** По явно найденному имени вызвать
   `unlock_discoverable_agent_tool(agent_tool_name)`. Ответ содержит
   описание и параметры, разобранные из docstring. Имя сохраняется во
   внутреннем unlocked-state. Это не добавление новой top-level схемы
   в список `LLMAgent.tools`. [Banking tools][tools]
3. **Исполнить.** Вызвать `call_discoverable_agent_tool(agent_tool_name,
   arguments)`, где внутренние аргументы передаются **JSON-строкой**,
   хотя внешние `ToolCall.arguments` — словарь. Dispatcher проверяет
   существование функции и предварительный unlock, разбирает JSON и
   вызывает функцию. Неверные имя/JSON/аргументы дают сообщения об ошибке.
   [Banking tools][tools]
4. **Пользовательское действие.** `give_discoverable_user_tool` выдаёт
   функцию пользователю; затем пользовательская сторона использует
   `call_discoverable_user_tool`. Это не agent-вызов той же операции.
   [Banking tools][tools], [additional instructions][additional]

`list_discoverable_agent_tools()` — **не поиск по полному каталогу** и даже
не перечень всех unlocked. Он читает журнал уже вызванных функций в БД.
Некоторые дополнительные read-only вызовы туда не логируются: реализация
учитывает mutating-функции и отдельный read allowlist оценщика. Unlock
сохраняет состояние в памяти, запись в БД происходит при call согласно
этому правилу. Не использовать внутренний allowlist как признак модели.
[Banking tools][tools], [Environment][environment]

Policy требует искать имена в KB, не угадывать их, не открывать инструменты
«про запас» и получить описание параметров до вызова. Код dispatcher
проверяет unlocked-state, но не доказывает, что имя действительно найдено
разрешённым способом. Значит, доступность по API и policy-correctness —
разные свойства. [Additional instructions][additional], [Banking tools][tools]

**Уточнение к архитектурному shorthand:** в текущем commit агент вызывает
`call_discoverable_agent_tool(agent_tool_name, arguments)`, а не
`call_discoverable_tool(name, kwargs)`. Для содержательного T-node полезны
наблюдаемые варианты `unlock:<имя>` / `call:<имя>`: иначе все специализированные
операции схлопнутся в один ID dispatcher, а выбор настоящего tool останется
скрыт в генерации его аргументов. Такое расширение ID — **наша факторизация**,
не новая схема upstream; снаружи нужно восстановить точный native вызов.

## 4. Доступная информация и реальный объём контекста

Для обычного агента допустимы policy выбранного retrieval-варианта,
выданные схемы, префикс разговора и собственных вызовов, полученные ответы
tools, фактически найденные KB-документы и возвращённые при unlock описания.
Текст policy содержит общие ограничения и идентификацию клиента;
специфические процедуры лежат в KB, а не обязательно в коротком заголовке.
[LLMAgent][agent], [policy header][header], [additional instructions][additional]

В селектор нельзя передавать скрытое состояние БД, будущие реплики,
инструкции user simulator, `evaluation_criteria`, gold actions и
`required_documents`. Наличие отдельного `LLMGTAgent`, которому специально
показывают resolution steps, не делает такой вход допустимым обычному
агенту. `golden_retrieval` тоже отдельный привилегированный режим: он
подставляет `task.required_documents`, в отличие от standard prompt.
[LLMAgent / GT agent][agent], [prompt builders][retrieval]

Ниже **статический собственный подсчёт текста источников**, не токены и
не измерение памяти. Policy собрана заменой component placeholders, как
в `load_prompt_template`; для alltools подставлена строка default OpenAI
backend. Chars — длина строки, words — разбиение по пробельным символам.
Для docstrings убраны пробелы по краям каждой строки, описания соединены
двумя переводами строки. Включены Args/Returns; Python-реализация исключена.

| Текст | Chars | Words |
| --- | ---: | ---: |
| Общий `policy_header` | 1779 | 298 |
| `additional_instructions` | 3816 | 608 |
| Собранная policy `bm25` | 5734 | 924 |
| Собранная policy default `alltools` | 7541 | 1222 |
| Docstrings 14 обычных banking tools | 3832 | 605 |
| Docstring `KB_search` | 163 | 23 |
| Docstrings всех 44 discoverable agent tools | 19967 | 2661 |

Источники подсчёта: [header][header], [additional][additional],
[BM25 template][bm25-policy], [AllTools template][all-policy],
[tools][tools], [mixins][mixins]. Полный исходник tools прочитан по raw HTTP
(189255 chars); ограниченный ответ `web_fetch` в 100000 chars не использован
для полного инвентарного подсчёта. Код upstream не импортировался.

Это **не готовый размер модельного запроса**: здесь нет сериализованных
JSON Schema, имён/типов параметров сверх docstring, system wrapper,
истории, tool results и выбранных KB-документов. Описания 44 функций
приведены только как инвентарный объём — их нельзя загрузить агенту заранее.
Даже короткий набор policy + первоначальные описания не доказывает
помещение в маленькое окно: токенизацию надо измерять конкретным tokenizer
на фактическом сериализованном входе. Автоматическая обрезка значимых
условий policy не является корректной компрессией.

## 5. Reference actions не дают единственную метку next step

Upstream прямо определяет `evaluation_criteria.actions` как **одну reference
trajectory**. Для DB-оценки она проигрывается в gold environment, чтобы
получить целевое конечное состояние. Иная последовательность может
привести к эквивалентному состоянию и пройти проверку. Итоговый reward
зависит от `reward_basis`; совпадение actions требуется, когда включён
`ACTION`, а не автоматически у всех задач. [Evaluation documentation][evaluation]

Даже `ActionEvaluator` проверяет для каждой эталонной записи наличие
совпадающего вызова **где-либо среди предсказанных tool calls**. Этот код
не задаёт единственный следующий шаг или обязательный порядок: цикл
`gold_action → predicted_tool_calls` использует `compare_with_tool_call`.
Поэтому нельзя превратить этот список в universally correct next-action
labels простым сдвигом на один шаг. [Action evaluator][action-evaluator]

Для узловой диагностики различать:

- совпадение с конкретной демонстрацией;
- принадлежность допустимому множеству следующих действий при данном
  наблюдаемом префиксе — требует отдельной проверенной разметки;
- сквозной успех по native evaluator.

Отсутствие вызова в reference не доказывает ошибку; высокий native reward
также не является исчерпывающим аудитом соблюдения всех текстовых правил.
Нельзя автоматически объявлять альтернативные поиски, уточнения или
порядки read-only проверок отрицательными примерами.

## 6. Узкая выполнимая постановка вместо validity gate

**Предложение, уже согласованное по структуре с T/E2, не принятое решение:**
выбирать **одно следующее намерение/имя** из наблюдаемого динамического
набора плюс `respond` и технический `defer`; фиксированная генеративная
модель затем заполняет аргументы либо пишет реплику. Для discoverable
ветки варианты включают только имена, реально найденные/открытые ранее,
с provenance до ответа поиска или unlock. Не оценивать validity готового
LLM-вызова под видом самостоятельного выбора действия.

На первом пилоте разумен `banking_knowledge + bm25`, без одновременного
исследования выбора retriever и без заранее раскрытого каталога. Область
single-call/multi-call, упаковка состояния и overflow/fallback должны быть
одинаковыми у сравниваемых селекторов. Это не обещание, что весь banking
превратится в короткую независимую классификацию.

Минимальные контроли, продолжающие [E2](<architecture.md>):

1. **Native joint LLM:** имя + аргументы/реплика в штатном вызове; исходная
   точка отсчёта системы, с явно зафиксированным multi-tool режимом.
2. **Факторизованная LLM:** LLM выбирает имя/намерение → та же фиксированная
   модель генерирует аргументы/реплику. Отличие от №1 показывает эффект
   факторизации и дополнительного вызова, не преимущество маленькой модели.
3. **Дешёвый селектор + тот же generator:** сравнение с №2 на **одинаковом
   состоянии, кандидатах и бюджете** выделяет замену селектора. Правила
   или лексический baseline — содержательный дешёвый контроль.
4. **Полный против ограниченного контекста у LLM:** отдельная абляция
   упаковки контекста. Полная LLM против урезанной маленькой модели —
   сравнение целых систем, не чистый эффект архитектуры селектора.

Ошибки выбора имени, аргументов, retrieval/discovery и ответа учитывать
раздельно; вывод о полезности делать по полному диалогу, стоимости всех
вызовов, retries/fallback и задержке, а не только по точности ID. Модели,
обучение и объём разметки уточняются в следующих разделах как предложения,
а не проведённые модельные эксперименты.

## 7. Реально измеренный размер policy в токенах

**Наше собственное статическое измерение 11.10.2026**, не оценка «символы / 4».
Использован установленный tokenizers 0.22.1, загружены только tokenizer JSON
и тексты policy по закреплённым версиям. Веса, Transformers-модели и upstream
не запускались; новых зависимостей не устанавливалось.

| Policy без tools и истории | Laya English tokenizer | Laya multilingual tokenizer | KEV / Qwen3.5 tokenizer |
| --- | ---: | ---: | ---: |
| Retail | 1527 | 1452 | 1454 |
| Airline | 1745 | 1698 | 1690 |
| Banking, BM25 | 1267 | 1241 | 1186 |

Retail/airline — исходный текст policy; banking — literal substitution двух
component placeholders в [BM25 template][bm25-policy], без task-specific gold.
Использованы tokenizer.no_truncation(), no_padding() и encode(text,
add_special_tokens=False). Не включены JSON Schema tools, история, найденные
документы, query/options, chat/model wrappers и специальные токены. Поэтому
это **не полный размер рабочего запроса**, а размер одного необходимого компонента.

**Вывод:** полные правила уже не помещаются в Laya English512 или typed1024.
Числа не доказывают достаточность любого окна 8k для полного эпизода: история,
аргументы и retrieved evidence ещё добавятся. Замеры throughput/accuracy не делались.

### Источники и воспроизведение измерения

- [Retail policy][retail-policy], SHA256 2c9652afbce57d6e087768d37cda64d31c53d50b3e3225cfdb791bac66466467.
- [Airline policy][airline-policy], SHA256 10dc0525421521208be39cee235bba84a16e2bcba9899eb93d92cd81d2f62fc4.
- [Banking template][bm25-policy], SHA256 84ac1a68e0ca59f4cb870faf124202887e7e4f2e92dbd4d62c78ad2bcbb16d3b.
- [Header][header], SHA256 d73a0578670becb80b7c1a57cdbe68a2ea506a884cdf41e2e310dd3c13e63a85.
- [Additional instructions][additional], SHA256 03f6af1b56aa2fa6543ee4883ea9979ac5f5e158b20dd32d91d9736de87bab6a.
- [Laya English tokenizer][tok-en], SHA256 6c8aaa9a542084f2457eab775d4eeb51f92a70c0fd9de28d5edb0ddec3c08d30.
- [Laya multilingual tokenizer][tok-multi], SHA256 609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f.
- [Qwen3.5 tokenizer][tok-kev], SHA256 fe000e3ed39ed12b8d2481d527d44f93c65d37e87645d2dcc80d1bf9d50d2927.

Ниже ядро воспроизведения. Аргументы — полные UTF-8 строки по ссылкам выше;
SHA256 сверяется до вычисления. Загрузка выполнялась curl с проверкой TLS
в память; усечённые ответы web_fetch не использовались для токенизаторов.

~~~python
from tokenizers import Tokenizer

def count_policy(tokenizer_json, policy_text):
    tokenizer = Tokenizer.from_str(tokenizer_json)
    tokenizer.no_truncation()
    tokenizer.no_padding()
    return len(tokenizer.encode(policy_text, add_special_tokens=False).ids)

def assemble_banking(template, header, additional):
    text = template.replace("{{component:policy_header}}", header)
    text = text.replace("{{component:additional_instructions}}", additional)
    assert "{{component:" not in text
    return text
~~~

## 8. Ограничения конкретных моделей

| Кандидат | Реальный режим контекста | Следствие для выбора действия |
| --- | --- | --- |
| Laya English | Config max_len512, head_max_len192 | Не baseline полного native состояния; только явно компактный вид |
| Laya typed-decisions | 1024 / 256 | Полная policy из измерения не помещается ещё до истории |
| Laya multilingual | Default1024 / 256; explicit max_len8192 поддерживается | Кандидат для длинного пилота, не доказанная политика τ-bench |
| KEV-0.8B | Cards validated8192; serving state65536, row73728 | Окно полезнее, но автор прямо не рекомендует tool-call routing |
| KEV-4B | Те же validated8192 / serving limits | Более обоснованный routing-кандидат; длинный serving cap не доказывает качество |

Источники: [English config][cfg-en], [typed config][cfg-typed],
[multilingual config][cfg-multi], [KEV0.8 card][kev08-card], [KEV4 card][kev4-card].
Повышение max_len само по себе не создаёт проверенного навыка работы с длинными
политиками. Авторский multilingual long-context probe — 20 department-routing
запросов, 4 варианта и искусственный filler; при 7k filler 8/20 правильных.
Это не оценка многоходового tool use. [Скрипт][laya-long-script], [результаты][laya-long].

### Options тоже расходуют контекст, и иногда обрезаются

Laya упаковывает head (вопрос/варианты) **перед** state. Реальное место state:

$$
B_{state}=\max(0,\; max\_len-|head|-1).
$$

Поэтому «состоянию всегда остаётся 320/768 токенов» — не точное правило.
Option text сначала обрезается до 48 токенов. При нехватке head budget
span варианта вместе с MASK получает cap max(4, floor((head_max_len−16)/K)).
Инструкция сохраняет минимум 8 токенов, поэтому head_max_len **не жёсткий
потолок**. При большом K head может превышать его. [Упаковка][laya-pack].
В str/dict сохраняется начало state, в list — конец; это обрезка, не summary.
Usage сообщает dropped state и проблемы options. Если markers не помещаются,
возникает ошибка. Записывать truncation telemetry; не считать штатную обрезку
доказательством, что модель получила необходимые факты. [Runtime][laya-trunc].

HTTP Laya допускает до100 choice options, KEV — до255; **это API-лимиты, не
доказанная точность среди стольких вариантов**. У Laya при большом K особенно
важны смысл обрезанных описаний и различимость labels. KEV production по
умолчанию отклоняет oversized state; явный truncate сохраняет начало,
слишком длинная row отклоняется всегда. [Laya API][laya-api], [KEV pack][kev-pack].

### Что известно о пригодности к routing

- **KEV0.8:** When2Call dev0.167 / test0.133 против four-way chance0.25;
  model card: «Do not use it for tool-call routing». Поэтому оставить его как
  дешёвый/отрицательный контроль или объект явно отдельной адаптации, не как
  основной готовый router. [Проверенная карточка][kev08-card].
- **KEV4B:** When2Call **dev0.660** — реальное узкое основание для пилота,
  а не аргумент «предупреждения нет». Это не test и не полный τ-bench с args.
  [Карточка][kev4-card].
- Laya support/domain/model routing и headline typed-decisions accuracy не
  являются τ-action-selection результатом. В проверенных источниках не найден
  готовый τ-bench результат этих checkpoints; обзор не претендует на полный
  citation search. [Laya benchmarks][laya-bench].

Порядок вариантов влияет на обе семьи. У KEV confidence нормирован относительно
1/K, у Laya confidence и answer_confidence различаются. Для calibration брать
документированные вероятности и явно выбранное событие, не один универсальный
порог для разных K/checkpoints. K также меняет мягкое распределение и фактическую
упаковку Laya. [KEV API][kev-api], [Laya benchmarks][laya-bench].

## 9. Контракт общего узла; не личная тема RLCD

**Актуальная граница после уточнений инициатора 11.10.2026:** выбор действий
и представления контекста проектируется для общей платформы, а не становится
самостоятельной личной темой инициатора. Его направление — **адаптация модели**;
RLCD против обучения без RL — возможное уточнение после общей схемы, не уже
обязательный выбор. [Согласованные направления](research.md#согласованные-направления-трёх-исследований),
[условный RLCD-план](rlcd-study-plan.md).

Ниже сохранён предложенный технический контракт T/E2 общего стенда вместо
verifier. Он пока предусматривает генератор после selector. Разрешение
инициатора пропускать LLM на подходящих шагах открывает отдельную развилку
[карты](README.md#wayfinder-decision-contract), но ещё не утверждает fast path.
Следующее поручение инициатора — проработать именно [варианты полного вызова](complete-call-options.md):
контракт ниже сохраняется как контроль name-only → generator, а не итоговая
схема сокращения LLM-вызовов. Работа с контекстом и сравнение архитектур не становятся обязательной
личной исследовательской программой. Проверка фактической достаточности
KEV8192 вынесена в [ресурсную оценку](resource-assessment.md#13-уточнение-что-именно-означает-validated-8192-у-kev-4b).

~~~text
Наблюдаемая история + доступные правила/результаты + известные actions
                     ↓
Одинаковый state builder и честно сформированный каталог кандидатов
                     ↓
Selector: правило / LLM / Laya / KEV → ID следующей операции
                     ↓
Fixed generator: только args выбранной операции либо текст ответа
                     ↓
Штатные checks, tools, среда и evaluator τ-bench
~~~

Нет предварительно выбранного большой LLM действия, которое маленькая модель
только разрешает. При недостаточной уверенности selector передаёт **сам выбор**
заданной fallback LLM; это техническая обёртка, не новая бизнес-операция.

### Что считать выбранной операцией

Для обычного tool — его имя; respond покрывает реплику, включая уточнение.
Разделить ask_user/respond/finish можно отдельным протоколом разметки, но это
наши виртуальные классы, не три готовых native tool names. Для discoverable
важен **semantic ID конкретной известной функции**, а не один общий
call_discoverable_agent_tool: если target name по-прежнему выбирает generator,
реальное банковское решение осталось у LLM.

Адаптер переводит выбранный semantic ID в native wrapper и фиксирует target;
генератору остаются обычные аргументы. Call-ветка допускает только действительно
unlocked функции; отдельный unlock-кандидат — только реально обнаруженное имя.
Provenance каталога — наблюдаемые сообщения и результаты discovery, не скрытый
список из Python-кода. list_discoverable_agent_tools не считать каталогом
всех возможностей: это журнал уже вызванных функций.

### Два честных варианта контекста

1. **Длинный selector:** KEV4B или Laya multilingual с явно настроенным окном,
   измеряемым полным упакованным запросом. Начать с 2k/4k и проверить 8k как
   отдельный режим; наличие поддержки не заменяет token/accuracy/memory test.
2. **Компактный selector:** фиксированное представление наблюдаемых фактов,
   последних реплик и доступных правил. Его качество является частью метода.
   Не заполнять поле «следующее действие» или hidden policy flags силами oracle.

Если состояние строит LLM-summary, она может сама решить задачу, внести ошибки
и съесть экономию. Поэтому сначала детерминированное извлечение наблюдаемых ID,
результатов, пар вопрос–ответ и явных фактов; непокрываемые состояния — fallback.
Нельзя выбросить подтверждение пользователя и ожидать, что RL восстановит факт.
Одному и тому же compact state могут соответствовать полные истории с разными
правильными действиями: это информационная потеря, не обязательно слабое обучение.

Все selectors в причинном сравнении получают **одинаковый семантический текст
и кандидатов**, который реально помещается без hidden truncation. Токенизаторы
различаются, поэтому равный номинальный max_len не доказывает равенства входов.
Long vs compact, полный vs shortlist, predict_long/windowing — разные условия.
Для shortlist измерять candidate recall; gold action нельзя подмешивать при
пропуске. Полное native сравнение сохраняется даже если compact baseline слаб.

### Ранее предложенный архитектурный пилот — не личный RLCD-план

Этот список сохранён для общей платформы/тиммейтов. В личном исследовании
RLCD не требуется выполнять весь context/model grid до сравнения обучения:
достаточно зафиксировать работоспособный вход и единый scaffold.

1. 100–200 **не тестовых** состояний для аудита входа: полные lengths по каждому
   tokenizer/head, число options, потерянные факты, необходимость discovery.
   Не начинать с 6000 меток и дообучения до проверки информационной достаточности.
2. Native LLM; factorized LLM full; factorized LLM compact; дешёвый compact
   selector — одинаковый generator, protocol single/multi-call, candidate source.
3. Заменить selector на KEV4B и Laya multilingual; English/typed только на
   реально помещающемся compact input. KEV0.8 — явно отрицательный reference.
4. Сравнить 2–3 разумных бюджета и seeded перестановки вариантов; не делать
   полный декартов grid всех размеров/доменов/окон. Проверить потерю критических
   фактов отдельно от селектора, сохраняя полные наблюдаемые входы для аудита.
5. Только после этого — сравнение CE/Brier/конкретного RLCD на **одной** модели
   с одинаковым входом. Laya logit-RLCD не объявлять OpenJev rationale-RLCD.
6. Лучшие условия — полный τ-knowledge: task success, выбор/args/discovery errors,
   fallback, стоимость, p50/p95. Аргументы и ответы по-прежнему требуют генерации;
   относительно native одного вызова ускорение **не гарантировано**.

### Разметка меняется, это не переименование binary labels

Новая запись: (наблюдаемый префикс, view, текущий каталог C, рекомендуемый action
или множество приемлемых следующих actions, свидетельства, ambiguities).
Для диагностики оценивать попадание выбранной операции в приемлемое множество
и отдельно ошибки отсутствующего кандидата. Для categorical CE/Brier нужно
заранее определить target distribution q над C: множество допустимых действий
само по себе не задаёт единственную «истинную» softmax-вероятность. Равномерное
q по множеству — явное правило целевой политики, не установленная вероятность
успеха. Imitation одной демонстрации тоже не равна optimal action policy.

Калибровку выбранного ответа проверять относительно определённого события,
например «выбранная операция приемлема при наблюдаемом префиксе», с независимыми
labels. Нельзя считать p(action) вероятностью успеха всей траектории. Сохранять
grouped splits по исходной задаче/семейству и не превращать соседние шаги в
независимые примеры. Native benchmark не предоставляет готовую полную разметку
этих множеств; teacher proposals проверяются отдельно.

## 10. Как это меняет ресурсы и критерий завершения

Ориентир 6000 из [ресурсной оценки](resource-assessment.md) — только порядок
возможного объёма adaptation, не подтверждённое достаточное число action labels.
Теперь измерять покрытие классов/семейств действий и K, а не баланс yes/no.
Для 8k training нельзя переносить память/время короткой Laya из прежней таблицы:
более длинные активации требуют нового smoke-test. Mac остаётся основной
машиной, но ресурсная выполнимость полного длинноконтекстного обучения не установлена.

Сохраняется минимум ВКР: агент с заменяемым selector, воспроизводимый protocol,
данные и сравнение. Научно полезны и выводы «работает лишь на узком short-context
поднаборе», «компрессия определяет потери сильнее модели», «дополнительная
факторизация не окупается». Новый RL-алгоритм и полная замена генеративной LLM
не становятся обязательными результатами.

## Первичные источники закреплённого commit

[agent]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/agent/llm_agent.py
[messages]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/data_model/message.py
[orchestrator]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/orchestrator/orchestrator.py
[environment]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/environment.py
[toolkit]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/environment/toolkit.py
[tools]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/tools.py
[retrieval]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval.py
[composed]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_toolkits.py
[mixins]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_mixins.py
[header]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/prompts/components/policy_header.md
[additional]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/prompts/components/additional_instructions.md
[shell-policy]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/prompts/components/shell_instructions.md
[bm25-policy]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/prompts/classic_rag_bm25_no_grep.md
[all-policy]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/prompts/all_tools.md
[evaluation]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/docs/evaluation.md
[action-evaluator]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/evaluator/evaluator_action.py

[retail-policy]: https://raw.githubusercontent.com/sierra-research/tau2-bench/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/retail/policy.md
[airline-policy]: https://raw.githubusercontent.com/sierra-research/tau2-bench/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/airline/policy.md
[tok-en]: https://huggingface.co/convaiinnovations/laya/resolve/7b928d828b7b0e022f929d9bd2e44165aa270148/tokenizer/tokenizer.json
[tok-multi]: https://huggingface.co/convaiinnovations/laya-multilingual/resolve/1720e3e3357cfe1e281542e223f8273b0890ca34/tokenizer/tokenizer.json
[tok-kev]: https://huggingface.co/Qwen/Qwen3.5-4B-Base/resolve/1001bb4d826a52d1f399e183466143f4da7b741b/tokenizer.json
[cfg-en]: https://huggingface.co/convaiinnovations/laya/blob/7b928d828b7b0e022f929d9bd2e44165aa270148/rl_agent_config.json
[cfg-typed]: https://huggingface.co/convaiinnovations/laya-typed-decisions/blob/e929ae5cf69bc34259cd2f95c9e91145b818b1f0/rl_agent_config.json
[cfg-multi]: https://huggingface.co/convaiinnovations/laya-multilingual/blob/1720e3e3357cfe1e281542e223f8273b0890ca34/rl_agent_config.json
[laya-pack]: https://github.com/NandhaKishorM/laya/blob/68804629e8ccd9d616d48a40e87de9fabbeae069/laya/common.py#L156-L275
[laya-trunc]: https://github.com/NandhaKishorM/laya/blob/68804629e8ccd9d616d48a40e87de9fabbeae069/laya/agent.py#L1132-L1179
[laya-api]: https://github.com/NandhaKishorM/laya/blob/68804629e8ccd9d616d48a40e87de9fabbeae069/laya/serve.py#L84-L124
[laya-bench]: https://github.com/NandhaKishorM/laya/blob/68804629e8ccd9d616d48a40e87de9fabbeae069/BENCHMARKS.md
[laya-long-script]: https://github.com/NandhaKishorM/laya/blob/68804629e8ccd9d616d48a40e87de9fabbeae069/research/scripts/bench_long_context.py
[laya-long]: https://github.com/NandhaKishorM/laya/blob/68804629e8ccd9d616d48a40e87de9fabbeae069/research/results/long_context_multilingual.json
[kev08-card]: https://huggingface.co/jaredpalmer/kev-0.8b/blob/bf75a6a8848ea6960ff2ed108d9ed44c2941174f/README.md
[kev4-card]: https://huggingface.co/jaredpalmer/kev-4b/blob/6cfce5c2fa4b4bd64026336ab649c5ca78857d52/README.md
[kev-pack]: https://github.com/jaredpalmer/kev/blob/2ecafc49fe1e8945cd600443e6c04c1cf0b3a78f/kev/model.py#L87-L142
[kev-api]: https://github.com/jaredpalmer/kev/blob/2ecafc49fe1e8945cd600443e6c04c1cf0b3a78f/kev/api.py
