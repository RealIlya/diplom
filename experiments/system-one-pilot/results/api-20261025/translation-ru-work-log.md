# Русский вспомогательный перевод UI — 25.10.2026

Поручение инициатора: «давай добавим перевод на русский для всего текста что нужно оценить».
Английские state/candidate и первичные ответы остаются исходными; перевод не меняет
целевую метку, scorer input/hash или LLM-аннотацию. Выбор агента: показывать русский
перевод основным текстом, английский оригинал доступен рядом в раскрываемом блоке.
Перевод создаётся Codex без дополнительных внешних API-запросов/расходов.

План: инвентаризация точных строк → перевод трёх независимых частей → проверка полного
покрытия/хешей → постоянное SQLite-хранение и backup/export provenance → UI → offline
и browser проверки без ввода человеческих меток → актуализация wiki и строгая сборка.
Blind controls скрывают и исходные, и переведённые объяснения до явного reveal.
Человеческие решения не трогаются. Исходное состояние review сохранено в ignored
translation-ru-v1/before-review.json для сравнения до/после миграции.

## Реализация и проверка содержания

- 256 уникальных строк: 8 state (20194 chars), 26 candidate (47016), 26 title
  (1319), 1 rubric (2195), 89 explanation (23168), 114 quote (8450); категории
  могут пересекаться. Базовые source hashes — SHA256 точного UTF-8 исходника.
- Три независимых translation batches: 84/86/86 строк, 33954/33957/33964 source
  chars. Переводы подготовлены Codex в отдельных контекстах, без сети/ключа/API.
  Snapshot модели внутри Codex недоступен; не приписываем ему выдуманную версию.
  Точная воспроизводимость обеспечивается сохранённым bundle и его SHA256.
- Семантически сверены все 26 candidate и 8 state; rubric и 46 коротких пояснений
  дополнительно проверены другими агентами (это не независимые human labels).
  Найдена 1 ошибка: «confirm cancellation directly with merchant in writing»
  переводилось как получение подтверждения от продавца, заменено на письменное
  подтверждение отмены непосредственно продавцу. Исправлено до frozen import.
- Полностью совпали числовые токены всех256 строк. Все8 state — валидный JSON,
  типы/ключи/массивы/нестроковые значения совпали. Различаются только natural text
  content/query; роли, tools, IDs, args и метаданные сохранены. atm_withdrawal
  (цитата-код) закономерно не кириллическая. Отдельный ранний assert «каждая строка
  обязана содержать кириллицу» отверг этот код; проверка уточнена без изменения
  технического идентификатора. Необычные исходные $660/«12.5% percent»/порог5 без
  единицы не исправлялись переводом.
- Bundle `translation-ru-v1/translations-ru-v1.json`, schema review-ru-v1, author
  Codex; digest 9c25d8d514687a797f885adee34f26e6ce01113db06276ed1d7de19ac0ffb4ac.
  Исходники/частичные переводы и backup до импорта сохранены локально.

## Постоянное хранение и защита исходного эксперимента

- В review.py отдельная immutable singleton таблица review_translation. Импорт
  проверяет schema, непустой RU, точные source SHA и полное покрытие known strings;
  неизвестные/пропущенные/дублированные строки отвергаются. Точный replay безопасен,
  изменение frozen bundle отклоняется. Исправления требуют новой review версии.
- card API выдаёт только переводы видимых текстов; до reveal нет reason/conditions/
  quotes скрытых моделей. Queue содержит русский title и ищет по обоим названиям.
  Никаких новых target labels, scorer payload или LLM-аннотаций.
- UI русские state/candidate, rubric, rationale/conditions/quotes, technical error
  объяснение и метки; английский оригинал рядом в details, тексты через textContent.
  JSON-state форматируется для чтения, точный исходник в disclosure не меняется.
  Названия продуктов и технические значения сохраняются. Raw response/history —
  диагностические оригиналы, не дополнительный target input.
- Draft/confirm присылают hash отображённого bundle, audit его хранит. При чужом
  hash запись отклоняется. Старые English-only клиенты присылают null/без token:
  export не приписывает им перевод. Подтверждённая версия включает RU+source/provenance.
- До импорта online backup `backups/pilot-before-ru-v1.sqlite3`. Сравнение всех строк
  cards/reviews/review_session/review_events до и после миграции **точно совпало**;
  все30 pending, 0 человеческих подтверждений. `translation-ru-migration.json`.

## Тесты, review и настоящий браузер

- RED: новые translation tests падали на отсутствии helper; после реализации оба
  GREEN. Scoped39 Python tests passed (5.674s), включая legacy и native fake-HTTP.
  Старые sqlite ResourceWarning сохраняются, сбоев/assert failures нет.
- Node regression PASS: русский текст/английский оригинал/fallback, форматирование
  без изменения source, hash показанного bundle либо null в draft/confirm,
  прежние delayed navigation/session failure guards. При расширении VM fixture
  забыли восстановить queue для второй итерации — test TypeError исправлен в
  фикстуре; фактическая UI логика не менялась ради теста.
- Независимый code review: существенных замечаний нет. На временных БД проверены
  blind gating, backup/restore, старое confirm до импорта → translation=None,
  чужой hash → отказ без изменения review. Эфемерный VM-тест подтвердил token
  propagation. Семантическая проверка переводов описана отдельно выше.
- Перед обновлением открытой вкладки: note пуст, status «Сохранено в SQLite»,
  0/30 confirmations. Созданный ранее сервер PID5737 обновлён на том же8765;
  reload восстановил current/filter/progress. В браузере видны русские titles,
  state/candidate/rubric и оба rationale. Английский state раскрыт и проверен.
- Открыта настоящая blind карточка421bda86: русские input тексты видны, ответов
  моделей нет, самостоятельная метка не выбрана, reveal не нажат. Возвращена
  исходная cdd196a0. Никаких draft/confirm агент не создавал.
  Screenshot api-ui-ru-blind-proof.png сохранён в artifacts/system-one-pilot/.

## Готовность

Русский UI оставлен открытым на http://127.0.0.1:8765/. Дополнительных API-запросов
и расходов0 (ledger summaries совпали с summary-delivery.json). 30 pending, labels0.
Резервная копия **с переводом** вне репозитория:
`/Users/nikitapasinin/Documents/ChatGPT/diplom-backups/system-one-pilot/20261025-ru-v1/`
(review/financial DB, translations JSON, SHA manifest). CLI restore в новый
`restore-validation-ru-v1.sqlite3`: integrity ok, 256 переводов, 30 pending, export0.
Raw labels/inputs и финансовый ledger не откатывались. Это тот же Mac, не внешний диск.

Финальная квитанция translation-ru-verification.json: 39 Python tests + Node PASS,
review без незакрытых замечаний, GitMark lint31 docs чисто, MkDocs strict0.68s,
diff check чисто. Общий Material advisory не является ошибкой сборки. Точное
значение ключа в новых source/results/translation JSON не найдено; сети при создании
перевода не было. Изменения не коммитились, push/публикация не выполнялись.
Screenshot api-ui-ru-proof.png показывает русский state и раскрываемый оригинал.
