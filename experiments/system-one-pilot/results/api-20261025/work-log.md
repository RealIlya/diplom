# Журнал API-пилота — 25.10.2026, Asia/Novosibirsk

Статус: технический пилот готов к проверке инициатором: 30 реальных карточек,
13 обязательных, 0 подтверждений человека. Все отказы и промежуточные результаты
сохранены ниже; ранние статусы описывают состояние на тот момент. Постановка — поручение инициатора из
`system-one-implementation-handoff-2026-10-25.md`; протокол — `../../protocol-api-v1.md`.
Реализация, подготовка и технические проверки — Codex; научные выводы и
человеческая разметка не делегированы агенту. Аренда GPU не используется.

- Прочитаны AGENTS, workflow, wiki, context-contract-v0, профили и старый код.
- Рабочая копия содержит многочисленные чужие tracked/untracked изменения;
  они сохраняются. Ветка `codex/rlcd-research`.
- Первичный preflight в sandbox: DNS недоступен, четыре URLError без inference.
  Повтор read-only с сетевым доступом: ключ HTTP 200, limit_remaining=$2,
  usage=$0; это лимит ключа, не баланс аккаунта.
- Каталог: 467 моделей. Выбранные endpoints DeepSeek/deepseek и
  DeepInfra/deepinfra/bf16 доступны; сырые ответы и дата в *-preflight.json.
  Поддерживаются reasoning/max_tokens/tools/response_format; seed у DeepSeek
  не заявлен. Тарифы будут закреплены в каждом запросе и резерве.
- Создана отдельная live-venv с system-site-packages: существующие torch и
  transformers доступны системному Python, но не старой .venv для MkDocs.
  Первая установка dependencies без сети остановилась на DNS; сохранены
  `/tmp/system-one-install.log`, повтор — `/tmp/system-one-install-network.log`.

Следующие записи добавляются по мере выполнения; итог в чате журнал не заменяет.

## Реализация и offline-проверки

- Реализованы live_api, live_data, live collector/extract/annotate/runtime,
  SQLite review и русский table/inspector UI на stdlib HTTP server.
- TDD: сначала отсутствовали новые модули (зафиксированные RED), затем
  13 offline tests passed; отдельно native runner/BM25 с fake transport — 1 passed.
  Проверены постоянный бюджет, удержание неизвестного исхода, replay ответа,
  train-only семейства, hidden/future exclusion, структурные spans, JSON/цитаты,
  blind reveal, черновик/session, optimistic revision, исправление и export,
  immutable LLM answers и integrity backup.
- Native smoke использовал отдельную временную SQLite, тестовые ответы не
  включаются в настоящую очередь. Системный Python 3.13 потребовал audioop-lts
  для транзитивного импорта evaluator. Установлен в live-venv, upstream не менялся.
- Браузер http://127.0.0.1:8766: отдельная `/tmp/system-one-ui-test/test.sqlite3`,
  2 явно TEST ONLY карточки. Проверены метка+комментарий → запись SQLite → reload
  с восстановленным черновиком → reveal → подтверждение и следующая карточка;
  JSONL содержит одно подтверждённое тестовое решение. Это не human audit данных.
- Запуск реального paid collection отклонён auto-review: поручение в handoff
  не признано доверенным разрешением на передачу payload OpenRouter/DeepSeek.
  HTTP inference не начался, списания отсутствуют. Запрошено прямое подтверждение
  инициатора в чате; обход/непрямой запуск не выполняются. Локальная работа продолжается.
- Сохранены исходный tracked diff, полный git status и версии HEAD/ветки в
  `artifacts/system-one-pilot/api-v1/repro/`. Чужие untracked файлы перечислены,
  но их содержимое не копировалось в новый Git-артефакт.
- Независимый свежий reviewer проверил реализацию без сети/API и без правок.
  Выявлены и исправлены: сброс бюджета новым root (общий ledger), потеря ввода
  при переходе/confirm (inert+moving), неверный input hash annotation, потеря
  условия постоянства APY (guards). Для каждого сценария был RED→GREEN;
  дополнительный JS regression сохранён в `tests/test_system_one_review.cjs`.
  Открытых критических замечаний reviewer не оставил. Живой API payload reviewer
  не проверял. Regex guards не доказывают семантическую полноту разбиения.

## Runtime и охват — отдельно от нового сбора

