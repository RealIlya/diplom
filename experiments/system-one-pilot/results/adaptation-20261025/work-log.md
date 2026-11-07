# Доменная адаптация — журнал25.10.2026 (Asia/Novosibirsk)

Инициатор после frozen сравнения поручил реализовать следующий план: независимые
данные, одна базовая модель, CE/Brier, native агентная проверка, решение о RLCD.
Автор реализации и измерений — Codex. Метки — согласованная DeepSeek/Qwen policy,
агент разрешает обычные споры. Старые30 train labels не переиздаются.

Исходная рабочая копия сохранена git-status-before.txt/git-head.txt и ignored
working-diff-before.patch. Прежний comparison и его artifacts остаются неизменны.
Полный Python baseline известен:79/80, один прежний тест презентаций.

До новых прогнозов уточнено: dev всего5семейств, не6. Split не меняется.
Используем2 calibration +3 validation families. Ранее изученное task_023
семейство обязательно calibration, а не validation. Выбор остальных по hash,
не по результатам. Test не участвует. Новый бюджет не создаётся: коллекция
$1/разметка$0.50 совокупно с прежними calls. На старте учтено collection
$0.059315396 (фактически.051000296 + верхние резервы двух4xx), annotation
$0.095484127; unresolved0. Остатки.940684604 и.404515873.

Рабочие решения агента, не приписываемые руководителю: KEV0.8B head-only,
5new train families, до2tasks/dev family, target100 новых cards, max10/family.
Frozen/CE/Brier используют один backbone+LoRA; это pilot только head adaptation,
а не полный fine-tuning. Параметры обучения/calibration заранее в protocol.
По прежней strict-schema annotation серии60calls/$0.046410504 оценка100 новых
пар ~$0.1547, scenario x2 ~$0.31; не гарантия. Резерв на каждом запросе по верхним
тарифам иmax_tokens2048, остановка до cap. Для13новых эпизодов историческая
оценка ~$0.133, сценарная исходная оценка $0.936–4.68 может превысить остаток:
количество не гарантировано, cap не повышается. Часть остатка планируется на
online pilot; перед ним отдельная оценка из фактических новых episodes.

Попытка запуска collect отклонена автоматическим approval review ДО создания
процесса/HTTP. Причина: нет признанного им явного разрешения на новые train/dev
payload именно во внешние DeepSeek/DeepInfra destinations. Обходов/повторного
запуска нет. Отправлен конкретный async вопрос с данными/ролями/маршрутом
OpenRouter→DeepInfra/общими лимитами. Ответ обязателен, timeout не согласие.
До ответа выполняется только локальная реализация/тесты. Все calls/cost пока
остаются исходными. Предыдущая запись «запущена» означает dispatch-попытку;
фактического нового сбора на этот момент нет.

Локальные части Task2/3 реализованы без внешних вызовов. Head loss — scalar
binary Brier или CE; optimizer отбирает только hard nondefect train, last20epochs,
температура только calibration. Индекс/feature bytes/original head имеют hashes;
потеря минимального покрытия cache останавливает training. Online source сохраняет
raw native trajectory и projected actor payload отдельно; не-KB/errors/policy/tools
не изменяются. Local failure/empty selection → оплачиваемый LLM fallback;
invalid completed selector answer → BM25, PaidClient errors не обходятся.
ALL evaluator запрашивается явно, native default model заменяется в transport
на заявленный DeepSeek и получает отдельную judge роль/call ID. Summary включает
failed/missing tasks и все API роли, запрещает подмену ALL на ENV-only.

Реальный local smoke: native MLX KEV0.8B → CPU head features одной СТАРОЙ train
карточки. CE и Brier по3 optimizer steps обновили head с конечными gradients;
воспроизведение native probability по кешированным features имеет delta~1.75e-8.
Это инженерная проверка на1train-примере, не adaptation-quality результат,
не новая train/dev серия и не выбор гиперпараметров. native-smoke.py/json сохранены.
Отправлен независимый read-only review всей новой реализации; API/GPU reviewer
не запускает. Разрешение внешнего collect всё ещё требуется, обхода не было.

