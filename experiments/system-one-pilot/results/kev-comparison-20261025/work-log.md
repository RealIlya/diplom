# KEV-0.8B / KEV-4B / Laya — журнал 25.10.2026

Поручение инициатора: прогнать обе KEV на существующей размеченной выборке и
сравнить с Laya по качеству, скорости и памяти. Автор реализации/измерений Codex;
метки — прежние6human/20LLM-consensus/4agent, не новая human разметка.

До прогнозов закреплён protocol.json:30 исходных карточек,29hard labels,3семейства,
threshold0.5, опубликованные temperatures, 3warmups и3repeats, без обучения/HPO.
Идентичный английский input_text и вопрос, native tokenizers/serialization.
Laya4096, KEV8192; никаких усечений. Coverage и общее admitted-подмножество отдельно.
Это train-only описательная проверка согласия с доверенными метками, не held-out
генерализация и не качество полного агента. Дешёвые constant/BM25 контроли.

Исходные models/runtime/backbones закреплены ранее проверенными SHA. Бесплатное
скачивание публичных весов11.3GB; API/rental0. Старое live-venv не изменяется;
новое compare-venv изолирует transformers5/MLX. Полный source archive загружался
медленно, параллельно получены37 runtime/license/readme/test файлов из GitHub API
с тем же SHA; оба источника сохранены, пути совпадающих файлов не подменены.
Независимый read-only аудит предупредил о truncation defaults384 и implicit HF
download в Checkpoint.load; выбираем direct native local MLX loader, strict8192,
проверяем base/revision/flags. Head CPUfp32 калибрует logits сам, дважды T не делим.

Следующие результаты/отказы добавляются по ходу работы.

При передаче задачи в новый диалог проверено: установка compare-venv завершилась
с exit 1 из-за incomplete-download mlx_metal-0.32.4 (16.8/78.1 MB, timeout;
лог /tmp/system-one-kev-install.log). Загрузка моделей также завершилась с exit 1:
после полной проверки Qwen3.5-0.8B-Base загрузка двух шардов Qwen3.5-4B-Base
получила read timeout, затем DNS NameResolutionError huggingface.co. Частичные
файлы сохраняются; продолжать с теми же revision и local_dir. Сессии41658/3043
завершены, повторно ждать их не нужно. Это ошибки подготовки, модельных
прогнозов и результатов сравнения ещё нет; compare.py и его тесты ещё не созданы.

## Продолжение 25.10.2026 (Asia/Novosibirsk)

Перед продолжением прочитан `/private/tmp/kev-laya-handoff-2026-10-25.md`,
проверено грязное дерево; прежние изменения сохранены. Возобновлены установка
и публичные загрузки; новые журналы `/tmp/system-one-kev-install-resume.log`
и `/tmp/system-one-kev-download-resume.log`, прежние логи не перезаписаны.
Экспорт содержит input внутри card, а не в корне строки — runner читает эту
фактическую схему. SHA frozen export совпал с protocol.json, 30/29/3 подтверждены.

До любых модельных прогнозов дополнены правила агрегации (исходный protocol.json
не изменён): primary probability = repeat0; ошибка repeat0 не заменяется более
поздним успехом. Разброс max-min по повторениям отдельно. Задержка — медиана и
линейно интерполированный p95 всех успешных warm измерений, 90 запросов/arm при
полном охвате; ошибки и число успешных запросов отдельно. AUC учитывает ties=0.5,
F1 при нулевом знаменателе=0, balanced accuracy/AUC при одном классе=null.
BM25: query=observed state, IDF pool=кандидаты одного snapshot, включая uncertain;
основная ranking оценка — pair-weighted within-snapshot AUC, ties=0.5; pooled AUC
только описательно. Вероятностные метрики BM25 не вычисляются.

Тесты tests/test_system_one_compare.py: сначала RED (отсутствуют функции), затем
4/4 GREEN: immutability/hash/duplicates, отсутствие gold/future в request,
AUC ties/F1, missing/error/repeats/common cohort. Реализован compare.py с native
adapters, offline flags, отдельными subprocess CLI, сериализованными IDs,
JSONL с flush после каждого запроса. Ключи/API/пилотная БД не используются.
Команда проверки: `python3 -m unittest discover -s tests -p test_system_one_compare.py`.

