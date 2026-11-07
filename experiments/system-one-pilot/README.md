# Воспроизводимые пилоты banking_knowledge

## Локальные проверки и CI

Обычные проверки используют `requirements-docs.txt` и `requirements-tools.txt`:
`python -m unittest discover -s tests -v`. Они не требуют локальных выгрузок,
весов или API. Тесты head-only обучения пропускаются, если не установлен torch.
Семь native-проверок запускаются явно в подготовленной среде пилота с закреплёнными
исходниками и данными τ-knowledge:

```sh
SYSTEM_ONE_NATIVE_TESTS=1 artifacts/system-one-pilot/live-venv/bin/python -m unittest discover -s tests -v
node tests/test_system_one_review.cjs
```

Native-проверки используют подставной HTTP и временные SQLite, не обращаются
к платным API и не изменяют журналы оплаченных серий. CI без исходников τ-knowledge
явно отмечает их как skipped. При изменениях native-интеграции нужен также полный
локальный запуск. [Запись подготовки к отправке в main 02.11.2026](results/repository-checks-20261102/work-log.md).

Результат и принятое решение — в [отчёте wiki](../../docs/gitmark/system-one-pilot.md).
Это инженерная диагностика scorer, а не завершённое сравнение native агентов.
Старые offline-метки предварительные, одного агента. Новый API-пилот ниже
подготовлен для human audit; подтверждённых человеком решений ещё нет.

<a id="api-pilot-v1"></a>

## Новый API-пилот — 25.10.2026