Получено прямое разрешение инициатора в ответ на полный payload/destination/budget
вопрос: «Разрешаю в прежних лимитах». Сценарии13 синтетических задач→симуляторDS;
observed истории/KB→actorDS/annotatorsDS+Qwen; criteria→толькоjudgeDS.
OpenRouter→DeepInfraFP8/BF16, общие caps$1/$0.50, test исключён.
external-approval.json привязан к frozen protocol SHA. Это новое доверенное
подтверждение снимает причину auto-review отказа; повторяем тот же collect.

Независимый reviewer подтвердил2P1: vacuous all([]) успех native NL evaluator и
swallowed BudgetError при reserve>remaining. Оба исправлены после RED repro:
Counter полной assertion coverage до native reward и stop на BudgetError в
collector/online. Дополнительно source hashes не открывают unselected task bodies,
selected train tasks проверяются отдельно. 68/68 целевых tests GREEN.

Полный unittest после review:98/99, прежнее падение test_presentations ожидает
единственный PPTX и не учитывает уже существующий research-talk-15min. Файл не
удалялся и тест не подгонялся. Лог /tmp/adaptation-full-tests.log.
Фактический collect стартовал после разрешения: task_007 completed, затем task_088;
новый сбор имеет отдельный namespace adaptation-v1, бюджет общий.

Первая MkDocs проверка после добавления nav выявила неправильный отступ новой
строки YAML; исправлен. Это ошибка документации, API/данные не затронуты.

MkDocs v2 parse исправлен; strict сборка теперь падает исключительно на3 чужих
новых jira-autonomy планах вне nav. Их не редактируем. Дополнительная контрольная
сборка использует /tmp overlay с not_in_nav только для этих3 файлов; исходный
конфиг сохраняет строгую проверку ссылок.

На контрольной точке4/13 episodes completed/user_stop, ошибок0; первые train,
calibration и validation задачи записаны. Outcomes не используются для смены
плана. Бюджет и immutable call journal остаются общими.

До extraction/новых labels добавлен описательный cheap offline контроль:
постоянная вероятность train useful prevalence и within-snapshot BM25 AUC.
analysis-addendum-before-labels.json фиксирует расчёт и исходный protocol SHA;
split/training/calibration/online план не меняется. Порог по validation не выбирается.

Сбор остановился на task_075: HTTP429, DeepInfra engine_overloaded,
upstream_provider_shared_pool.6 завершённых эпизодов и1 failed сохранены.
Исследован оригинальный body без повторного inference; официальный OpenRouter
описал отличие HTTP отказа до acceptance от ошибки внутри200 после acceptance.
Добавлено узкое ручное reconciliation с exact response hash и проверкой metadata.
Generic429/timeouts/5xx всё ещё блокируют серию. RED→GREEN2tests, всего70/70.
Полный резерв$0.0241173 сохранён, actual неизвестен (не приравнен к0);
старый failed task_075 не повторяется. Продолжаем только ещё не начатые задачи
в том же порядке и caps. Подробный receipt reconciliation-429.json.

Task_041 failed JSONDecodeError на последнем actor response: completion_tokens2048,
reasoning881, finish_reason tool_calls,4валидных tool JSON и5-й truncated79chars.
Локальный json.loads воспроизводит ошибку без API. Полный платёж известен;
collector переходит к следующей закреплённой задаче. Max_tokens/actor settings
не меняем после исхода, task_041 не повторяем. tool-json-failure.json.

Коллекция завершена:13попыток,10completed/user_stop,3failed (task075HTTP429,
task041/task039JSONDecodeError на max_tokens2048). Новый known actual$0.096949863,
всего collection actual.147950159, charged_or_held.180382559, unresolved0.
Extraction:36snapshots/977pool rows/100selected,10накаждуюиз10семей,errors0.
Tokenizer предупреждал о10734>8192 на полном неadmitted входе; encoder не
запускался, выбранные100 проходят native serialization4096 без truncation.
Новые роли50train/20calibration/30validation. Annotation preflight estimate
~.1547,scenariox2.31, remaining.404515873; capнеповышается, гарантий100парнет.
Запускается strict-schema v2 двойная разметка в разрешённых destinations.

