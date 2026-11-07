# Доверенная разметка — 25.10.2026

## Новое решение инициатора

После просмотра LLM-ответов инициатор поручил доверить всю разметку связке
DeepSeek + Qwen3.8 и разбирать расхождения силами агента. Обращаться к нему
только при критическом противоречии, которое агент не может разрешить сам.
Это отменяет прежнюю обязательную ручную очередь/слепые контроли как gate.
Наблюдение инициатора не выдаётся за измерение независимой истинности меток.

Политика deepseek-qwen-agent-v1: два полных валидных согласных ответа без
дефекта → принять (включая законную uncertain); расхождение, дефект или technical
error → агент проверяет тот же state+candidate и rubric-v1, фиксирует отдельный
арбитраж с точными цитатами. Не чинить raw-ответы и не выдавать техническую
ошибку за uncertain. Неполнота применимости сама по себе не critical: uncertain
сохраняется и не идёт в бинарное обучение. Critical — существенная несовместимость
исходных фактов/правил или нарушение границ/происхождения, неразрешимое по
наблюдениям и исходникам, которое препятствует корректному решению. Сначала
расследует агент. Нового разрешения на дополнительные бюджеты/обучение нет.

## Разбор текущей очереди до применения

25 карточек дают согласие моделей без дефекта, в том числе одна uncertain.
Пять требуют agent adjudication: 3 расхождения, native placeholders, ошибка цитаты.
Агент прочитал именно исходный state+candidate и оба ответа; hidden task/future/gold
не использовались. Resolutions не называются человеческими метками.
Критических неразрешимых противоречий в этих случаях не обнаружено.

- 3f864f7c: uncertain — тип карты не установлен, применимость продуктового совета
  не доказана. Не превращаем неизвестное в уверенный бинарный ответ.
- 8e7f0c55: useful — открытие нового savings входит в текущий запрос; правила
  пополнения/предпосылки частично помогают действовать, а query не вся потребность.
- 696758e1: useful — явное исключение неподходящего credit-процесса для ATM
  shortfall полезно по прямому правилу рубрики, даже без полного решения спора.
- f8614990: irrelevant, defect=true — APR другого продукта не объясняет decline;
  missing-value placeholders остаются дефектом исходных данных и не идут в обучение.
- cfa9fdc7: useful — stacking правила помогают максимизации APY. Основание —
  валидный DeepSeek и наблюдаемый документ; невалидная цитата Qwen не исправляется
  и не учитывается как второй валидный ответ.

Локальный файл agent-adjudications-v1.json содержит причины/conditions/1–4 точные
цитаты и input SHA. Все5 прошли существующий validate_annotation без новых API.

## Применение и сохранение работы инициатора

За время самостоятельной проверки инициатор подтвердил6 карточек. Состояние
прочитано перед изменением, формы не содержали несохранённого ввода. Все6
confirmed/notes/first_label/reveal/audit сохранены **без изменения**, включая
useful вместо model uncertain вcdd196a0. Плановая запись f8614990 не применялась:
там уже было человеческое irrelevant. Исходные placeholders/defect модельного
ответа остались в истории. Поэтому фактически добавлены24 trusted labels:
20 llm_consensus, 4 agent_adjudication. Всего30 (11useful/18irrelevant/1uncertain),
human_review=true6, false24. Обязательных действий пользователю0.

Таблица trusted_labels отдельная/неизменяемая. До и после применения все строки
cards/reviews/review_events/review_translation совпали; контрольный SHA в
trusted-labels-summary.json. Экспорт30 записей — exports/trusted-labels-v1.jsonl.
Eligibility23 относится только к24 trusted rows: uncertain не идёт в бинарный
train. Human6 не проходили новую quality-фильтрацию и не объявляются training-ready.

Первая попытка применения транзакционно отвергнута: adjudication карточки
Business Bronze был привязан к другому снимку с тем же title, а для правильного
3f864f7c запись отсутствовала. Полный rollback подтвердил trusted_labels count0.
Привязка исправлена по точному row ID/input hash, literal quotes проверены снова;
повтор прошёл. Сырой ответ/траектория/человеческие решения не менялись. Эта ошибка
не скрыта и не дала частично принятого набора.

## Проверки и review

41 Python tests passed (первый полный запуск4.898s), Node regression PASS.
Новые тесты: полная транзакция/идемпотентность, validation/input binding,
model-consensus vs agent provenance, отсутствие fake human labels, сохранение
human draft, backup/export. При независимом review найден stale-tab риск: старая
форма могла прислатьautosave после accept и убрать accepted из export. Исправлено
серверным запретом draft/reveal/confirm для trusted row подBEGINIMMEDIATE. Regression
всех3 действий GREEN, reviewer повторил офлайн0.045s и закрыл замечание. HTML
accepted ветка проверена VM: controls редактирования/подтверждения не создаются.

report.py научился status trusted_labels_ready и раздельным human_confirmed/
trusted_accepted. Первая summary-trusted-delivery.json верно содержала human6 в
структуре, но старую константу «no confirmed human labels» в prose. Эта ошибка
отчёта исправлена новым summary-trusted-delivery-v2.json с human confirmations6;
исходная сводка сохранена, исходные измерения не подменялись.

Сервер обновлён на том же8765. Browser reload сохранил currentcfa9fdc7 и показал
«Принято30/30 · вам нужно0», все30 строк и отдельные источники. Принятая карточка
содержит причину/исходныеответы/перевод, без полей note/label/confirm. Агент не
вводил никаких человеческих меток. Старые ручные страницы не являются текущим
обязательным процессом. Бюджеты API остаются прежними; обучения не было.

## Финальная квитанция

41 tests passed (финальный повтор2.348s), Node PASS. GitMark strict lint31 docs
чисто, индекс406chunks; MkDocs strict0.69s, git diff check чисто. Новые source,
trusted metadata и adjudication JSON не содержат точного значения ключа.

Backup вне Git: /Users/nikitapasinin/Documents/ChatGPT/diplom-backups/system-one-pilot/20261025-trusted-labels-v1/.
Review/financial DB, экспорт и adjudications с SHA manifest. Restore в новый
restore-validation-trusted-v1.sqlite3 дал точное совпадение30 экспортных записей,
6 human/24 trusted; integrity ok. Это тот же Mac, не защита от потери диска.
Ledger summaries в точности совпали с исходной summary-delivery.json: новых
API-вызовов и расходов0. Source/raw/human решения не переписывались.

Browser показывает30/30 принято, вам нужно0; вкладка оставлена открытой.
api-ui-trusted-proof.png сохранён; обязательных форм для принятых меток нет.
Верификация в trusted-policy-verification.json. Новое правило записано в
канонической wiki и workflow; будущий агент не должен снова требовать массовый
human audit. Никаких commit/push/публикации/обучения не было.