Реализация: `scripts/system_one_pilot/live.py`, `live_api.py`, `live_data.py`,
`review.py`, `review.html`, `rubric-v1.txt`. [Протокол до прогнозов](protocol-api-v1.md),
[подробный журнал](results/api-20261025/work-log.md),
[текущий статус](../../docs/gitmark/system-one-pilot.md#api-implementation-v1).
Старый offline CLI и результаты ниже сохранены отдельно.

**Текущая очередь завершена:** принято30/30 — 6 решений инициатора сохранены,
20 согласий DeepSeek+Qwen3.8 приняты автоматически, 4 спора разобраны агентом.
Обязательных ручных действий0. Действующее поручение: агент ведёт разметку сам,
к инициатору обращается только с критическим противоречием, которое не может
разрешить. [Политика](../../docs/gitmark/system-one-pilot.md#trusted-annotation-policy),
[журнал](results/api-20261025/trusted-policy-work-log.md),
[текущая сводка](results/api-20261025/summary-trusted-delivery-v2.json).

Пять заранее выбранных train-попыток: 3 `user_stop`, 1 `max_steps=80`, 1 HTTP404.
Все траектории сохранены. В пуле398 document-snapshot пар: 277 admitted при4096,
121 STATE_OVERFLOW, 0 CANDIDATE_OVERFLOW; очередь из8 снимков/3 семейств.

Первая двойная разметка v1: 42 валидных ответа, 18 технических ошибок. После
наблюдения ошибок формата агент закрепил **v2 strict JSON schema** и независимо
повторил **все те же 30 входов** двумя моделями, с прежней рубрикой; ответы v1
им не передавались. v2: 59 валидных ответов, 1 ошибка буквальной цитаты; 3 пары
расходятся, 1 содержит `uncertain`, 1 отмечена LLM как дефект. Ошибка не стала меткой.
Первичные v1-ответы сохранены. Это проверка процесса, не доказательство качества.

Сбор: API usage **$0.05100023096**, плюс максимум двух HTTP404 **$0.0083151**;
постоянный ledger с округлением вверх учитывает **$0.059315396 / $1**.
Разметка со smoke и обеими версиями: usage **$0.09548411104**, ledger
**$0.095484127 / $0.50**. Первоначальные блокировки auto-review сняты прямыми
ответами инициатора; после privacy-отказа официального endpoint тот же DeepSeek
закреплён на `deepinfra/fp8`, Qwen — `deepinfra/bf16`. Настройки privacy не менялись.
[Машиночитаемый итог](results/api-20261025/summary-delivery.json).

Все команды выполняются из корня проекта; `pilot_python` — отдельная среда,
в которой переиспользуются установленные torch/transformers:

```sh
python3 -m venv --system-site-packages artifacts/system-one-pilot/live-venv
artifacts/system-one-pilot/live-venv/bin/python -m pip install -r experiments/system-one-pilot/requirements-live.txt
pilot_python=artifacts/system-one-pilot/live-venv/bin/python
```

Команды воспроизведения и безопасного возобновления выполненных серий: Штатные исходники/веса должны быть получены и проверены по разделу
«Повтор с публичных источников» ниже. Ключ читается из корневого `.env`, без вывода:

```sh
"$pilot_python" -m scripts.system_one_pilot.live budget
"$pilot_python" -m scripts.system_one_pilot.live collect --episodes 5
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false "$pilot_python" -m scripts.system_one_pilot.live extract
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4 "$pilot_python" -m scripts.system_one_pilot.live runtime --device mps
"$pilot_python" -m scripts.system_one_pilot.live annotate --version 2
"$pilot_python" -m scripts.system_one_pilot.review import
"$pilot_python" -m scripts.system_one_pilot.review trust --adjudications artifacts/system-one-pilot/api-v1/trusted-labels-v1/agent-adjudications-v1.json
"$pilot_python" -m scripts.system_one_pilot.review serve --port 8765
```

Рабочий URL — `http://127.0.0.1:8765`, только loopback. После импорта достаточно
повторять последнюю команду для возобновления UI: SQLite восстанавливает
черновики, подтверждения, первую самостоятельную метку, раскрытие, фильтры
и текущую карточку. Переход сначала сохраняет черновик; при ошибке остаётся
на карточке. Конкурирующее устаревшее изменение отклоняется по revision.

Данные новой серии — `artifacts/system-one-pilot/api-v1/`: `trajectories/`,
`snapshots.jsonl`, весь `pool.jsonl`, выбранный `queue.jsonl`, `admission.json`,
исходные `annotations/` (v1), `annotations-v2/` (рабочая v2), `pilot.sqlite3`
проверки, `exports/`, `backups/`. Frozen plans и исходный code ZIP закрепляют
параметры/версии; импорт сверяет prompt, модель, call ID и raw с финансовым ledger.
**Денежный ledger отдельный и общий для всех `--root`:**
`artifacts/system-one-pilot/authorized-series-20261025.sqlite3`.
Новый каталог представления/данных не даёт нового бюджета. Не удалять и не
откатывать ledger, чтобы повторно оплачивать запросы. Уже оплаченные ответы
возвращаются из него; неизвестный исход удерживает reserve и блокирует серию.
Незавершённый native эпизод после crash требует проверки журнала; автоматического
replay с повторной оплатой нет. `extract` не перезаписывает прежнюю версию.

**Русский перевод, 25.10.2026:** по последующему поручению инициатора все тексты
для оценки в текущей очереди показаны по-русски: состояние, документы, названия,
рубрика, причины/условия и цитаты моделей. Английский оригинал раскрывается рядом;
названия продуктов, IDs, имена tools и технические значения сохранены. Это
вспомогательный перевод Codex, а не новый вход Laya/разметчиков. 256 уникальных
строк покрывают все 30 карточек; дополнительных API-вызовов и расходов нет.
[Журнал перевода и проверок](results/api-20261025/translation-ru-work-log.md).

Перевод хранится в отдельной неизменяемой таблице той же SQLite, входит в backup.
Копия с переводом проверена восстановлением:
`/Users/nikitapasinin/Documents/ChatGPT/diplom-backups/system-one-pilot/20261025-ru-v1/`.
Подтверждение и черновик передают хеш показанного перевода в audit; export включает
его только если при подтверждении эта версия была показана. Старым решениям
перевод не приписывается задним числом. Скрытые LLM-ответы и их переводы выдаются
только после reveal. Исходные cards/input hashes/annotations/progress при импорте
перевода не меняются. Исправление уже закреплённого перевода требует новой review
версии, а не незаметной замены текста в старых решениях.

Для восстановления перевода из сохранённого локального пакета (в штатной БД он
уже загружен; точный повтор безопасен):

```sh
python3 -m scripts.system_one_pilot.review translations --from-file artifacts/system-one-pilot/api-v1/translation-ru-v1/translations-ru-v1.json
```

В текущем UI accepted-карточки доступны для просмотра, оригиналы/переводы и
причины сохранены; ручное подтверждение не требуется. Экспорт — кнопкой «Экспорт JSONL».
Новые серии: тот же trust CLI принимает согласия; недостающие решения сначала
готовит агент, а не передаёт обычные споры инициатору. При истинной неразрешимой
критической проблеме остановить только затронутую часть и обратиться к инициатору.

Ручной режим сохранён для добровольных решений и истории. В нём: выбрать метку и причину → для слепого контроля «Сохранить и раскрыть» →
посмотреть ответы → «Подтвердить и следующая». Отложенная карточка, дефект данных
и метка «Неясно» — разные состояния. История до cutoff служит диагностике:
факт за пределами точного входа оценщика отмечается как дефект, а не скрытая
подмена входа. При общей ошибке моделей остановить очередь специальной кнопкой;
возобновление требует пересмотра рубрики и новой версии затронутых карточек.
Это решение агента, не новое согласование с инициатором.

Экспорт содержит принятые trusted labels и текущие подтверждённые человеком решения, версию входа,
исходные ответы и историю; черновики/deferred/defect не становятся метками.
Агент не создаёт человеческих решений: trusted-label-v1 явно human_review=false,
модельное согласие и агентный арбитраж различаются. Шесть исторических human
решений остаются human-review-v1. Текущий экспорт30 записей:
`artifacts/system-one-pilot/api-v1/exports/trusted-labels-v1.jsonl`.

```sh
"$pilot_python" -m scripts.system_one_pilot.review export --out /tmp/human-review-v1.jsonl
"$pilot_python" -m scripts.system_one_pilot.review backup --out /tmp/pilot-review-backup.sqlite3
"$pilot_python" -m scripts.system_one_pilot.review --db /tmp/restored-review.sqlite3 restore --from-backup /tmp/pilot-review-backup.sqlite3
```

Restore создаёт **новый** файл, не перезаписывает рабочую БД и не откатывает
финансовый ledger. Кнопка UI «Резервная копия» сохраняет обе БД online backup
с `integrity_check`; после каждого подтверждения создаётся такой snapshot.
CLI `backup` копирует указанную review БД; для ledger используйте отдельный
явный `--db artifacts/system-one-pilot/authorized-series-20261025.sqlite3`.
Копию надо перенести на независимый носитель для защиты от потери Mac/диска:
локальные snapshots защищают от повреждения рабочего файла, но не всего диска.
Бэкап ledger нужен для расследования, а восстановление старой копии не даёт
права забыть расходы после её даты.

Проверки без сети/оплаты:

```sh
"$pilot_python" -m unittest discover -s tests -p 'test_system_one*.py'
node tests/test_system_one_review.cjs
```

Браузерный smoke выполнен на отдельной `/tmp/system-one-ui-test/test.sqlite3`,
никакие его TEST ONLY решения не импортируются в реальную очередь.
На **новой** очереди MPS runtime проверен на реальных входах 364/1014/3364 токена:
0.923/0.250/1.361 s, finite logits; peak RSS 1.76 GB, MPS driver до 4.26 GB.
Все 30 сохранённых token IDs/decode/hash отдельно сверены с фактическим Laya batch.
Это одиночные измерения без оценки качества на длинном контексте.
Ранее runtime проверен отдельно на архивных train-наблюдениях
(`artifacts/system-one-pilot/archival-runtime-validation-v1/`); их соответствие
upstream задачам по-прежнему не подтверждено. Это технический runtime, без обучения
и без оценки качества. `probe-4096.py` отдельно проверяет полный тензор 4096
с явным синтетическим повтором токенов: он не создаёт карточек/меток датасета.

Фактический snapshot вне репозитория:
`/Users/nikitapasinin/Documents/ChatGPT/diplom-backups/system-one-pilot/20261025T065434Z/`
с `pilot.sqlite3`, `authorized-series-20261025.sqlite3`, SHA256 manifest.
Обе копии прошли integrity check; review восстановлена в новый
`artifacts/system-one-pilot/api-v1/restore-validation.sqlite3` без изменения рабочей.
Это тот же Mac, а не защита от потери диска. Через настоящий UI созданы также
`backups/pilot-20261025T065504583294Z.sqlite3` и пустой экспорт
`exports/human-review-v1-04fab9c15255464da5af15b742973a5c.jsonl` (0 подтверждений).
После вашей проверки кнопка экспорта создаст новый файл, не перезаписывая этот.

## Сохранённые артефакты

- `config.json` — окончательный протокол до разметки/модельных прогнозов; `config-v1-english.json` — отклонённый ранний профиль.
- `manifests/` — ошибочное разбиение, 97 задач в одной группе; **не использовать**.
- `manifests-v2/` — промежуточное разбиение до исправления cash-back ancestry; **не использовать**.
- `manifests-v3/` — действующее разбиение 57/20/20, 29 групп; 20 test ID не передаются в replay/model.
- `acquisition.json`, `checkpoint-manifest.json` — URL, ревизии и проверенные SHA-256.
- `admission-english.json`, `admission-multilingual.json` — по каждой паре число токенов и явный отказ при overflow.
- `annotation-selection.json`, `annotations-v1.jsonl` — выбор до прогнозов, хеши входов, цитатные диапазоны, причины и uncertain.
- `leak-report.json`, `archive-compatibility.json` — границы разбиения и неподтверждённое соответствие архивной ревизии задач.
- `results/ce-v1/`, `results/ce-v2/` — неизменённые raw prediction/training events и полные manifests двух запусков.
- `repeatability.json`, `errors.json`, `artifact-manifest.json` — повторяемость, ошибки и каталог локальных больших файлов.

Тела исходников, snapshot/queue, HTML разметки и head weights находятся в
`artifacts/system-one-pilot/`; публичные исходные веса — в `models/`. Они не входят
в Git. Это локальное хранение; общего резервного хранилища у проекта пока нет.
Повтор не перезаписывает прежний run: все выходные каталоги/JSON создаются эксклюзивно.

## Повтор с публичных источников

Из корня репозитория, Python 3.13. На другом устройстве задержки будут другими.
Нужны примерно 2 ГБ диска для исходников и одного checkpoint, больше для среды.
`fetch` обращается только к публичным HTTP-файлам и проверяет SHA-256; платных
inference API в коде нет. Таймаут оставляет `.part`: сохраните его как отдельную
неудачную попытку перед повтором, не подменяйте им проверенный файл.

```sh
python3 -m venv artifacts/pilot-reproduction/venv
artifacts/pilot-reproduction/venv/bin/python -m pip install -r experiments/system-one-pilot/requirements.txt
artifacts/pilot-reproduction/venv/bin/python -m scripts.system_one_pilot.fetch --out artifacts/pilot-reproduction/inputs
```

Далее для краткости `python3` означает этот интерпретатор с зависимостями:

```sh
pilot_cache=artifacts/pilot-reproduction
tau_source="$pilot_cache/inputs/source/tau2-bench-4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699"
laya_source="$pilot_cache/inputs/source/laya-68804629e8ccd9d616d48a40e87de9fabbeae069"

python3 -m scripts.system_one_pilot.cli prepare --tau "$tau_source" --out "$pilot_cache/manifests"
python3 -m scripts.system_one_pilot.cli replay --archive "$pilot_cache/inputs/source/published-prefix-20MB.json" --manifests "$pilot_cache/manifests" --out "$pilot_cache/replay"
python3 -m scripts.system_one_pilot.cli audit --queue "$pilot_cache/replay/queue.jsonl" --checkpoint "$pilot_cache/inputs/checkpoint" --laya-source "$laya_source" --out "$pilot_cache/admission.json"
OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python3 -m scripts.system_one_pilot.cli fit --queue "$pilot_cache/replay/queue.jsonl" --annotations experiments/system-one-pilot/annotations-v1.jsonl --split "$pilot_cache/manifests/split.json" --checkpoint-manifest experiments/system-one-pilot/checkpoint-manifest.json --checkpoint "$pilot_cache/inputs/checkpoint" --laya-source "$laya_source" --device mps --out "$pilot_cache/ce-run-1"
```

В sandbox MPS может быть недоступен при доступной GPU; фактические прогоны
выполнены вне sandbox. Для CPU есть явный `--device cpu`, без обещания той же скорости.
Входы/метки не меняются. Сохранённый `head.safetensors` называется
`adapted-head.safetensors`: это FP32 non-encoder state, загружаемый поверх исходного
checkpoint; это не самостоятельная новая foundation model.

Семантические task/family assignments, input hashes и метки повторяются; время
создания manifest и новые run IDs отличаются. Для воспроизведения нужны текущие
исходники этого репозитория: их хеши записаны в run summary. `ce-v1` создан до
исправлений review, `ce-v2` — после них; исходные записи не переписывались.

## Проверка разметки и границ

Локальный `artifacts/system-one-pilot/annotation-review.html` показывает все
91 вход и обоснование. Для нового review копировать JSONL в новую версию,
сохраняя `row_id`, `input_sha256`, цитату и происхождение; отдельно записывать
reviewer, disagreement и adjudication. `null` допустим только в исходной очереди;
fit принимает `useful`, `irrelevant`, `uncertain`, исключая последний из hard CE.
`quote_span` индексирует символы `input.candidate`, `char_span` исходной очереди —
символы body исходного наблюдаемого документа. Заголовок также поступает модели.

```sh
python3 -m unittest discover -s tests -p test_system_one_pilot.py
python3 -m scripts.system_one_pilot.fetch --out artifacts/pilot-reproduction/inputs --verify-only
```

Считать качество всего пула/агента по этим результатам нельзя: admission оставил
183/783 пары, разметка охватила 91 пару, hard dev — 27 пар из одной группы.
BM25 — собственное lexical re-ranking наблюдаемого пула с regex tokenizer,
`k1=1.5, b=0.75`, а не запуск native corpus retrieval. Его scores не вероятности.
P@3 — диагностический rank-only бюджет три фрагмента, без agent packer/rollout.
Native evaluator, эпизодический reward, ECE и окупаемость здесь не измерены.

## Frozen KEV–Laya сравнение 25.10.2026

Продолжает готовый экспорт `api-v1/exports/trusted-labels-v1.jsonl`, не вызывает
сбор, разметку или обучение. Параметры, pins, бюджет и правила исключений —
`results/kev-comparison-20261025/protocol.json`, дополнения до прогнозов и все
попытки — `work-log.md` рядом. Checkpoint/source receipts и сырые JSONL хранятся
в игнорируемом `artifacts/system-one-pilot/kev-comparison-v1/`.

```sh
python3 -m scripts.system_one_pilot.compare prepare \
  --out /tmp/kev-cohort-check.json
artifacts/system-one-pilot/live-venv/bin/python -m scripts.system_one_pilot.compare run \
  --arm laya --out artifacts/system-one-pilot/kev-comparison-v1/runs/laya-NEW
artifacts/system-one-pilot/compare-venv/bin/python -m scripts.system_one_pilot.compare run \
  --arm kev-0.8b --out artifacts/system-one-pilot/kev-comparison-v1/runs/kev-0.8b-NEW
artifacts/system-one-pilot/compare-venv/bin/python -m scripts.system_one_pilot.compare run \
  --arm kev-4b --out artifacts/system-one-pilot/kev-comparison-v1/runs/kev-4b-NEW
python3 -m scripts.system_one_pilot.compare summarize \
  --runs artifacts/system-one-pilot/kev-comparison-v1/runs/laya-NEW \
         artifacts/system-one-pilot/kev-comparison-v1/runs/kev-0.8b-NEW \
         artifacts/system-one-pilot/kev-comparison-v1/runs/kev-4b-NEW \
  --out /tmp/kev-summary-NEW.json
```

Запускать последовательно, в свежих процессах с доступом к Metal. Каталог каждого
запуска должен быть новым. Переменные offline задаёт runner до импортов моделей;
веса должны быть заранее загружены и сверены. Старое live-venv не обновлять.
Latency включает native tokenization, forward и CPU readout; загрузка и прогрев
отдельно. RSS и backend memory пересекаются в unified memory: их не складывать.
MPS transient allocator peak недоступен, показываются снимки после запросов;
для MLX сохраняется native peak после сброса счётчика перед измерениями.
Качество — только repeat0, uncertain исключается только из бинарных метрик.
Это описательное сравнение на train-карточках, не held-out test и не агентный reward.


## Независимые dev-семейства и адаптация KEV-0.8B

Поручение25.10.2026 продолжает frozen comparison. Протокол заранее сохранён в
`results/adaptation-20261025/protocol.json`, ход и неудачные попытки —
`work-log.md` рядом. Он закрепляет13 train/dev tasks, роли семейств, sampling,
параметры head-only CE/Brier и общие прежние caps$1/$0.50.
Прямое разрешение на внешние payload записано в `external-approval.json`.
Test исключён; прежние30 labels неизменны.

```sh
artifacts/system-one-pilot/live-venv/bin/python -m scripts.system_one_pilot.live \
  --root artifacts/system-one-pilot/adaptation-v1 collect \
  --plan experiments/system-one-pilot/results/adaptation-20261025/protocol.json
artifacts/system-one-pilot/live-venv/bin/python -m scripts.system_one_pilot.live \
  --root artifacts/system-one-pilot/adaptation-v1 extract \
  --allowed-splits train dev --target 100 --per-family 10
artifacts/system-one-pilot/live-venv/bin/python -m scripts.system_one_pilot.live \
  --root artifacts/system-one-pilot/adaptation-v1 annotate --version 2
artifacts/system-one-pilot/live-venv/bin/python -m scripts.system_one_pilot.review \
  --root artifacts/system-one-pilot/adaptation-v1 import
```

Споры разбираются по исходному observed input, с точными цитатами и input hash;
`review trust --adjudications FILE` принимает согласия и явные решения агента.
После create-only export:

```sh
python3 -m scripts.system_one_pilot.adaptation dataset \
  --protocol experiments/system-one-pilot/results/adaptation-20261025/protocol.json \
  --labels artifacts/system-one-pilot/adaptation-v1/trusted-labels-v1.jsonl \
  --out artifacts/system-one-pilot/adaptation-v1/dataset-v1
artifacts/system-one-pilot/compare-venv/bin/python -m scripts.system_one_pilot.adapt_head features \
  --protocol experiments/system-one-pilot/results/adaptation-20261025/protocol.json \
  --dataset artifacts/system-one-pilot/adaptation-v1/dataset-v1 \
  --out artifacts/system-one-pilot/adaptation-v1/features-v1
artifacts/system-one-pilot/compare-venv/bin/python -m scripts.system_one_pilot.adapt_head train \
  --protocol experiments/system-one-pilot/results/adaptation-20261025/protocol.json \
  --dataset artifacts/system-one-pilot/adaptation-v1/dataset-v1 \
  --cache artifacts/system-one-pilot/adaptation-v1/features-v1 \
  --out artifacts/system-one-pilot/adaptation-v1/heads-v1
```

Feature cache требует Metal; CPU head обучается только на hard train. Неудача
заранее закреплённых gates сохраняется и останавливает обучение. Calibration
выбирает только температуру; validation не выбирает параметры и epoch.
Online runner `python -m scripts.system_one_pilot.online run --help` запускается
отдельно для native/bm25/llm/frozen/ce/brier после оценки оставшегося бюджета.
ALL evaluator использует отдельный DeepSeek judge, полное покрытие assertions
проверяется до reward. BudgetError останавливает серию; частичный оплаченный
эпизод автоматически не переигрывается.

Фактические offline результаты:130/130 features, hard73train/17cal/27val,
20epochs обеих head; quality и независимая сверка — `head-summary.json` и
`numerical-verification.json` в results/adaptation-20261025. Train-prior и
BM25 ranking контроль — `cheap-controls.json`. Каждая команда create-only;
существующие каталоги не удалять и результат новым запуском не подменять.

```sh
artifacts/system-one-pilot/compare-venv/bin/python -m scripts.system_one_pilot.online run \
  --arm native \
  --protocol experiments/system-one-pilot/results/adaptation-20261025/protocol.json \
  --dataset artifacts/system-one-pilot/adaptation-v1/dataset-v1 \
  --heads artifacts/system-one-pilot/adaptation-v1/heads-v1 \
  --out artifacts/system-one-pilot/adaptation-v1/online/native-v1
```

Та же команда выполняется последовательно для `bm25`, `llm`, `frozen`, `ce`,
`brier` с отдельным каталогом arm-v1. Сценарий `run-online.py` рядом с протоколом
сохраняет свежий лог каждого процесса и останавливается при ненулевом exit.
Перед выполнением сверить согласованный остаток через `online-estimate.json`;
это новый платный запуск, а не команда просмотра сохранённых результатов.
Для независимой проверки offline чисел без inference — `verify-numerics.py`
в том же каталоге (create-only `numerical-verification.json`).

При неизвестном API-исходе серия останавливается. `--continue-from PREVIOUS_DIR`
допускается только после receipt/reconciliation: новый `--out` сохраняет ранее
успешные и failed попытки без повторного HTTP и запускает только не начатые
задачи. Проверяются protocol/dataset/head SHA, native ALL/model lineage и
соответствие prior task JSON метаданным receipt. Исходная папка не изменяется.
Подготовленный `results/adaptation-20261025/continue-online.py` перед запуском
проверяет отсутствие unresolved, hashes сохранённых frozen результатов и
последовательно выполняет frozen-v2/ce-v1/brier-v1. После отдельного разрешения на конкретный
unknown call этот сценарий выполнен: все7 оставшихся эпизодов предприняты. Историческая точка остановки и
предложение продолжения — `online-unknown-outcome.json` и
`online-continuation-proposal.json`; частичная сводка — `online-interim-v1.json`.

Итог серии25–26.10.2026: `online-summary.json` — все18 попыток шести arms,
14 ALL-оценок/4 technical failures, по1/3 подтверждённых успехов. Окончательные
каталоги: native-v1, bm25-v1, llm-v1, frozen-v2, ce-v1, brier-v1; frozen-v1
сохраняется как исходная прерванная попытка и не суммируется вторично.
Последний Brier041 HTTP429 остался failed без повторного запуска.

```sh
artifacts/system-one-pilot/compare-venv/bin/python -m scripts.system_one_pilot.online summarize \
  --runs artifacts/system-one-pilot/adaptation-v1/online/native-v1 \
         artifacts/system-one-pilot/adaptation-v1/online/bm25-v1 \
         artifacts/system-one-pilot/adaptation-v1/online/llm-v1 \
         artifacts/system-one-pilot/adaptation-v1/online/frozen-v2 \
         artifacts/system-one-pilot/adaptation-v1/online/ce-v1 \
         artifacts/system-one-pilot/adaptation-v1/online/brier-v1 \
  --ledger artifacts/system-one-pilot/authorized-series-20261025.sqlite3 \
  --out /tmp/online-summary-recheck.json
PYTHONPATH=. artifacts/system-one-pilot/compare-venv/bin/python \
  experiments/system-one-pilot/results/adaptation-20261025/verify-observed-online.py \
  --summary /tmp/online-summary-recheck.json --out /tmp/observed-recheck.json
```

Эти две команды только пересчитывают сохранённые результаты. Контроль цен и
токенов по ролям — `online-audit.json`, окончательный ledger — `budget-final.json`,
решение пока не запускать RLCD — `decision.json`. Сырые данные/веса остаются
в ignored artifacts; все выводы и ограничения — в каноническом отчёте wiki.

## Первый пакет расширения27.10.2026

План: `docs/superpowers/plans/2026-10-27-system-one-expansion.md`; протокол/журнал/
метаданные — `results/expansion-20261027/`. Исходные данные находятся в ignored
`artifacts/system-one-pilot/expansion-packet-v1/`; engineering logs и grouped
benchmark — в `artifacts/system-one-pilot/expansion-v1/`.

`python -m scripts.system_one_pilot.expansion prepare` создаёт только новый
протокол и каталог:9trainсемейств вне прежних130, target200. Это create-only
команда; уже закреплённый protocol не пересоздавать. `... expansion run` делает
реальные разрешённые API-вызовы: newcaps$.20collection/$.75annotation и общий
$1 на календарные сутки Asia/Novosibirsk, история предыдущих вызовов включена.
Не сбрасывать общий ledger ради новой серии. Unknown останавливает все роли;
автоматических повторов нет. Если queue-summary уже существует, run сверяет
hash очереди и продолжает только annotation, без повторного collect/extract.
Незавершённый эпизод без raw receipt требует расследования, не перезапуска.

Grouped scorer: `GroupedKev(adapter, group_size=5).score_many(state, pool)`;
контроль `BatchKev(adapter, group_size=5)` сохраняет старую сериализацию.
`online.select_evidence` принимает оба scorer через score_many, обычные scalar
callables совместимы. Старый online CLI/default и его frozen протокол не менялись.
Первый новый пакет только train; новые online quality сравнения пока не запускать.

Пакет завершён:200 новых доверенных меток,181 пригодна для бинарного обучения;
новый dataset330 строк, train15 семейств. Старые130/роли/dev сохранены.
Все400 ответов и11 ошибок цитирования сохранены;168 consensus/32 agent
arbitration, без новой проверки человеком. Known$.448283146 / held$.467319346
при общем дневном$1. Первый provider504 учтён полным максимумом, без повтора;
при annotation новых504 нет. Сводки — dataset-summary.json, annotation-summary.json,
budget-final.json в `results/expansion-20261027/`.

Продолжение неполного пакета по сохранённому разрешению выполнялось командой:

```sh
PYTHONPATH=. artifacts/system-one-pilot/live-venv/bin/python experiments/system-one-pilot/results/expansion-20261027/continue-packet.py
```

`provider_timeouts.py` допускает только exact provider504 с сохранённым ID
в scope первого пакета: append-only reconciliation/full reserve, без изменения
исходного api_calls. Прочие unknown блокируются. Не расширять разрешение на
новый namespace или иные ошибки молча.

Офлайн-экспорт после всех200 пар выполнялся один раз:

```sh
PYTHONPATH=. artifacts/system-one-pilot/live-venv/bin/python experiments/system-one-pilot/results/expansion-20261027/finalize-packet.py
```

Финализатор проверяет paid provenance, SHA/схему/цитаты и разбиение, принимает
согласия/арбитраж по сохранённой политике и создаёт новый `dataset-v1/` под
`expansion-packet-v1/`. Команда create-only; существующий экспорт не заменять.
Это train-only версия данных, не новый утверждённый протокол обучения или
независимой оценки. Полные ограничения и измерения — в каноническом отчёте
`docs/gitmark/system-one-next-stage.md#expansion-packet-v1-results`.