Annotation остановилась после22valid на HTTP429 для29f55515…/DeepSeek.
Оригинальный body подтверждает тот же engine_overloaded/sharedpool; manual
reconciliation exacthash, весь reserve$0.0064698 удержан. Запрос не повторяется.
Создан source-bound technical_error annotation record с точным ledger raw,
без semantic label. Qwen и остальные ещё не отправленные calls продолжаются;
этот ряд требует agent adjudication. reconciliation-annotation-429.json.

Во время adjudication, ДО import/trust/dataset/предсказаний, сохранён черновик
agent-adjudications-v1.json и новая рабочаяv2. Исправлена первоначальная
слишком строгая трактовка row29f55515…: диагностические вопросы поdebit decline
полезны при неизвестном коде как partial next step, без утверждения причины.
Согласовано сc41d5d…: ссылка на обязательный отдельный fraud protocol — нормальная
cross-reference, когда условие и запрет premature unlock сохранены, не дефект
подготовки. v2 принимаетuseful/defectfalse;rubricнеизменна. Скрытые task критерии и predictions при этом не просматривались; hard counts
по train/calibration/validation ещё не вычислялись и gates для решений не использовались.
Первые рабочие размышления сохранены, ещё не были принятыми labels/quality results.

Прерывание чата остановило процесс разметки:111ответов сохранены, последний
Qwen be759760… остаётся reserved без response. Outside-sandbox pgrep подтвердил
отсутствие процесса; повторных inference нет. Полный резерв$0.0097036 удержан.
Readonly GET/key архивирован: account usage.340240774, это aggregate не receipt
конкретной generation. IAB и Comet Activity требуют входа; generation id не успел
сохраниться. Протоколunknownblocks не обходится. Запрошено явное исключение:
вручную учесть полный upper bound, сохранить technical error без повтора,
продолжить только оставшиеся карточки в общемcap.50. До ответа платныеcallsстоят.
Локально все полученные disputes рассмотрены, draftv2 содержит15решений.

Локальная защита от повторения interrupted-response проблемы: generation_id из
X-Generation-Id сохраняется в новой append-only api_receipts до чтения body.
Тест имитирует body timeout после headers и проверяет сохранённыйid, запретdelete
и запретповтора. RED→GREEN,71/71SystemOne tests. Это не возвращает id старого
прерванного запроса. Протоколunknownblocks и pending approval не обойдены.
Все15draft adjudicationsv2 проверены validate_annotation/exactquotes/inputhash.

Получено явное разрешение: «Учесть максимум и продолжить».
interruption-approval.json фиксирует exactcall/requestsha/$0.0097036/cap.50.
Atomic append-only reconciliation сохраняет fullreserve, actualNULL, statusunknown.
Вместо отсутствующего body добавлен ЯВНЫЙ local-client-interruption-receipt-v1
(origin NOT provider response, provider_response_received=false, безchoices/model
annotation). Его hash/source закреплены в api_receipts и annotation technical_error.
Это не восстановленный или выдуманный ответ Qwen. Исходный запрос не повторяется.
111полученных+1technical record сохранены; следующие calls продолжаются в том жеcap.

Первый detached restart ошибочно разрешил symlink venv/python в basePython через
Path.resolve. Preflight прошёл, единственныйновыйDS request ab722… получил явный
HTTP429 engine_overloaded/sharedpool. Валидных model labels этот subprocess
не создал. Fullreserve$0.0071298 учтён по прежнему проверенному HTTP методу,
originalrequestнеповторяется, technical record сохранён. Исправлен launcher path:
абсолютный путь кvenv symlink БЕЗ resolve; старый worker receipt/log сохранены.

Annotation завершена:200записей/190valid/10technical;100приняты,78consensus
и22agent adjudication. Старые30/6human решений не менялись. Final draftv2
запечатан agent-adjudications-final-v1.json, exportSHA и audit metadata сохранены.
Source import проверил все requests/responses по immutable ledger, включая явный
local interruption receipt (не provider answer). Новых humanreview0.
Dataset130: train80/hard73/8families (26useful47irrelevant), cal20/hard17/2families
(8useful9irrelevant), val30/hard27/3families (5useful22irrelevant). Все gatespassed.
Запущен offline native featurecache, backbone+LoRA frozen, labels не в encoder.

