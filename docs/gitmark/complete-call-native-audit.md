---
node_type: reference
title: Полные native вызовы τ-knowledge из наблюдений
service: _platform
status: active
updated: 2026-10-11
links:
  relates_to: [docs/gitmark/action-selection-review.md, docs/gitmark/README.md]
---

# Полные native вызовы τ-knowledge из наблюдений

**Вывод:** узкий complete-call path без генеративной LLM на автоматизированном
шаге технически возможен: имя и все аргументы ряда вызовов собираются из
наблюдений. Это не доказательство правильного выбора следующего действия,
покрытия банковских задач или эффективности KEV/Laya. Полная идентификационная
цепочка **не является read-only**: policy требует запись в журнал верификации.
Контекст: [исходный аудит](<action-selection-review.md>) и
[вопрос «Какие native вызовы можно собрать из наблюдений?»][ticket].

## 1. Дата, метод и границы

Статический аудит **11.10.2026**, `sierra-research/tau2-bench`, commit
`4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699`. Прочитаны нужные участки
[banking tools][tools], обычные [policy header][header] и
[additional instructions][additional], [retrieval mixins][mixins]. Для проверки
фактического формата returns дополнительно прочитаны [query helper][query]
и [схема таблицы][schema] — исходный код, **не содержимое БД**.

Метод: pinned raw HTTP, `curl --fail --location` с проверкой TLS в новый
временный каталог, затем `read`/`grep`; upstream не импортировался и не исполнялся.
Полный исходник [tools][tools] — 189257 bytes, SHA256
`e7287dc76ab74f7c172a9b632b6ebdb067a85bbc0cb7c769f7bdf08ec18aa1c0`.
Не читались tasks, test goals, DB fixtures, `required_documents`; не было весов,
модельных прогонов, платных API или измерений на Mac 24 GB. Среда, native policy,
tools и evaluator не изменялись. Ниже нет реальной или восстановленной task trajectory.

## 2. Шесть обычных read tools

Сигнатуры приведены без `self`; все аргументы обязательны, возвращаемый тип —
`str`, декоратор — `ToolType.READ`. **Общий фактический return:** текст
`Found N record(s) in 'table':`, затем `Record ID: ...` и все пары
`field: value` каждой найденной записи; не JSON и не фиксированная проекция.
Пустой результат — `No records found in 'table'.`; ошибки также строки.
Таблица хранит `Dict[str, Dict[str, Any]]`: фиксированный перечень полей
реальной записи не гарантирован схемой. [Формат][query], [схема][schema].

| Native сигнатура | Поиск и реально возвращаемые поля | Откуда собрать аргумент без hidden state |
| --- | --- | --- |
| `get_user_information_by_email(email: str) -> str` | `users`, точное равенство `email`; все поля и Record ID. Docstring обещает сведения DOB/email/phone/address, но не типизированную схему результата. [Код][identity] | Email, явно сообщённый пользователем либо полученный в относящемся к нему tool result; не выдумывать и не считать найденный email подтверждением личности. |
| `get_user_information_by_name(customer_name: str) -> str` | `users.name`; регистр значим; все поля и Record ID. [Код][identity] | Явно названное полное имя, без угадывания написания; несколько совпадений не дают единственного клиента. |
| `get_user_information_by_id(user_id: str) -> str` | `users.user_id`; все поля и Record ID. [Код][identity] | Явный user ID из user/tool сообщения; привязка к человеку ещё требует проверки. |
| `get_credit_card_accounts_by_user(user_id: str) -> str` | `credit_card_accounts.user_id`; все поля и Record ID. Docstring перечисляет card type, date opened, current balance, reward points, **не фиксирует имена JSON-полей**. [Код][reads] | ID установленного клиента после идентификации и её логирования; наличие интереса пользователя/основания в процедуре. |
| `get_credit_card_transactions_by_user(user_id: str) -> str` | `credit_card_transaction_history.user_id`; все поля и Record ID, без отдельной декларации полей транзакции. [Код][reads] | Тот же проверенный user ID; конкретный transaction ID **не входной аргумент** этого метода. |
| `get_referrals_by_user(user_id: str) -> str` | `referrals.referrer_id`; все поля и Record ID. [Код][reads] | ID клиента как **referrer**, а не автоматически ID приглашённого человека из другой записи. |