Laya-v1 выполнил 90/90 forwards, но завершение receipt упало с FileExistsError:
общий write_json использует create-only, а runner пытался вторично писать receipt.
Артефакты v1 и исходный runner compare-runner-v1.py сохранены; v1 не является
итоговым завершённым прогоном, будет новый v2. Причина воспроизведена отдельным
тестом RED; исправление — отдельный receipt-start.json и create-only receipt.json
в finally. Дополнительно RED→GREEN проверки pinned весов по bytes/revision и
отказ сводки от running/несовместимого protocol/неполного completed receipt.
7/7 сравнительных тестов и 48/48 System One тестов GREEN в live-venv.

Независимый reviewer: serialization/temperature корректны; потребовал контроль
фактических весов и полноты receipt, добавлены. MPS не предоставляет публичного
peak allocator API: memory peak процесса измеряется ru_maxrss, backend MPS только
max post-request current/driver samples; transient peak MPS явно неизвестен,
его не выдаём за измеренный. MLX native peak доступен. Метрики памяти не суммируем.
Полный unittest discover: 76 тестов, 1 прежний failure
`test_all_stored_presentations_are_complete_packages`: в чужой рабочей копии
дополнительная research-talk-15min-2026-10-11.pptx, тест ожидает единственный deck.
Эти презентации и тест не изменялись. В обычном python3 System One suite не имеет
pandas, поэтому соответствующая проверка выполнена установленным live-venv.

Установка окружения завершена exit0: torch2.8.0, transformers5.17.0,
mlx-lm0.31.3, mlx/metal0.32.4, peft0.21.2, numpy2.5.3. Pip предупредил о
несовместимости унаследованного sentence-transformers5.1.2 с transformers5;
sentence-transformers в KEV runner не импортируется. Offline import smoke
`kev.checkpoint`, `kev.mlx_model` завершился IMPORT_OK вне sandbox.
Полные compare-freeze.txt/live-freeze.txt сохранены в ignored artifacts.
Laya-v2 завершён exit0. До просмотра качества решено использовать итоговую серию
из трёх моделей ПОСЛЕ окончания всех downloads/install, чтобы сетевой IO
подготовки не влиял на одну модель. Поэтому v2 сохраняется как промежуточная
техническая проверка; итоговая Laya-v3 будет с тем же протоколом и 3 repeats.
Модели не загружаются одновременно; пользовательские приложения не закрываются.

Runtime/model review завершён независимым агентом comparison_review (read-only,
без GPU). Исправления: summary проверяет protocol/status/полноту и дубликаты;
KEV перед load сверяет bytes+SHA каждого файла с receipt и adapter revision с
protocol.models; run receipt хранит SHA проверенных receipts. Для MLX peak counter
сбрасывается после load и после warmup, сохраняя все три фазы отдельно.
Добавлены common_latency и constant baseline на общем hard-подмножестве.
Фактическое оборудование sysctl: Apple M4 Pro, 12 CPU cores, 25769803776 bytes
unified memory. Hardware receipt сохранён. Системный swap не приписываем модели:
это всей машины, пользовательские программы не закрывались.

Подготовка до итоговой серии: 48/48 Python System One tests и 3 UI self-checks
PASS; GitMark preflight lint 31 файла чисто. Команды и хвосты в /tmp/kev-*tests*,
/tmp/kev-gitmark-preflight.log. Прогоны v1/v2 не выдаются за итоговую серию.

KEV-0.8B offline LOAD_ENCODE_OK: 30/30 входов, 340–3181 full tokens,
186 merged LoRA tensors, backbone BF16 + CPU head FP32, опубликованная
T=2.3510958125672174. Это load/encode smoke без прогнозов и без quality/speed
сравнения; лог /tmp/kev-load-smoke.log. Native mlx-lm load_model(Path) прочитан:
он читает локальные config и shards, без snapshot_download в этом пути.

## Итоговая серия и расчёт

Все4 набора публичных весов завершены и проверены по sizes/LFS SHA256;
models-verified.json и adapters-verified.json сохранены. Финальная серия driver:
`laya-v3` → `kev-0.8b-v1` → `kev-4b-v1`, все exit0. Отдельные subprocess,
offline, batch1; warmup3/model +90 измеренных запросов/model. Все30/30 admitted,
0 overflow/ошибок, общий quality denominator29. Source KEV37/37 sha совпали.