Offline featurecache130/130, errors0, 44.184s включают load4.971s; MLXpeak2.396GiB, labelsнеencoder. CE/Brier20epochs выполнены без ошибок. Train73/cal17/val27. Validation frozen9/27, CE20/27, Brier21/27; train-prior22/27. Температуры3/published/published, cal-only. Все780predictions и18групп метрик независимо пересчитаны sklearn1.7.2/numpy2.5.3, maxdelta1.11e-16. Первая попытка verification ошиблась именем поляdefect, до расчёта/выхода; исправлено без повторной inference.

Online estimate: прежние ENV3tasks $0.018044773;6arms~$0.108268638, scenariox3+judge/selector$0.524805914, available$0.819617441. Это оценка, не гарантированный максимум; атомарный ledger останавливает до превышения$1. Detachedworker11231, absolutevenvpathбезresolve, последовательные6arms, оригинальныеepisodeIDsнеповторяются.

Проверки после durable-header fix:71/71targeted,101/102full (единственное pre-existingPPTX), NodeUIpass, GitMark31pass, MkDocsstrictbuildpass без overlay. Три Jira plans прежнего снимка больше не мешают текущей сборке; чужие файлы нами не удалялись. Source snapshot выполняемого runner сохранён отдельно во время первого arm с SHA в code-manifest-online-start.json. Native035 completed/reward1 ACTION; native061 completed/reward0 DB — завершение диалога не гарантирует успех.

Native arm завершён:035reward1 ACTION,061reward0 DB,041failedJSONDecodeError (все calls known/complete; последний response{'call_id': 'online-adaptation-v1/native/task_041/039/agent', 'finish_reason': 'tool_calls', 'completion_tokens': 2048, 'max_tokens': 2048, 'tool_calls': 4, 'actual_usd': 0.000719093, 'technical_error': 'JSONDecodeError', 'rerun': False}). 041неперезапускается, параметров не меняем. Переход кследующему arm по протоколу;отказ входит в denominator3.

BM25armзавершён:035reward1user_stop29.1s,061reward0max_steps187.4s,041reward0max_steps222.0s.1/3success,3/3ALLcompleted,0technical. Наnative041техническийотказсохранён; сравнениенаallplannedнеотбрасываетего. LLM035reward1,112.3s;нипорог,ниsplit,ниactorlimitsвпроцессе неменяются. APIcachetokensбудутпоказаныотдельно: fixedarmorder и sharedprovidercache ограничивают причинное толкование затрат/latency.

LLMarm завершён14:30:34UTC:035reward1/112.33s,061reward0user_stop/826.89s,041failedJSONDecodeError/519.9s. 1/3success,2/3ALLcompleted; technicalfailure сохранён без повтора, fallbackcost включён вledger. Начат frozen arm, затем CE/Brier. До результатов не менялись гиперпараметры/порядок/упаковка/API actor2048.

Frozen061 остановлен: URLError безHTTPstatus/body/headers/generationid на call022agent, максимум$0.021303, requestSHA90244879bc2b8c03d6957cd5b6a1bec9e5af90f999638380c17d2fcc81e5fd02. Worker корректно остановился, frozen041/CE/Brier не стартовали, исходныйэпизоднеповторяется. Предыдущее разрешение fullbound относилось к конкретному Qwen annotation request, поэтому новое unknown не учтено произвольно. Требуется receipt либо отдельное исключение. Официальные OpenRouter docs25.10: GETgeneration требуетid; Analyticsдляпоколений требуетmanagementkey; текущийinferencekey не заменяет login/dashboardreceipt.

Подготовлена create-only continuation: frozen-v2 импортирует verbatim035completed и061failed, запускаеттолько041; затемCE/Brier. Никаких новыхpaidcallsпослеunknown. RED2continuationtests → GREEN73/73targeted,103/104full (прежнийPPTX). Независимая реконструкция из agent-visible native trajectories151events (BM25:83, LLM:46, frozen:22), всеstateSHA/poolsize/selectedobservedIDs/renderedtokens≤4096 совпали. Nativeevents0. MkDocsstrict иGitMark31pass; это промежуточная, не финальная серия.