Эти шесть методов и их query helper не записывают DB/state. Фильтры используют
точное сравнение, не fuzzy entity resolution. Внутренние JSON constraints
собраны f-строками: кавычки/escape в значении могут нарушить разбор; внешне валидный
вызов не гарантирует успех. Не исправлять это подменой native реализации.
[Вызовы][identity], [остальные reads][reads], [сравнение][match], [helper][query].

**Граница знания о полях:** ключ фильтра присутствует у успешного совпадения,
но остальные поля надо извлекать именно из полученного сообщения. Нельзя
обещать наличие `transaction_id`, `account_id` или `user_id` после любого поиска
по email только по названию tool. `Record ID` — ключ записи конкретной таблицы,
не универсальный бизнес-ID; `ID` документа KB — ещё другой тип. [Query][query],
[схема][schema], [retrieval format][mixins].

## 3. Идентификация и подтверждения

- Policy требует перед доступом к данным проверить **любые два из четырёх**:
  date of birth, email, phone number, address. Их должен правильно назвать
  пользователь; имя/user ID недостаточны. Отдельного endpoint проверки policy
  не назначает: написано `call the appropriate read tools`, затем сопоставить
  значения. Повторная проверка в разговоре не нужна; общий KB-вопрос без доступа
  к личным данным её не требует. [Обычная policy][auth].
- **Bootstrap ≠ доступ после проверки.** Текст одновременно требует
  `first verify ... before proceeding` и read tools для самой проверки; точный
  bootstrap allowlist/порядок формально не описан. Lookup идентификационных полей
  нельзя приравнивать к уже разрешённому чтению транзакций/рефералов. Этот аудит
  не придумывает дополнительное разрешение: до проверки запрещена утечка любых
  данных пользователю, неоднозначный bootstrap остаётся вне fast path. [Policy][auth].
- После проверки обязателен
  `log_verification(name: str, user_id: str, address: str, email: str, phone_number: str, date_of_birth: str, time_verified: str) -> str`.
  Все **семь** аргументов обязательны, хотя проверяются два identity-поля.
  `name/user_id` привязываются к найденному клиенту; четыре identity-поля — к
  наблюдаемой записи и сообщённым пользователем значениям; `time_verified` —
  к результату tool времени. Не названные пользователем поля технически можно
  скопировать из наблюдаемой записи, **но они не становятся подтверждёнными факторами**.
  Пропуск поля, несколько клиентов, расхождения форматов адреса/телефона/DOB
  не разрешены статическим аудитом; для DOB docstring требует `MM/DD/YYYY`.
  Метод лишь пишет `verification_history`, не проверяет два совпадения.
  Успешный log не является endpoint-доказательством личности; этот WRITE-шаг
  пока можно оставить LLM. [Код][verification], [policy][auth].
- Timestamp надо получить через `get_current_time() -> str`: policy запрещает
  предполагать текущее время. Даже фиксированная строка в реализации не оправдывает
  её hardcoding в кандидате: нужен наблюдаемый ответ tool. [Policy][header],
  [код][clock]. Успешный ответ на `log_verification` — отдельное наблюдение;
  попытка вызова и сообщение об ошибке не равны успешной записи.
- В двух проверенных policy-компонентах нет общего требования отдельного «да»
  перед каждым read. Это **не отменяет** намерение пользователя, идентификацию
  и специальные условия найденной KB-процедуры. Для перевода к человеку header
  содержит отдельное требование предварительно спросить пользователя, с
  оговорёнными KB-исключениями. Не переносить его механически на все tools и
  не считать проверку личности согласием на любую банковскую операцию.
  [Header][header], [additional][additional].

## 4. Retrieval, discovery и служебные записи

