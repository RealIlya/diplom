---
node_type: report
title: "Атлас System One: проверка источников и результатов на 19.10.2026"
service: _platform
status: active
updated: 2026-10-19
links:
  relates_to: [docs/gitmark/README.md, docs/gitmark/system-one-training-review.md, docs/gitmark/rlcd-review.md, docs/gitmark/model-research.md]
---

# Атлас System One: проверка источников и результатов

**Срез источников: 19.10.2026.** Это доказательная подложка для исследовательского
атласа, а не новая постановка вместо [канонической](research.md). Сравнение
на τ-bench, обучение моделей и платные запросы при подготовке не проводились.
Числа ниже принадлежат авторам источников; собственных результатов качества
на `banking_knowledge` ещё нет. Подробные выжимки статей сохранены в
[обзоре обучения](system-one-training-review.md) и [разборе RLCD](rlcd-review.md).

## 1. Что могло означать «CD vs Brier»

**Интерпретация запроса, а не установленный факт:** вероятнее всего, речь о
**CE (cross-entropy) против Brier loss**, дополнительно — о том, меняется ли
эффект loss при наличии генерируемого рассуждения. Сокращение `CD` само по себе
не выбирает метод. В атласе эти оси нужно разводить:

| Термин | Что меняется | Что не следует из названия |
| --- | --- | --- |
| CE | Loss распределения по допустимым ответам | Не требует генерации объяснения |
| Brier | Квадратичная ошибка распределения | Сам по себе не является RL |
| Knowledge distillation | Источник targets: ответы/распределения учителя | Не задаёт автоматически CE, Brier или наличие rationale у student |
| RLCD в Laya/SBERT2S1 | Оценка градиента proper-score reward на зашумлённых logits | Не обучает текстовые рассуждения |
| RLCD в OpenJev | Proper-score readout и обучение распределения генерируемых rationale | Один запрос не означает один forward pass |
| LoRA/QLoRA | Какие параметры обновляются и как хранятся веса | Не альтернативная функция потерь |
| Temperature scaling | Преобразование logits после обучения | Не дообучение банковского знания |