Read-only analytics/meta попытка с существующимkey получила403, generationid не восстановлен; invoice/callbody не выдуманы. Источники официальных OpenRouter API docs и receipt записаны в online-recovery-summary.json. Платных inference0 после остановки. Продолжение7эпизодов требуетответа на pending вопрос. Локальные проверки и оба обученных checkpoint готовы; окончательного online/RLCDвывода нет.

Снимок остановленной серии ledger-paused-v1.sqlite3 прошёл integrity_check; budget-paused-v1.json сохраняет knownusage и upperbounds отдельно. Source-continuation-v1/manifest — подготовленный, ещё не использованный paidrunner. Final текущей остановки:73/73targeted,103/104full (PPTXизвестный),151observed eventsverified, GitMark31/MkDocsstrict/diffcheckpass. Не начатыхэпизодов7; pendinguserexception не заменяется ожиданием или общей APIавторизацией. Всеmetadata/rawhashes текущего состояния — artifact-manifest-interim-v1.json.

Получено явное разрешение инициатора «Учесть максимум и продолжить» для frozen061call022agent. online-interruption-approval.json привязан к requestSHA иcap$1. Atomic append-only reconciliation удерживает$0.021303 полностью; исходныйstatusunknown,responseNULL,actualNULL сохранены, не выдуман provideranswer. Отдельный auditreceipt. Исходный эпизод не повторяется; разрешены7 не начатых episodes через подготовленную continuation.

Свежий независимый read-only review continuation: Critical/Important/Minor0. Reviewerповторил2pureContinuationTests(2/2), сверил логи73/73targeted,103/104full. Отдельная локальная SHAпроверка послеcopyfile: оба frozen035/061 JSON byte-identical, прежнийselector-eventsполныйprefixnewv2. Ограниченияreview: исходныеlabelsemanticsнепереразмечены(принятаusertrustedpolicy), итогrunningсериипроверимпослевсехпопыток; аппаратнаянезависимаярепликациянедоступнавsingle-hostpilot. Train_secondsвключаетprediction/calibrationкакзаявленовотчёте.

Продолжение пересекло полночь Asia/Novosibirsk,26.10.2026. Frozen041 completed/reward0/terminationtimeout, elapsed942.9s; native timeout900 проверяется междуитерациями, текущие scoring/API не прерываются посередине (pinnedOrchestrator._check_timeout/is_done). Позднийpool33–34docs, selector≈46.4–46.8s безfallback. Это сумма покандидатных nativeforward, не single-cardlatency. Frozenитог1/3success,2ALLgraded/1technical,0missing. НачатCE.

CEarm завершён,3/3ALLgraded,1/3success,0technical. Исходы[{"task": "task_035", "status": "completed", "reward": 1.0, "termination": "user_stop", "seconds": 154.7389788749988}, {"task": "task_041", "status": "completed", "reward": 0.0, "termination": "max_steps", "seconds": 604.0924792500009}, {"task": "task_061", "status": "completed", "reward": 0.0, "termination": "timeout", "seconds": 937.8402159999987}]. НачатпоследнийBrierarm,035ужеreward1;061/041остаются.

Дополнительно сверены9 исходных KEV–Laya records/receipts с архивным manifest: всеSHAнеизменны. Summary/protocolнеперечисленывтомmanifest, этаSHAпроверканеутверждаетихпроверку. Экспериментыповторноневызывались; metadataописаниеoriginal-comparison-integrity уточнено до финальной поставки.