| Native контракт | Наблюдаемый вход/выход и ограничение complete-call |
| --- | --- |
| `KB_search(query: str) -> str` | Query можно детерминированно копировать/собирать из видимого запроса и результатов, без LLM; это **наше правило построения**, не штатный генератор запросов. Return содержит title, document `ID`, score, **полный content** и timing, либо сообщение об отсутствии результатов. Качество поиска не следует из корректности строки. [Код][mixins] |
| `KB_search_bm25(query: str, k: int = 10) -> str`; `KB_search_dense(query: str, k: int = 10) -> str` | Тот же formatter; `k` — параметр/default схемы, не скрытый факт клиента. Это варианты доступного retrieval toolkit, не разрешение подменить выбранный native backend. Dense backend и его ресурсы здесь не запускались и не проверялись. [Код][mixins] |
| `grep(pattern: str) -> str` | Regex, а не natural-language query; полный content совпавших документов, ID/title/score. Детерминированное экранирование буквальной видимой фразы — возможный кандидат, не универсальная поисковая стратегия. [Код][mixins] |
| `unlock_discoverable_agent_tool(agent_tool_name: str) -> str` | Имя **из реально полученного KB content**, tool нужен для текущей работы, не «про запас». Возвращает имя, description, параметры с type/required, разобранные из docstring. Хотя похоже на чтение описания, пишет `_agent_discoverable_tools_state` в памяти; DB-записи на unlock нет. [Policy][discovery], [код][unlock] |
| `call_discoverable_agent_tool(agent_tool_name: str, arguments: str = "{}") -> str` | Только после успешного unlock; внутренние args — **JSON-строка**, не вложенный dict во внешнем arguments. Имя/поля — из наблюдавшихся KB/unlock, значения — из user/tool сообщений и разрешённых defaults. Проверяет существование, unlock, JSON и вызов Python; числовые int при JSON-разборе нормализуются в float. Не проверяет факт KB-discovery, идентификацию и всю policy. [Код][call] |
| `list_discoverable_agent_tools() -> str` | Читает журнал **вызванных** функций, не каталог всех функций и не полный список unlocked. Не использовать для обхода поиска KB. [Код][listed] |

**Read-like ≠ отсутствие служебной записи.** Wrapper call имеет тип WRITE:
после возврата underlying метода он добавляет `tool_name/status=CALLED` в
`agent_discoverable_tools` для mutating tool или read tool из внутреннего
allowlist оценивания. Этот allowlist нельзя читать/передавать селектору или
использовать при отборе кандидатов. Вызов underlying read может поэтому менять
служебную DB; журнал может не содержать другие выполненные reads. Код также
не проверяет, является ли возвращённая строка бизнес-ошибкой, перед записью.
[Dispatcher][call]. Аналогично `give_discoverable_user_tool` меняет память и
`user_discoverable_tools`; это выдача действия пользователю, не его исполнение
агентом. [Код][give], [policy][additional].

В query-retrieval mixins нет записи банковской DB; это не аудит всех побочных
эффектов backend. Метка READ у `shell(command)` сама по себе также не доказывает
чистоту произвольной команды: mixin передаёт её sandbox. Универсальный shell
compiler в проверенный узкий path не включён. [Код][mixins].

## 5. Цепочка observation → ID reference → next candidate

**Вывод из контрактов, не task trajectory и не проверенный агент:**

1. Пользователь явно назвал email `e`. Синтаксически собирается полный кандидат
   `get_user_information_by_email(email=e)`; допуск bootstrap обсуждён выше,
   само наличие аргумента не разрешает вызов. Совпадений может быть 0, 1 или несколько.
2. Полученный tool result `m` содержит запись клиента. Только если в ней реально
   есть `user_id=u`, сохранить ссылку вида `(message=m, record=r, field=user_id)`
   со значением `u`, типом сущности и связью с этим пользователем. Не читать БД
   напрямую и не выводить `u` из формы имени/email.
3. Если пользователь правильно назвал два требуемых значения, есть все семь
   наблюдаемых аргументов и время из `get_current_time`, можно собрать полный
   `log_verification(...)`. Если данных/подтверждения нет — уточнение или fallback,
   а не заполнение пропуска из gold. После успешной записи допустимо рассматривать,
   например, `get_credit_card_accounts_by_user(user_id=u)`, когда это нужно запросу.