Отдельно существует **Reinforcement Learning from Contrastive Distillation**:
статья Yang et al., arXiv:2307.12950v3, 16.03.2024, ICLR 2024. Там пары
предпочтений строятся из ответов на контрастные prompts, затем обучается
preference model и применяется RL. Это другой RLCD, не **Reinforcement Learning
for Calibrated Decisions**. [Первичная карточка статьи](https://arxiv.org/abs/2307.12950v3).

### Формулы для сопоставимого эксперимента

**Предлагаемое обозначение:** $p_\theta(k\mid x)$ — выход одного фиксированного
узла; $t_k$ — target, сумма $t_k$ равна 1. Для hard label $y$ имеем
$t_k=\mathbf1[k=y]$.

$$
L_{\mathrm{CE}}(p,t)=-\sum_{k=1}^{K}t_k\log p_k,
\qquad
L_{\mathrm{Brier}}(p,t)=\sum_{k=1}^{K}(p_k-t_k)^2.
$$

**Математическое пояснение:** при неизвестном исходе $Y\sim q$ оба expected
loss минимальны при $p=q$, если допускается любое распределение и достигается
глобальный минимум. Это не равенство градиентов, поведения оптимизатора или
качества конечной нейросети на новой области. Для бинарного случая сумма по
двум классам равна $2(p_{\mathrm{true}}-y)^2$; выбор этой нормировки нужно
зафиксировать во всех таблицах и коэффициентах. Общая теория proper scoring:
[Gneiting и Raftery, JASA 2007](https://doi.org/10.1198/016214506000001437).
Библиография подтверждена предыдущим обзором; полного повторного чтения этой
статьи в данном срезе не было.

**Предлагаемая первая проверка:** одинаковые checkpoint, encoder/head,
training rows, tokenizer, train budget и seeds; различается только CE/Brier.
Честное сравнение требует сопоставимого dev tuning каждого loss, а не одного
удачного learning rate для одного метода. Raw и откалиброванные результаты
публикуются отдельно; temperature подбирается без test.

## 2. Модели: какой объект реально можно сравнивать

| Кандидат | Проверенное устройство / граница | Следствие для атласа |
| --- | --- | --- |
| Laya English | ModernBERT-large, 421M, typed decisions без генерации; default context 512 | Компактный локальный scorer; нельзя передавать полную банковскую историю с молчаливым truncation |
| Laya Multilingual | mmBERT-base, 322M, default 1024; до 8192 при явной настройке | Проверять длину полного запроса и явно выбирать checkpoint |
| Laya Typed-Decisions | 421M, default 1024; специализация четырёх workflow | Уже адаптированная чужая модель не заменяет «до обучения на наших banking данных» |
| KEV-4B | Qwen3.5-4B-Base + LoRA + pointer head, prefill-only | Может оценивать данные варианты; не генерирует произвольные tools/аргументы |
| KEV-0.8B | Отдельный малый checkpoint | Автор прямо не рекомендует готовый checkpoint для tool-call routing |
| OpenJev-RLCD | Research training loop генеративного Qwen3-1.7B | Ветка изучения reasoning, не готовый одношаговый Laya backend |
| TypeSafe Jev | Hosted typed-decision API, внутренний training recipe не опубликован | Справочная мотивация; исключён из основной реализации решением проекта |

Laya: [model card](https://huggingface.co/convaiinnovations/laya), прочитана
19.10.2026. Карточка заявляет Apache-2.0, но её рекламная фраза о математической
калибровке не заменяет измерения в нашем домене. Существующее закрепление весов:
[`55cf4c4…`](https://huggingface.co/convaiinnovations/laya/tree/55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851).
Длина окна основы не равна проверенной длине конкретного адаптированного scorer.

KEV-4B: [model card](https://huggingface.co/jaredpalmer/kev-4b), срез 19.10.2026,
указывает релиз весов 24.09.2026, revision `139fdd94`, temperature 2.41.
**Served 65536** токенов состояния и **validated 8192** — разные показатели;
train states не длиннее 7552. В карточке есть MLX-замеры на **M5/32 GB**,
но они не являются замерами на нашем M4 Pro/24 GB.
[Закреплённые веса](https://huggingface.co/jaredpalmer/kev-4b/tree/139fdd94f1b6a6ad80cc15e08fcb99cac885a101).

KEV-0.8B: [ограничения карточки](https://huggingface.co/jaredpalmer/kev-0.8b#limitations-and-trade-offs)
сообщают падение When2Call development 0.260 → 0.167, test 0.233 → 0.133.
Это конкретный отрицательный результат исходной модели, не доказательство
невозможности её адаптации и не измерение на τ-bench.
[Закреплённые веса](https://huggingface.co/jaredpalmer/kev-0.8b/tree/9a45d25eb2ab761841196625383fa1dff0e56c1e).

TypeSafe: [публикация от 15.09.2026](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
называет RLCD и описывает типизированный интерфейс. Заявленные ускорения
получены в условиях поставщика; эталонами части workflow выступают ответы
других моделей. Типовая корректность выхода не доказывает истинность решения.
Отсутствие открытого внутреннего рецепта не позволяет считать OpenJev точной
репликацией Jev.

## 3. Что в открытом training-коде подтверждено

### KEV: штатный Brier-флаг — добавка к CE

Проверен [`kev/train.py`, commit `0fe8fc97c2bcc247fa3efb6e5c32af4e99770e91`](https://raw.githubusercontent.com/jaredpalmer/kev/0fe8fc97c2bcc247fa3efb6e5c32af4e99770e91/kev/train.py),
функция `question_loss`, строки 34–54:

- hard-label ветка сначала вычисляет CE;
- `brier_w` добавляет к CE взвешенный Brier;
- soft-target ветка возвращает CE раньше, до проверки `brier_w`;
- для ordinal `score` возможна отдельная добавка ranked probability score.

**Инженерный вывод:** эксперимент «чистый CE против чистого Brier» требует
явного выбора нового loss branch и проверки формулы/маски вариантов. Запуск
существующего `brier_w` следует называть **CE + λ·Brier**. До выполнения этой
правки pure-Brier trainer нельзя показывать как готовый компонент.
Опубликованные инструкции допускают `--init_from` и собственный JSONL;
проектный adapter и dataset converter ещё должны быть реализованы.

### Laya/SBERT2S1: шум в logits и генерация rationale — разные вещи

Проверен [`research/s1/objectives.py`, commit `a3a0637264adfb35c6b1c6544cb6392d69fcedb0`](https://raw.githubusercontent.com/pritamdeka/sbert2s1/a3a0637264adfb35c6b1c6544cb6392d69fcedb0/research/s1/objectives.py).
Варианты `Proper`, PG и Reparam нельзя автоматически подписывать «Brier»:
proper reward включает log/spherical score, а для ordinal вопросов ещё RPS.
PG использует случайные возмущения logits; текстовых reasoning tokens здесь
нет. PG-LOO меняет estimator: исключает собственный reward из baseline и
убирает нормировку reward стандартным отклонением. Reparam служит контролем
прямого градиента той же сглаженной функции.

**Вывод для дизайна:** сравнивать pure CE/Brier и воспроизведение конкретного
RLCD-рецепта в отдельных таблицах. Иначе одновременно меняются функция,
шум и estimator, и причина различий остаётся неустановленной.

### OpenJev: две стадии и открытая последовательность рассуждения

Проверен [`openjev_rlcd/train.py`, commit `22db40ad3333f5cf0bc5139097da70e0f8c05018`](https://raw.githubusercontent.com/ZimmyGao/openjev-rlcd/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/train.py).
Генерация останавливается перед answer-option readout: rationale сэмплируется,
распределение по допустимым answer tokens считывается. Stage 1 использует
дифференцируемый readout loss на собственных rationale; это **не замороженный
backbone с обучением одной головы**. Stage 2 добавляет score-function term
для rationale и KL-якорь. Single-query evaluation включает одно рассуждение.

**Математическая интерпретация для нашего дизайна:** если $r\sim\pi_\theta$
и reward зависит от $p_\theta(\cdot\mid x,r)$, градиент содержит
и $\nabla_\theta R$, и $R\nabla_\theta\log\pi_\theta(r\mid x)$.
Без сэмплируемого rationale и без иного случайного действия Brier reward
можно оптимизировать напрямую. Называть такой direct loss «RLCD» не создаёт
нового алгоритма. Подробные коэффициенты и caveats — в [разборе](rlcd-review.md).

## 4. Опубликованные результаты, которые мотивируют сравнение

Эти таблицы предназначены для обзора литературы. Между таблицами отличаются
данные, backbone, интерфейс, бюджет и единицы метрик; их нельзя склеивать
в общий рейтинг моделей и приписывать ожидаемое качество banking.

### SBERT2S1: сравнение objectives при одном backbone

Pritam Deka, arXiv:2610.02486v1, **01.10.2026**, препринт. Один
S-PubMedBERT-MS-MARCO; две головы C/PFR; три seeds. Ниже
**chance-normalized accuracy ×100**, seen tasks, среднее ± SD.
[Таблица 4 и appendix E](https://arxiv.org/html/2610.02486v1#S6).

| Objective | PFR | C |
| --- | ---: | ---: |
| CE | 68.3 ± 0.4 | 70.2 ± 0.4 |
| Direct proper score | 68.5 ± 0.2 | 70.7 ± 0.3 |
| Released PG | 65.3 ± 1.5 | 67.7 ± 0.9 |
| PG-LOO | 67.8 ± 0.6 | 69.2 ± 0.6 |
| Reparam | 68.5 ± 0.5 | 69.8 ± 1.6 |

Released PG уступает CE; после temperature scaling ясного преимущества RL
по калибровке нет. Это ограниченное сравнение, не универсальный запрет RL.
Порядок на held-out задачах отличается. Авторы обнаружили пересечения exact
training inputs с evaluation и проверили sensitivity removal; это не чистое
повторное обучение. [Статья, §§6–8 и appendix I](https://arxiv.org/html/2610.02486v1).

Опубликованный S1-PubMedBERT — **CE-вариант**; лицензия весов **CC BY-NC 2.0**.
Его нельзя автоматически включать в набор unrestricted checkpoint.
[Model card](https://huggingface.co/pritamdeka/S1-PubMedBERT).

### OpenJev: reasoning и калиброванный readout

Gao, Wang, arXiv:2609.38850v1, **30.09.2026**, препринт. Qwen3-1.7B;
средние трёх seeds после temperature scaling. Ниже accuracy в процентах,
Brier — multiclass sum; **это не τ-bench**.
[Таблица 1](https://arxiv.org/html/2609.38850v1#S5.SS1).

| Метод | GSM8K-Verify: accuracy / Brier | MMLU-Pro: accuracy / Brier |
| --- | ---: | ---: |
| SFT, direct answer | 70.4 / 0.382 | 42.3 / 0.711 |
| GRPO + KL | 91.8 / 0.150 | 42.4 / 0.753 |
| Stage 1, Brier | 90.4 / 0.164 | 47.0 / 0.667 |
| Stage 1, log score | 91.3 / 0.149 | 46.5 / 0.668 |
| Две стадии RLCD | 92.2 / 0.135 | 47.7 / 0.658 |

На GSM8K отличие accuracy двухстадийного RLCD от GRPO незначимо;
разница Brier имеет $p=0.09$. GSM8K-Verify проверяет предложенный ответ,
а MMLU-Pro использует собственное разбиение, поэтому это не числа стандартного
leaderboard. Сравнение SFT и RLCD одновременно меняет reasoning и training
recipe; причинный эффект одного loss из него не следует.
[Условия и ограничения статьи](https://arxiv.org/html/2609.38850v1#S4).

**Отдельная проверка headline coverage:**
[`metrics.py`](https://raw.githubusercontent.com/ZimmyGao/openjev-rlcd/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/metrics.py)
различает `cov@e`, фактический `risk@e` и `oracle_cov@e`.
[`final_tables.py`](https://raw.githubusercontent.com/ZimmyGao/openjev-rlcd/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/final_tables.py)
выводит oracle-метрику. Поэтому часто цитируемые **81.1% против 19.4%**
при 5% error описывают допустимый префикс **размеченного test**, а не
гарантированный охват будущего deployment с заранее выбранным threshold.

### Laya: сигнал пользы доменной адаптации

Карточка автора сообщает accuracy **0.362 → 0.766** для base English и
`laya-typed-decisions` на 2000 решениях четырёх workflow.
Это мотивирует проверку адаптации, но не предсказывает величину нашего эффекта,
не изолирует loss и не оценивает полный интерактивный агент.
[Первичная model card, Fine-tune for better accuracy](https://huggingface.co/convaiinnovations/laya#fine-tune-for-better-accuracy).

## 5. DeepSeek V4.1 Flash подтверждён, alias меняется

Название из запроса пользователя корректно. Официальный релиз
**DeepSeek-V4.1-Flash — 10.09.2026**.
[Сообщение DeepSeek](https://deepseek.com/en/news/deepseek-v4-1-flash/).
**17.10.2026** выпущен **V4.1-Flash-1017**;
[`deepseek-flash` обслуживается этой версией](https://api-docs.deepseek.com/news/news261017/).
Это пример сильного LLM baseline, а не утверждённая экспериментальная победа.

Проверка [официальной API-страницы](https://api-docs.deepseek.com/quick_start/pricing/)
на 19.10.2026:

| Поле | Значение среза |
| --- | --- |
| API model | `deepseek-flash` |
| Версия | DeepSeek-V4.1-Flash-1017 |
| Интерфейс | OpenAI-compatible; JSON, tools; thinking / non-thinking |
| Контекст | 1M |
| Цена USD / 1M input cache miss | 0.15 off-peak; 0.30 peak |
| Цена USD / 1M input cache hit | 0.003 off-peak; 0.006 peak |
| Цена USD / 1M output | 0.60 off-peak; 1.20 peak |

Это тариф прямого провайдера, не OpenRouter, не рублёвый бюджет и не стоимость
нашей задачи. Старые aliases `deepseek-v4-flash` и `deepseek-v4-flash-vision-exp`
переадресуются на текущий Flash. Перед серией заново фиксируются provider,
model/version, тариф, дата, route и режим кеша; один alias не гарантирует
воспроизводимость весов. Не смешивать результаты до/после смены backend.

По [Thinking Mode guide](https://api-docs.deepseek.com/guides/thinking_mode/):
по умолчанию thinking включён, effort `high`; `temperature` в этом режиме
игнорируется. Для Flash `top_p` в thinking ограничен 0.95–1.0, в non-thinking
фиксирован 1.0. При использовании tools в следующие запросы передаётся
`reasoning_content` предыдущих turns. Поэтому адаптер должен учитывать
его в истории, длине и usage, а «temperature=0» нельзя выдавать за
детерминированный reasoning-run. Локальная доступность API не проверялась
платным вызовом; совместимость нашего τ-адаптера ещё предстоит подтвердить.

## 6. Как честно проверить рассуждение и тип обучения

**Предложение исследовательского дизайна, не результат литературы:**

1. Основной практический эффект: LLM-agent против того же harness с готовым
   System One scorer против того же scorer после banking-адаптации.
   Это сравнение систем, поэтому одинаковые наружные tools, policy и evaluator
   обязательны; генерирующий LLM сохраняет свою роль там, где scorer не умеет
   формировать ответ или свободный аргумент.
2. Основной причинный опыт: один выбранный System One checkpoint, direct
   inference, CE против pure Brier, одинаковый train/calc/test контракт.
3. Reasoning/no-reasoning: отдельный малый decoder с одним и тем же backbone,
   typed answer readout и явным переключением rationale. Матрица
   `{direct, rationale} × {CE, Brier}`. Политика генерации rationale, длина,
   механизм readout и источники labels фиксируются. Архитектурное сравнение
   Laya против OpenJev не заменяет эту матрицу.
4. RLCD-ветка: после matched CE/Brier — сравнить readout-only continuation,
   readout + REINFORCE и при достаточном бюджете GRPO из одного warm checkpoint.
   Это проверяет дополнительный вклад RL, а не только дополнительные шаги.
5. Distillation-ветка: reasoning teacher → проверенные final targets → direct
   student. Отдельный контроль teacher без reasoning на тех же train rows.
   Дистилляция System 2 в direct outputs мотивирована
   [Yu et al., arXiv:2407.06023v3, 24.07.2024](https://arxiv.org/abs/2407.06023v3),
   но перенос на banking — новая проверяемая гипотеза.

Под «matched» здесь понимаются фиксированные объекты сравнения и одинаковая
возможность dev tuning; равные optimizer steps не означают равное число
tokens/FLOPs при rationale. Нужно публиковать обе оси бюджета: exposure
training examples и фактические вычисления/время. В teacher targets не
попадают test task solutions, скрытые пользовательские инструкции или
будущие наблюдения. Отсутствие rationale на inference не доказывает
отсутствие внутренних вычислений модели.

## 7. Что остаётся неизвестным

- Перенесётся ли адаптация на удержанные семейства задач `banking_knowledge`,
  а не только на новые шаги знакомых траекторий.
- Сохраняется ли полезность после одинаковой post-hoc calibration и fallback.
- Выигрывает ли pure Brier, CE + Brier или RLCD у корректно настроенного CE.
- Достаточны ли имеющиеся проверяемые labels для различения методов.
- Окупает ли сокращение LLM context локальную обработку, обучение и разметку.
- Помещается ли конкретная training-конфигурация в доступную память и бюджет.

Ответы требуют будущих запусков; цифры литературного обзора их не заменяют.
Версии источников выше прочитаны по первичным web-страницам и коду.
Commit-ссылки указывают проверенные снимки, но не заявляются последними HEAD.
API GitHub для повторного чтения дат commit через web был недоступен;
несверенные даты commit здесь не добавлены. Независимого человеческого review
этого среза пока нет.