Последний Brier041 остановлен наcall005agent HTTP429; все18plannedэпизодов уже предприняты, новыхнет, повторовнебудет. Receipt metadata{"call_id": "online-adaptation-v1/brier/task_041/005/agent", "http_status": 429, "reserve_usd": 0.0160548, "request_sha256": "99e0eedab78d0675b93b68faaae4720cbd7343f25db4462a23c53b9bfb2d3b1d", "stored_response_sha256": "ae0f95919c59b77c6ef3b8a435fed8f68024f9991b2bfd189fd916b329826134", "retry": false, "error_metadata": {"provider_name": "DeepInfra", "provider_error_code": "engine_overloaded", "limit_source": "upstream_provider_shared_pool"}, "strict_body_parse": true, "accounting": "entire upper bound conservatively accounted under existing narrow rule"}. ПослеошибкиAPIзапросынеотправлялись; нетнеобходимостиобходитьunknownstopилипроситьрасширитьлимит радипродолжения. Сериязавершаетсясfailedattempt.


## Финал серии25–26.10.2026

Все18 planned эпизодов шести arms предприняты; missing0. ALL-оценено14,
technical failures4: Native041/LLM041 JSONDecodeError, Frozen061 URLError,
Brier041 HTTP429 engine_overloaded/sharedpool. Последний429 проверен строгим
parser/exactresponseSHA, полный$0.0160548 учтён по существующему narrow rule;
original request не повторён. Остатка planned задач нет, дальнейшего API после
ошибки не было. У каждого arm1/3 подтверждённых успехов — толькоtask035.
Общее graded подмножество всех6 — одна задача; это не18 независимых задач.

Online known$0.182158621, с полными unknown резервами$0.219516421. Collection
вместе с прежнимсбором known$0.330108780/held$0.399898980<cap$1; annotation
known$0.264627506/held$0.287930706<cap$0.50. Вместе known$0.594736286,
учтено$0.687829686; actual8 консервативно учтённых calls неизвестен, unresolved0.
Новый data overhead общий: known$0.266093242/held$0.313513742, не копируется
на каждый arm. CPU head/feature API$0, rental0₽, energy/amortization не измерены.
Cap не сбрасывался в полночь. Seed25 native; provider seed не отправлялся.

Решение в decision.json: пока не начинать RLCD. Узел CE/Brier лучше frozen по
согласию/balanced accuracy, но хуже train-prior по accuracy/Brier/NLL; native
успехов не добавилось. Малые3 семейства/5useful и4technical не обосновывают
дорогой следующий метод. Это не результат испытания не запущенного RL.
Предложения: сначала отдельный protocol для prefix reuse/батчирования,
простого threshold/calibration контроля и надёжного tool-call output; затем
расширить независимую проверку. Ничего из этих новых предложений не запускалось.

Проверки после завершения:73/73targeted,103/104full (единственный прежний
PPTX-list test), NodeUI pass. Отдельный final-integrity-verification повторно
пересчитал18 метрик по780 сохранённым predictions, maxdelta1.11e-16;
независимо проверил train-prior; исходнаяfrozen head совпала с initial, CE/Brier
веса изменены, температуры соответствуют cal. Original30export/newexport/
protocol SHA неизменны. Все284 observed selection events восстановлены из
native trajectories: state/pool/IDs/renderedtokens≤4096 совпали, emptypacks0.
Старые035/061frozen JSON byte-identical вv2. Freshreview findings0. GitMark31,
MkDocsstrict иdiffcheckpass. Canonical section13 обновлён вместе с задачей/
планом; section12 и9 original benchmark runfiles сохранены.

Финальные артефакты: budget-final.json, online-summary.json, online-audit.json,
observed-online-verification.json, final-integrity-verification.json, decision.json,
verification-final.json и artifact-manifest-final.json. История interim/paused
и все исходные ошибки сохранены. Итоговый read-only SQLite snapshot и исходники
в ignored artifacts; записи/веса/синтетические клиентские тексты не публикуются.
Commit/push/publish/reset и test-эпизоды не выполнялись.

Финализацияартефактов: sourcecore/testhash совпали с провереннымиsnapshots; ledger-final.sqlite3 read-onlybackup/integrity_checkok. code-manifest-final иverification-final фиксируютsource/hash/actualchecks. working-diff-final/git-status-final сохраняютгрязнуюрабочуюкопию, безGitmutations. Финальныйmanifestпишетсяпослеэтойзаписи; непрерывностьизмерений/финансов/источников подтверждена, обязательнойработыпопланунеосталось.