Первый summarize с относительными CLI paths упал до записи сводки:
Path.relative_to(absolute ROOT) получил relative folder. Причина воспроизведена
тестом test_summary_accepts_relative_cli_run_paths (RED), исправлено resolve()
в постобработке (GREEN8/8). Ни один forward/порог/метка/параметр не менялся;
повтор inference из-за postprocessing ошибки не нужен. Исходный inference runner
с hash2c639ca88c95bf9d437629a1fa0cd24788a673cfd892bb11570a8a3f0147c569
сохранён как compare-runner-final.py, все3 receipts содержат этот hash.

Команда расчёта:
`python3 -m scripts.system_one_pilot.compare summarize --runs artifacts/system-one-pilot/kev-comparison-v1/runs/laya-v3 artifacts/system-one-pilot/kev-comparison-v1/runs/kev-0.8b-v1 artifacts/system-one-pilot/kev-comparison-v1/runs/kev-4b-v1 --out experiments/system-one-pilot/results/kev-comparison-20261025/summary-v1.json`.

Фактическое согласие: Laya13/29 (F1.57895, Brier.46422, AUC.61616),
KEV-0.8B17/29 (F1.625, Brier.24506, AUC.75253),
KEV-4B24/29 (F1.73684, Brier.11054, AUC.95960). Always-irrelevant18/29:
одной accuracy недостаточно. BM25 within-snapshot AUC.6 на20 парах.
Request median/p95: Laya197.33/942.97ms; KEV-0.8B233.22/575.94ms;
KEV-4B1423.54/3513.78ms. Все270timings и вероятности сохранены в raw JSONL.
Вероятности повторов побитово совпали (max spread0).

Memory: peak RSS Laya2.631GiB / KEV0.8B3.099GiB / KEV4B3.556GiB НЕ полный
расход unified memory. KEV warm MLX peaks2.375/8.923GiB, load2.396/14.778GiB;
Laya MPS max post-request driver sample10.871GiB, current1.199GiB, transient peak
неизвестен. MPS и MLX counters не эквивалентны и не складываются с RSS.
Системный swap до серии~11.2GiB, после~14.6GiB — pressure/background ограничивают
сравнение latency. Успешный запуск не объявляется чистым аппаратным benchmark.

Независимая numerical-verification.json: scikit-learn подтвердил все6 quality
метрик с точностью1e-10; numpy p95 совпал, semantic+ID hashes30/model,
90 requests/model, порядок и общий cohort проверены. SHA paid ledger неизменен.
Вывод: на ЭТИХ train карточках KEV4B лучше по агрегатным quality metrics, но
медленнее и пропустил4/11 useful; перенос на held-out и итог агента неизвестен.
Код, условия/отказы/все попытки и ограничения зафиксированы до завершения задачи.

## Проверки завершения

- compare tests8/8, полный System One набор49/49, UI3/3, site tests5/5 PASS.
- Полный Python набор80:79 PASS и1 прежний FAIL в test_presentations:
  test_all_stored_presentations_are_complete_packages ожидает один pptx,
  хотя research-talk-15min-2026-10-11.pptx уже был в исходной рабочей копии.
  Чужая презентация и её тест не исправлялись в задаче сравнения моделей.
- Первый strict MkDocs build остановлен с3warnings: план не в nav и2 ссылки
  на неподдерживаемый `{#anchor}`. Исправлено по существующему HTML anchor
  шаблону и добавлен готовый план в архивную nav. Повторный strict build PASS.
- GitMark strict lint:31 файл чисто; index31/411chunks. Git diff --check PASS.
- Протокол и исходный frozen export не менялись; paid ledger SHA не изменился.
- Ветки/commits/push/publish/платныеAPI/аренда/обучение не выполнялись.

Итоговый канонический отчёт: docs/gitmark/system-one-pilot.md#kev-laya-comparison;
таблицы берутся из summary-v1.json, независимые проверки — numerical-verification.json,
команды/статусы — verification.json, raw hashes — artifact-manifest.json.
Открытого технического блокера для поставленного локального сравнения нет.
Не проверены held-out переносимость, причинный вклад loss/архитектуры и
итоговый native agent reward/стоимость. MPS transient allocator peak неизвестен.