4. После каждого нового результата перестроить кандидатов. ID счёта/транзакции
   связывать с **конкретной записью и типом аргумента** следующей операции; document
   ID не подставлять в user ID. Для specialized call дополнительно нужны видимая
   KB-процедура, её условия и успешный unlock, а не имя из исходного Python-каталога.

Здесь пункты 1–3 опираются на [reads][identity], [policy идентификации][auth],
[логирование][verification] и [account read][reads]; пункт 4 — на
[формат результатов][query] и [discovery policy][discovery]. Автоматическая
проверка/привязка таких ссылок — **предложение адаптера**, её реализация не проверена.

**Три synthetic complete-call примера, не измеренный успех и не batch:**
условный `SYNTHETIC_USER_01` ранее получен как `user_id` нужного клиента в tool
сообщении, два фактора правильно названы пользователем, логирование успешно.
В каждом отдельном префиксе пользователь просит соответствующие сведения;
остальные применимые условия policy/KB выполнены. Тогда возможны отдельные кандидаты:

| Запрос | Полностью заданные native name + arguments |
| --- | --- |
| История приглашений | `{"name":"get_referrals_by_user","arguments":{"user_id":"SYNTHETIC_USER_01"}}` |
| Карточные счета | `{"name":"get_credit_card_accounts_by_user","arguments":{"user_id":"SYNTHETIC_USER_01"}}` |
| Карточные транзакции | `{"name":"get_credit_card_transactions_by_user","arguments":{"user_id":"SYNTHETIC_USER_01"}}` |

Здесь ID придуман **только для иллюстрации**; наличие реальной записи и результат
вызова не утверждаются. Сигнатуры взяты из [обычных tools][reads].

Для KEV/Laya кандидатом должен быть **целый native вызов с фиксированными
аргументами**, а не одно имя плюс генеративное заполнение. Технический ID вызова
и сериализацию может создавать harness; бизнес-значения нельзя допридумывать.
Селектор решает, какой кандидат уместен, а compiler не должен содержать
`test task → next action`, скрытые ID, gold или oracle-флаг «verified».
Общие ограничения из публичной policy допустимы; специфическую процедуру надо
получать через штатный KB, не hardcode по test. Если уникальная привязка,
процедура или требуемый факт не установлены — `defer`, не молчаливый guessed call.
Это сохраняет native среду, но **не обещает полного диалога без LLM**.

Остаётся непроверенным: покрытие реальных состояний такими кандидатами,
неоднозначность ссылок, надёжность парсинга текстовых returns, выбор query,
достаточность контекста и качество/память/задержка KEV/Laya. Policy-correctness,
успех по evaluator и уверенность selector — разные проверки. Индекс/навигация
и сборка сайта не изменялись: связывание отчёта с картой выполняется отдельно.

## Первичные pinned источники

Все ссылки ниже относятся к одному проверенному commit; номера строк — исходного кода.

[ticket]: <README.md#wayfinder-native-complete-calls>
[tools]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/tools.py
[identity]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/tools.py#L395-L422
[reads]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/tools.py#L445-L479
[clock]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/tools.py#L386-L393
[verification]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/tools.py#L481-L530
[give]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/tools.py#L532-L600
[unlock]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/tools.py#L602-L641
[call]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/tools.py#L643-L700
[listed]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/tools.py#L702-L716
[query]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/db_query.py#L433-L471
[match]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/db_query.py#L145-L233
[schema]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/data_model.py#L80-L105
[header]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/prompts/components/policy_header.md#L6-L14
[additional]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/prompts/components/additional_instructions.md
[auth]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/prompts/components/additional_instructions.md#L31-L44
[discovery]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/data/tau2/domains/banking_knowledge/prompts/components/additional_instructions.md#L19-L29
[mixins]: https://github.com/sierra-research/tau2-bench/blob/4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699/src/tau2/domains/banking_knowledge/retrieval_mixins.py#L15-L180