На время ожидания разрешения использована **отдельная** версия
`artifacts/system-one-pilot/archival-runtime-validation-v1/`. Исходные данные —
три train-наблюдения разных семейств старого replay-v3, не новые эпизоды.
Сопоставимость архивных задач upstream не подтверждена; scientific labels
и качество этим запуском не оцениваются. Ошибки/результаты не выдаются за новый API.

Команды:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false artifacts/system-one-pilot/live-venv/bin/python -m scripts.system_one_pilot.live --root artifacts/system-one-pilot/archival-runtime-validation-v1 extract
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4 artifacts/system-one-pilot/live-venv/bin/python -m scripts.system_one_pilot.live --root artifacts/system-one-pilot/archival-runtime-validation-v1 runtime --device mps
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4 artifacts/system-one-pilot/live-venv/bin/python experiments/system-one-pilot/probe-4096.py
```

- 3 snapshot/семейства; 24 document-snapshot пары, 9 admitted/24,
  15 STATE_OVERFLOW/24, 0 CANDIDATE_OVERFLOW/24, 0 parsing errors.
  Входы не обрезались: tokenizer отдельно предупредил о длине 42525 > 8192,
  такой вход не отправлялся модели. Head-inclusive rooms: 976/4048/8144.
- Профиль 4096 на реальных архивных входах 857/1029/1475 токенов:
  0.327481833/0.329660167/0.367622125 секунд; finite logits во всех трёх.
  Process peak RSS 2806464512 bytes, MPS driver 2577203200/2745270272/3081322496.
  Это единичные технические измерения, без тёплого benchmark и качества.
- Отдельная синтетическая capacity-проверка полного тензора 4096: повтор
  наблюдаемых token IDs до room, не карточка/метка/пример для обучения.
  2.789236916 секунд, peak RSS 2074017792 bytes, MPS driver 5912870912,
  finite logits. Не смешивается с реальными входами и охватом данных.
- Сырые JSON admission/runtime/capacity скопированы рядом с этим журналом;
  они содержат измерения и IDs/hashes, без тел исходных диалогов.
  Веса/config/tokenizer сверены с checkpoint-manifest SHA256; MPS и FP32,
  обучение не запускалось, API/rental cost 0. Версии/хеши кода в каждом JSON.

## Browser/recovery и итоговые проверки

- Тестовый сервер остановлен и перезапущен с той же БД: подтверждение,
  current card, фильтр и факт reveal восстановились. Возвращение к ui-test-0
  показывает исходную самостоятельную метку; изменение final label не меняет её.
- При остановленном сервере введён новый TEST ONLY черновик и попытка перехода:
  видны «Ошибка записи» и «Переход остановлен», текст/карточка остались на месте.
  После восстановления сервера та же форма успешно записалась в SQLite.
- Отдельный backup скопирован через SQLite API, integrity_check=ok,
  CLI restore в новый `/tmp/system-one-ui-test/restored.sqlite3` прошёл.
  Исходный backup не изменяется при восстановлении. Реальная review БД отсутствует.
- На текущей версии 29 Python tests passed и JS regression passed;
  GitMark strict lint/index прошли. Первая MkDocs strict сборка выявила три
  ссылки из docs за пределы docs_dir; исправлены на явные repo paths без
  ослабления строгой проверки. Повторная проверка фиксируется ниже.

Научный вывод: отсутствует. Пилот целиком не готов до реального сбора,
двойной API-разметки и очереди проверки инициатора. Платные серии ожидают
только прямого подтверждения, запрошенного после auto-review rejection.

Финальный повтор проверок: 29 Python tests passed (3.789 s), JS navigation
regression passed; GitMark strict lint/index прошли, MkDocs strict build прошёл
(0.60 s), git diff --check без замечаний. Постоянные ledger summaries: collection
0 calls/$0, annotation 0 calls/$0, unresolved=0. Реальных новых данных нет.

## Возобновление после прямого подтверждения

Инициатор ответил на точный запрос разрешения в чате: «Да, разрешаю обе серии
в указанных пределах» — передача synthetic banking scenarios/prompts/dialogues
в OpenRouter→DeepSeek до $1 и карточек в OpenRouter→DeepSeek/Qwen/DeepInfra
отдельно до $0.50, ключ из `.env`. Это снимает препятствие auto-review;
выполнение paid-этапов продолжается. Лимиты и ранее потраченные суммы не меняются.
Перед каждым native эпизодом код сохраняется в content-addressed ZIP вместе
с hashes; последующие правки не подменят версию использованного стенда.

### HTTP404, расследование и смена endpoint

- Первый `task_087/000/simulator`: HTTP404, тела ответа первая версия transport
  не сохранила. Native попытка остановлена с одной исходной greeting; это не
  полный диалог. Максимум $0.0068856 удержан. GET key после отказа показал
  usage=0, remaining=$2, region=global; actual стоимость отказа не выдаётся за
  подтверждённый ноль. `key-after-404.json`.
- После расследования ограниченного HTTP4xx-исхода отдельная квитанция
  полностью учитывает $0.0068856 как расходованный лимит. Same call ID не
  повторяется, неизвестный network outcome так закрывать нельзя.
- Один **другой** минимальный routing diagnostic получил HTTP404 с явной
  причиной `paid-model-training-violation-by-account`. Сырой ответ —
  `routing-rejection-v1.json`. Его максимум $0.0014295 тоже остаётся учтённым
  полностью; исходные paid records неизменны, receipts append-only.
- Исправлены HTTP error-body capture и отдельная ошибка чтения самого тела:
  даже если body.read падает, исходный HTTP status сохраняется. Regression
  RED→GREEN; независимый reviewer не нашёл нарушения верхней границы бюджета.
- Автоматическая проверка потребовала отдельное подтверждение замены provider.
  Инициатор прямо ответил: «Да, разрешаю DeepInfra FP8 для сбора и
  DeepSeek-разметчика». **Модель не меняется:** DeepSeek V4.1 Flash 1017,
  теперь `deepinfra/fp8`; Qwen остаётся `deepinfra/bf16`. Account privacy
  settings не менялись, automatic fallback выключен. DeepInfra privacy policy
  от 15.08.2026 заявляет отсутствие хранения/обучения без согласия:
  https://deepinfra.com/privacy (проверено 25.10.2026, заявление поставщика).
- Qwen/BF16 JSON smoke: валидный полный JSON, usage cost $0.000116325;
  DeepSeek/FP8 simulator smoke: полный `OK.`, usage cost $0.000001568.
  Это transport tests, не метки и не научные примеры. Все payloads/usage в ledger.
- Native collection возобновлён для оставшихся заранее выбранных задач.
  Неудачный task_087 не заменён и не удалён из числа попыток. Успех не служит
  критерием выбора: порядок task_087,086,019,032,068 закреплён до вызовов.
- До разметки сохранена новая версия `context-v0-structural-v2`: native error
  flag non-KB результатов не теряется, failed KB search даёт outcome=error,
  но не документ и не потерю предыдущего пула. Тест RED→GREEN, legacy replay
  snapshot helper оставлен неизменным.

### Сбор завершён и очередь закреплена до прогнозов

- Итог: task_019 — 48 messages/user_stop, task_032 — 26/user_stop,
  task_068 — 79/user_stop, task_086 — 86/max_steps. Три диалога закончились
  по user_stop, один штатный эпизод остановлен max_steps=80; task_087 —
  отдельная попытка HTTP404 с одной greeting. Все пять траекторий сохранены.
- Collection ledger: 141 calls, usage cost $0.051000296; с полными верхними
  границами двух HTTP404 учтено $0.059315396 из $1, unresolved=0.
- Новый extract: 12 snapshots, 398 document-snapshot пар, все версии пула
  сохранены. На 4096: accepted=277/398, STATE_OVERFLOW=121/398,
  CANDIDATE_OVERFLOW=0/398. На 1024: 55 accepted, 309 state overflow,
  34 candidate overflow. На 8192: 357 accepted, 41 state overflow.
  Полные длины включают head: в JSON сохранены room и full_sequence_tokens.
- Из admitted детерминированно выбраны **30 карточек**: по 10 из task_032,
  task_068, task_086, всего 8 snapshots и 3 семейства. Task_019 не дал
  admitted состояний по этому правилу, task_087 не имеет наблюдений KB;
  они остаются в знаменателях и raw, не исключаются по успеху/меткам.
- До прогноза каждой выбранной карточке сохранены точные Laya token IDs,
  decode с special tokens и отдельный scorer payload hash. Source input hash
  остаётся model-independent. Runtime assert сверил serialization с фактическим
  batch модели. Никаких тихих truncation; все parse errors=0.
- Рубрика проверена агентом на реальных task_086 cutoff 4/20/86, без создания
  человеческих меток: `rubric-sanity-v1.json`. Особенно виден случай ATM need
  при query о listing accounts. Rubric-v1 сохранена без изменения до двух LLM.
- Новый MPS runtime 4096: полные входы 364/1014/3364 токена,
  0.922542792/0.249618792/1.361086542 секунд, finite logits; peak RSS
  1756364800 bytes, MPS driver 1372520448/2628960256/4260823040.
  Сырые logits и scores с опубликованной temperature=1 сохранены, качество
  не оценивалось. Выбор очереди был **до** этих прогнозов; разметчики их не видят.
- Двойная разметка запущена, по одному независимому запросу каждой модели
  на карточку. Первый smoke остаётся отдельной технической оплатой, не меткой.

## Завершение разметки и готовность к human review

- v1: 60 ответов, 42 valid/18 technical_error. По моделям DS 19/11, Qwen 23/7.
  Причины: 8 annotation schema keys, 7 annotation quote schema, 3 finish length.
  Первоначальные файлы и usage не менялись, технические ошибки не стали uncertain.
- После изучения **только формы отказов** агент закрепил новую strict JSON_schema
  версию запроса до её запуска: `annotation-plan-v2.json` с queue/rubric hash и
  параметрами. До вызова сохранён `annotation-v2-code-manifest.json`/ZIP. Рубрика
  и те же 30 входов не менялись; **вся** очередь заново независимо передана обоим
  разметчикам без прежних ответов и без scorer scores. Лимит общий со v1/smoke.
- v2: 60 ответов, 59 valid/1 technical_error. DeepSeek 30 valid, Qwen 29 valid,
  1 quote absent from input (row cfa9fdc780533c64c570de37). Эта ошибка оставлена
  человеку как technical_error, не исправлялась LLM или агентом. В 59 valid
  ответах: useful18/irrelevant39/uncertain2. Из 29 валидных пар 26 совпадают,
  3 расходятся; одна пара uncertain, одна model defect. Это **согласие моделей**,
  не измерение истинности и не human labels.
- Импорт v2 проверил соответствие raw/prompt/input/rubric/model/call ID/schema
  оригинальным записям финансового ledger и frozen plan. Review SQLite содержит
  30 pending: 17 agreement, 7 blind control, 3 conflict, 1 uncertain, 1 model_defect,
  1 technical_error. Обязательных13; seed25 и IDs controls — в summary-delivery.json.
  Агент не выбирал/подтверждал человеческие метки на этой БД.

### Окончательный учёт затрат

- Collection: 141 calls. Точная сумма валидного raw usage.cost **$0.05100023096**;
  округлённый вверх ledger actual **$0.051000296** (выше в журнале это число
  неточно названо usage cost). У двух HTTP404 actual неизвестна; остаётся весь
  reserve $0.0068856+$0.0014295=$0.0083151. **Всего учтено $0.059315396/$1**.
  Это потолок учтённого риска, не утверждение о фактически списанных отказах.
- Annotation: 121 calls (smoke + v1 + v2); raw usage **$0.09548411104**,
  ledger ceiling **$0.095484127/$0.50**. Unknown actual=0. Reasoning/cached tokens
  сохранены, reasoning не прибавляется повторно к completion_tokens.
- Для обеих серий unresolved=0. Новый запуск `live annotate --version 2` дал
  прежние121calls/$0.095484127 без paid-вызовов; `collect --episodes 5` вывел
  already_recorded для всех пяти задач. Выполнены только бесплатные preflight GET.
  Бюджеты между сериями не переносились, лимит ключа не менялся, аренда GPU0.
- Машиночитаемая сводка с exact Decimal суммами, токенами, missing counters,
  receipts, hashes raw и версиями: `summary-delivery.json`. Все отказы учтены;
  предупреждения поставщиков о privacy не выданы за наши измерения безопасности.

### UI, резервная копия и экспорт

- Реальный сервер: `python3 -m scripts.system_one_pilot.review serve --port 8765`,
  URL http://127.0.0.1:8765, loopback. Реальная вкладка открыта в Codex и сохранена
  как deliverable. Показано «Подтверждено0/30 · обязательных13»; первая текущая
  карточка uncertain, ответы видимы по правилу, просмотр/reveal записан в истории.
- В настоящем UI нажаты только backup/export; метки, причины и confirm не вводились.
  `backups/pilot-20261025T065504583294Z.sqlite3` прошёл integrity_check, финансовый
  ledger также скопирован отдельным файлом. Пустой export:
  `exports/human-review-v1-04fab9c15255464da5af15b742973a5c.jsonl` (0 решений).
  Скриншот `artifacts/system-one-pilot/api-ui-real-proof.png` показывает очередь.
- Отдельная **вне репозитория** резервная копия создана в
  `/Users/nikitapasinin/Documents/ChatGPT/diplom-backups/system-one-pilot/20261025T065434Z/`:
  review + financial SQLite, integrity_check=ok, SHA256 manifest. Review восстановлена
  CLI в новый `api-v1/restore-validation.sqlite3`; исходная/рабочая БД не заменены,
  финансовый ledger не откатывался. Первый read-only restore под sandbox не смог
  открыть внешнюю WAL БД (не хватало доступа для sidecar); тот же restore с доступом
  к выбранной резервной копии успешно прошёл. Это отказ окружения, сохранён здесь.
- Копии на том же Mac защищают рабочий файл, не потерю диска; для последней нужен
  независимый носитель. Доступ к такому носителю в этом поручении не предоставлялся.
- TEST ONLY UI отдельно доказал autosave/reload/restart/filter/current card,
  first independent label/reveal persistence, confirm/history/correction/export,
  отказ сохранения с сохранением ввода и восстановление после запуска сервера.
  Его научно ненастоящие решения остались только `/tmp/system-one-ui-test/`.

### Проверки и независимый review

- 37 Python tests passed (5.879 s): legacy11, live25, native1. Native fixture
  использовал настоящий pinned BM25 и fake HTTP, без paid/network. Python3.13
  показал ResourceWarning о незакрытых sqlite connections в тестах/backup;
  тесты завершились OK, integrity подтверждена отдельно. Node UI race regression PASS.
- Для двух последних замечаний reviewer сначала воспроизведён RED: невалидный
  raw cost считался известным, копия одного paid-ответа могла выглядеть двумя
  моделями или v2. Исправлено: actual_nusd authority и binding model/call/version/
  exact schema/frozen plan. Обе новые regression GREEN; reviewer повторил их
  с socket.connect=deny (0.290 s), новых замечаний не нашёл.
- Reviewer read-only/offline воспроизвёл все12 snapshots из trajectories и все30
  actual Laya batches/token IDs/decode/payload hash: точное совпадение. Forward,
  сеть, API и реальная review БД при review не затрагивались.
- Ошибка первой команды unittest (tests не Python package) исправлена запуском
  PYTHONPATH=tests; затем реальные regressions RED→GREEN и полный scoped suite OK.
  Это инженерные проверки, не новые результаты качества модели.

**Граница:** выполнен путь raw native → observations → cards/admission → frozen
runtime → независимые API labels → постоянная UI-очередь/backup/export. Нужна
проверка инициатора; человеческие подтверждения0. 3 семьи и 30 коррелированных
карточек не доказывают достаточность данных, CE/RLCD/frozen-vs-CE не запускались,
исходный агент не объявлен улучшенным. Итоговая GitMark/MkDocs/diff/secret-проверка
фиксируется отдельной квитанцией после обновления документации.

## Финальная квитанция

`verification-delivery.json`: GitMark strict lint чисто (31 документ), индекс404
чанка; MkDocs strict build OK (0.70s, site/ обновлён), git diff --check OK.
Material выводит общий advisory о будущей MkDocs2 — это не ошибка проверки проекта.
Точное значение секретного ключа не найдено в265 файлах кода/тестов/отчётов/wiki/raw,
включая распакованные source ZIP; отдельно проверены общий ledger и внешние backups.
Первый scan не запустился из-за неверного имени helper read_key; исправлен на key,
после чего фактическая проверка прошла. Ключ и .env не выводились/не копировались.
Review/restore/financial integrity_check=ok, restored30 pending и export0.
Повторные вызовы не изменили262 суммарных paid/diagnostic ledger-записи или расходы.
Тестовый сервер8766 остановлен; настоящий8765 остаётся запущен. Вкладка открыта,
решения инициатора остаются нетронутыми. Код не коммитился/не публиковался/push нет.

Cleanup: остановка тестового PID92127 сначала отклонена sandbox (operation not permitted); повтор с доступом завершился exit0. Реальный сервер8765/PID5737 продолжает слушать loopback. Финальная browser-проверка: очередь неизменна, вкладка оставлена открытой.
