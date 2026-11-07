---
node_type: reference
title: "RLCD для System One: обзор и программа исследования"
service: _platform
status: draft
updated: 2026-10-11
links:
  relates_to: [docs/gitmark/research.md, docs/gitmark/sources.md]
---

# RLCD для System One: обзор и программа исследования

Статус: исследовательский обзор и предложения, **не утверждённая тема ВКР**.
Контекст проекта — [постановка исследования](research.md), реестр работ —
[научные источники](sources.md). Проверка первичных источников: **11.10.2026**.
Ни обучение, ни платные вызовы не выполнялись; результаты ниже принадлежат авторам,
а проверка реализации — статическое чтение закреплённого кода, не воспроизведение обучения.
Пять предлагаемых тем и подробная программа — в [плане ВКР](rlcd-study-plan.md).

## Короткий вывод

**Факт источника.** OpenJev-RLCD обучает reasoning-модель: сначала она генерирует
обоснование (*rationale*), затем выдаёт распределение по фиксированным вариантам ответа.
Вознаграждается не только правильность выбранной метки, а всё распределение с помощью
строго правильного правила оценивания (*strictly proper scoring rule*). Рецепт —
**сначала обучить распределение после обоснования, затем усилить полезные обоснования
через REINFORCE**. Это независимая реализация идеи, а не раскрытие закрытого Jev.
[Статья, §§2–3][method]; [оговорка авторов репозитория][repo].

**Наша интерпретация.** Для System One интересен принцип «обучать честную вероятность
решения», но эта работа **не демонстрирует быстрый одношаговый System One**: *single query*
означает одно сгенерированное обоснование, а не один forward pass. Главное число
«81% решений при ошибке ≤5%» — ретроспективный **oracle coverage на тесте**, а не
доказанная доля безопасной автоматизации с заранее установленным порогом.
[Считывание single][readout-code]; [определения coverage][metrics-code];
[вывод таблицы][tables-code].

## Источник, версии и изменение abstract

| Объект | Что установлено при проверке |
| --- | --- |
| Авторы и название | Zhimin Gao, Pichao Wang. *OpenJev-RLCD: A Working RLCD Implementation*. [Карточка arXiv][abs-v1]. |
| arXiv v1 | **30 сентября 2026, 03:08:45 UTC**, размер в истории 55 KB. Единственная версия, указанная в полученной истории подачи. [Versioned abs][abs-v1]. |
| arXiv v2 | **Не подтверждена**: запросы [abs v2][abs-v2] и [HTML v2][html-v2] вернули HTTP 404. Даты v2 нет; придумывать её нельзя. |
| Актуальная версия без суффикса | [Текущий abs][abs-current] указывает v1; текст abstract после удаления HTML совпал с [abs v1][abs-v1]. |
| Закреплённая реализация | Commit **`22db40ad3333f5cf0bc5139097da70e0f8c05018`**, автор/committer date **2026-10-01T13:54:21Z**, сообщение `Add arXiv link and citation`. [Commit][commit]; [GitHub API][commit-api]. |
| Научный статус | Подтверждён препринт arXiv; подтверждения рецензирования/публикации в venue в проверенных источниках нет. [Карточка][abs-v1]. |

**Что действительно отличается.** Метаданные [abs v1][abs-v1] содержат сокращённый
abstract со сломанными TeX-макросами `\gvTwoCovFive` и `\gvGrpoCovFive` вместо чисел.
В [abstract полного HTML v1][paper] они раскрыты как **81% и 19%**; там же подробнее
описаны пустые обоснования, целевая калибровка и обещание API-compatible server.
Таким образом, обнаружено различие **abstract карточки и abstract полного текста одной
версии**, но не подтверждён переход v1→v2 или существенная позднейшая смена выводов.
Сравнение нынешних endpoint не заменяет архивный снимок дня подачи: историческую
неизменность метаданных оно не доказывает. [Текущий abs][abs-current];
[versioned abs][abs-v1]; [HTML v1][paper].

Все формулы и результаты ниже относятся именно к доступной **v1**. Репозиторий
прямо отказывается от утверждений о внутреннем алгоритме Jev. Обещание сервера
в abstract отдельно не верифицировано: в проверенном дереве commit нет выделенной
реализации API-сервера. [README][repo]; [дерево commit][tree]; [abstract][paper].

## Что именно предсказывает модель

Пусть $x$ — вопрос с $K$ вариантами, $Y\sim q(\cdot\mid x)$ — наблюдаемый исход,
$r\sim\pi_\theta(\cdot\mid x)$ — сгенерированное обоснование. После маркера
`Answer:` берутся логиты **только токенов допустимых ответов** и нормируются:

$$
u_\theta(x,r)=\operatorname{softmax}(z_\theta(x,r)[\text{option tokens}]),
\qquad p_\theta(x)=\mathbb E_r u_\theta(x,r).
$$

$u$ — распределение одного запроса, $p$ — математическое ожидание по обоснованиям;
среднее нескольких $u$ — отдельный *mixture readout*. В основной таблице *single* —
первое из четырёх сэмплированных при оценке обоснований, не голосование и не лучший
из четырёх ответов. [Статья, §2][setting]; [код, строки 134–163][readout-code].

**Граница задачи.** Это конечный набор меток, а не произвольные JSON-объекты,
калиброванные непрерывные величины или исполнение tool calls. В GSM8K-Verify
модель получает задачу и предложенный численный ответ, а возвращает `yes/no`;
золотой ответ в формируемый prompt не включён. Если генерация не завершилась
маркером, код принудительно дописывает `Answer:` перед считыванием распределения: это
исправление формата, не доказательство корректного рассуждения.
[Построение prompt][gsm-code]; [генерация и readout][generation-code].

## Вознаграждение и градиент

### Правильность метки и честность распределения — разные цели

Использован сдвинутый отрицательный multiclass Brier score:

$$
R(u,Y)=2u_Y-\lVert u\rVert_2^2=1-\lVert u-e_Y\rVert_2^2.
$$

В ожидании по исходу:

$$
J(u,q)=2u^\top q-\lVert u\rVert_2^2
      =\lVert q\rVert_2^2-\lVert u-q\rVert_2^2.
$$

Поэтому максимум по свободному распределению единственен: $u=q$. Другой
исследованный proper score — $\log u_Y$, то есть отрицательный cross-entropy
loss. Это **не** отличие «RL использует вероятности, а CE не умеет»: CE также
является strictly proper loss; существенно, где и на каких обоснованиях он
применяется. [Статья, §§2, 5.4][setting]; [log-score ветвь кода][loss-code].

Для сравнения, вознаграждение RLVR $1[A=Y]$, где $A\sim p$, имеет ожидание
$p^\top q$ и поощряет сосредоточение на наиболее вероятной метке, а не
воспроизведение всего $q$. При детерминированной правильной метке обе цели
имеют правильный one-hot оптимум; утверждение об обязательной некалиброванности
**любого** конечного RLVR-решения из этого не следует. Последняя оговорка — наш
вывод из формулы, а наблюдаемая переуверенность в опытах — результат авторов.
[Статья, corollary 1 и §5.1][theory].

### Почему авторы не вознаграждают смесь обоснований

Для $p=\mathbb E_r u(r)$ справедливо тождество:

$$
J(p,q)=\mathbb E_rJ(u(r),q)+\mathbb E_r\lVert u(r)-p\rVert_2^2.
$$

**Вывод авторов.** Оценивание смеси добавляет бонус за различающиеся ответы
обоснований; математически бонус не требует содержательной обоснованности
расхождения. При one-hot ответах $u=e_A$ получаем
$\mathbb E_AJ(e_A,q)=2\Pr(A=Y)-1$, а бонус равен $1-\lVert p\rVert^2$:
«RLVR + Gini diversity» совпадает с Brier-целью смеси при коэффициенте бонуса 1.
Это тождество о целях, не тождество всех практических оптимизаторов RLVR.
[Статья, proposition 1 и corollary 1][theory].

Для семейства $J_\lambda=\mathbb E_rJ(u(r),q)+\lambda\operatorname{Var}_r(u)$
можно записать дефицит относительно $\lVert q\rVert^2$ как
$\lVert p-q\rVert^2+(1-\lambda)\operatorname{Var}_r(u)$. Поэтому при
$\lambda<1$ оптимум свободных readouts — $u(x,r)=q(x)$ для всех обоснований
с ненулевой вероятностью; при $\lambda=1$ достаточно $p=q$. Авторы выбирают
$\lambda=0$, per-rationale score. Условие: $Y\perp r\mid x$, то есть собственное
обоснование не меняет исход мира. Наше алгебраическое пояснение основано на
[proposition 2][theory].

**Границы вывода.** Это optimum неограниченного семейства распределений, а не
гарантия сходимости нейросети, калибровки на новых данных или отсутствия вреда
от KL-регуляризации. В агенте, где выбор действия меняет будущий исход,
$Y\perp r\mid x$ требуется обосновать заново. Это наша интерпретация условий
[proposition 2][theory], не эксперимент OpenJev на интерактивном агенте.

### Две составляющие градиента

Для $M\ge2$ независимых обоснований одного вопроса, общего исхода $Y$,
$R_i=J(u_\theta(x,r_i),Y)$ и leave-one-out baseline
$b_i=(M-1)^{-1}\sum_{j\ne i}R_j$:

$$
\widehat{\nabla_\theta J}=
\frac1M\sum_i\nabla_\theta R_i+
\frac1M\sum_i\operatorname{sg}(R_i-b_i)\nabla_\theta\log\pi_\theta(r_i\mid x).
$$

Первое слагаемое — дифференцирование proper score через readout при фиксированных
сэмплированных токенах; второе — REINFORCE, изменяющий вероятность обоснования.
`sg`/`detach` останавливает градиент через вознаграждение и baseline внутри
score-function слагаемого. В идеальном on-policy случае полная оценка несмещённая;
baseline использует другие независимые обоснования.
[Статья, §3.1 и appendix A][estimators-paper]; [реализация][estimators-code].

Для проверки руками, при $u=\operatorname{softmax}z$,
$\nabla_zR=2(\operatorname{Diag}(u)-uu^\top)(e_Y-u)$; для log score
$\nabla_z\log u_Y=e_Y-u$. Это наш вывод дифференцированием reward из
[§2][setting], а не отдельная заявленная авторами теорема.

## Две стадии: что обновляется на самом деле

1. **Stage 1 — calibrate.** Сэмплировать собственные актуальные обоснования,
   минимизировать $\mathcal L_1=-M^{-1}\sum_iR_i$, отключить score-function term.
   **Не замораживается backbone и не обучается только отдельная head:** AdamW
   получает `model.parameters()`, градиент readout проходит через всю модель;
   нет градиента через дискретный выбор токенов. При изменении общих весов
   меняется и последующая генерация обоснований.
   [Алгоритм 1][recipe]; [optimizer и цикл][training-code].
2. **Stage 2 — reinforce.** Начать с checkpoint $\theta_1$, продолжить pathwise
   обучение и добавить REINFORCE с proper-score reward, leave-one-out baseline
   и KL-якорем к $\theta_1$. В коде свежий optimizer, checkpoint загружается
   также в frozen reference. [Алгоритм 1][recipe]; [инициализация][training-code];
   [двухстадийный скрипт][two-stage].

Точная удобная запись второй стадии, согласованная с кодом:

$$
\ell_i=\log\frac{\pi_\theta(r_i\mid x)}{\pi_{\theta_1}(r_i\mid x)},
\quad h_i=\frac{R_i-\beta\ell_i}{M},
\quad A_i=h_i-\frac{1}{M-1}\sum_{j\ne i}h_j,
$$

$$
\mathcal L_2=-\frac1M\sum_iR_i
-c\sum_i\operatorname{sg}(A_i)\log\pi_\theta(r_i\mid x),
\qquad c=0.3,\quad\beta=0.04.
$$

KL здесь направлен как $D_{KL}(\pi_\theta\Vert\pi_{\theta_1})$ по
распределению **обоснований**, а не как KL выходных меток. Коэффициент $c$
масштабирует весь score-function term, включая KL shaping. При $c=0.3$ это
**не несмещённая оценка полного исходного градиента** из предыдущего раздела;
это намеренно изменённое правило обновления для уменьшения влияния шумной части.
[Код KL и `sf_coef`][training-code]; [surrogate][estimators-code].

**Важная деталь проверки.** В скрипте stage 1 тоже передан `--kl-beta 0.04`,
но `--no-score-function` отсоединяет `logp_r`, а KL входит только через
этот term. Поэтому **активного KL-штрафа на стадии 1 нет**, несмотря на
вычисление reference log-probabilities. Нельзя описывать рецепт как «обе
стадии обучаются с KL». [Скрипт, строка 18][two-stage];
[цикл, строки 304–314][training-code]; [surrogate][estimators-code].

**Мотивация авторов.** При совместном обучении с нуля без KL наблюдалось
исчезновение обоснований примерно за 100 шагов («System-One collapse»);
с KL шум score-function term мешал pathwise обучению. Сообщается отношение
норм градиентов 7–12×; реализованная диагностика берёт первый item и три
MLP-матрицы, поэтому это не измерение полной нормы всех параметров.
[Статья, §3.2][failure-modes]; [диагностика, строки 346–357][loss-code].

## Результаты авторов и границы сравнения

Условия: Qwen3-1.7B, non-thinking chat template **с явно запрошенным reasoning**;
8 вопросов × 4 обоснования, AdamW $2\cdot10^{-6}$, по 400 шагов на стадию;
seeds 17/23/29, продолжения используют 1017/1023/1029. Для всех методов
температура подбирается по dev NLL, включая RLCD; «калибрована обучением»
не означает, что основной результат получен без temperature scaling.
[§4 и appendix B][setup]; [общие параметры][common]; [TS-код][metrics-code].

Данные и измерения:

- **GSM8K-Verify:** бинарная проверка предложений Qwen3-0.6B; train/dev из
  GSM8K-train, 4000/300 используются; test — 1260 GSM8K-test задач, для которых
  предложение удалось распарсить. Это не самостоятельное решение полного
  GSM8K и не оценка интерактивного агента. [§4][setup]; [loader][gsm-code].
- **MMLU-Pro:** случайное разбиение benchmark на 4000/500/1500; фактическая
  оценка на первых 300 dev и 1000 test. Loader берёт официальный **test**
  и заново делит его, поэтому числа не сопоставимы напрямую с leaderboard
  полного untouched MMLU-Pro. Это не найденная утечка между авторскими
  train/test, а иной протокол. [§4][setup]; [loader, строки 25–40][mmlu-code].
- **ChaosNLI:** 1000/199/400, распределение 100 аннотаторов; при посещении
  train-item выбирается одна метка. [Loader][chaos-code]; [§5.3][aleatoric].

Ниже — **опубликованные авторами средние трёх seeds**, single readout после TS,
не наши измерения. Accuracy и coverage — в процентах; Brier/AURC меньше — лучше.
Источник всех строк: [таблица 1 статьи][results].

| Метод | GSM8K: Acc / Brier / AURC / oracle Cov@5% | MMLU-Pro: Acc / Brier / AURC / oracle Cov@20% |
| --- | --- | --- |
| SFT + TS, прямой ответ | 70.4 / 0.382 / 0.174 / 6.2 | 42.3 / 0.711 / 0.386 / 15.6 |
| RFT/STaR + KL + TS | 91.4 / 0.160 / 0.075 / 11.6 | 40.9 / 0.761 / 0.493 / 0.0 |
| GRPO + KL + TS | 91.8 / 0.150 / 0.061 / 19.4 | 42.4 / 0.753 / 0.481 / 0.0 |
| RLCD stage 1, Brier | 90.4 / 0.164 / 0.047 / 62.6 | 47.0 / 0.667 / 0.312 / 27.3 |
| RLCD stage 1, log score | 91.3 / 0.149 / 0.038 / 72.2 | 46.5 / 0.668 / 0.319 / 24.8 |
| RLCD две стадии | **92.2 / 0.135 / 0.034 / 81.1** | **47.7 / 0.658 / 0.304 / 27.6** |

**Не преувеличивать превосходство.** На GSM8K разница accuracy RLCD–GRPO
не значима; Brier −0.015 имеет $p=0.09$; преимущество AURC имеет парный bootstrap
$p<10^{-3}$. Для двухстадийного GSM8K опубликованы accuracy $92.2\pm0.7$ и
coverage $81.1\pm7.2$; у GRPO coverage $19.4\pm7.3$ — здесь ± обозначает
разброс по seeds, не доверительный интервал гарантированного риска.
[§5.1 и таблица 1][results].

**Вклад RL отдельно.** В forked-checkpoint контролях stage 2 сравнивается
с теми же дополнительными 400 шагами readout-only, anchor-only и GRPO.
На GSM8K RLCD-RL превосходит продолжение readout-only на 3.5 п.п. accuracy
и 0.057 Brier; на MMLU-Pro отличие от readout-only по Brier +0.002
незначимо и меняет знак между seeds. На GSM8K GRPO из уже калиброванного
checkpoint помогает сопоставимо с RLCD-RL; на MMLU портит калибровку.
Поэтому тезис «вторая стадия всегда необходима и всегда лучше GRPO»
не поддерживается самими опытами. [§5.2 и таблица 2][stage2-results].

### Главное ограничение headline: oracle coverage

В статье $\operatorname{Cov}@\varepsilon$ определяется как наибольший
префикс тестовых объектов, отсортированных по уверенности, с **наблюдаемой**
ошибкой не выше $\varepsilon$. В коде различие сделано явно:

- `cov@e`: выбор префикса по средней **предсказанной** ошибке $1-\max u$;
- `risk@e`: реальная ошибка этого выбранного префикса;
- `oracle_cov@e`: наибольший префикс с допустимой **реальной** ошибкой.

Генератор итоговой таблицы выводит именно `oracle_cov@0.05`, а не `cov@0.05`.
Значит **81% vs 19% характеризует ранжирование на размеченном тесте**.
Это не даёт права обещать «автоматически делегируем 81% будущих решений
с гарантированной ошибкой ≤5%». Такая гарантия требует отдельного протокола
выбора порога и оценки риска, которого headline не предоставляет.
[Определение в статье][setup]; [код метрик, строки 24–54][metrics-code];
[вывод, строки 90–93][tables-code].

## Проверка ключевого кода на закреплённом commit

Все ссылки в этой таблице закреплены на **`22db40ad3333f5cf0bc5139097da70e0f8c05018`**,
а не на изменяемом `main`. Проверено чтением, тесты и обучение здесь не запускались.

| Проверяемая часть | Наблюдение по коду |
| --- | --- |
| Reward и `detach` | `single_surrogate`: `r = 2*u[:, y] - (u*u).sum(1)`, `local = r.detach()/m`, LOO baseline; pathwise часть сохраняется как `r.mean()`. [Строки 59–76][estimators-code]. |
| Mixture estimator | `rb_surrogate` использует независимые попарные произведения без диагонали, а не квадрат эмпирического среднего с конечновыборочным смещением; требует M≥3. [Строки 24–56][estimators-code]. |
| Stage 1/2 | Полная модель обновляется в обеих стадиях; `logp_r.detach()` отключает score function; checkpoint и KL reference согласованы; `c=.3` задаётся отдельно. [Цикл][training-code]; [скрипт][two-stage]. |
| GRPO baseline | Реализованы group-normalized бинарные rewards и REINFORCE по rationale+answer. В этой ветке **нет PPO importance ratio, clipping или нескольких PPO epochs**; корректнее говорить о конкретном baseline авторов, а не обо всех GRPO-реализациях. [Строки 331–337][loss-code]. |
| Single-query | Оценка генерирует M обоснований для сравнения readouts, но `single` берёт строго `u[0]`. Стоимость всего evaluation-run не равна стоимости одного production-запроса. [Строки 134–163][readout-code]. |
| TS и статистика | T выбирается на dev по NLL; парные тесты используют совпадающие test-items, сначала усредняя per-item значения по seeds. AURC — отдельный bootstrap по items. [Метрики][metrics-code]; [evaluation][evaluation-code]. |
| Проверки несмещённости | Есть точное перечисление маленьких табличных моделей, KL/cost shaping и λ∈{0,0.5,1}; assertions требуют ошибку <10⁻¹². Это не тест сходимости LLM и не проверка преимущества c=.3. [Тесты][tests-code]. |
| Версии модели/данных | `from_pretrained`/`load_dataset` вызываются без pinned `revision`; commit кода сам по себе не фиксирует все внешние артефакты. Для повторения нужны отдельно revisions весов/токенизатора/данных. [Загрузка модели][training-code]; [MMLU loader][mmlu-code]. |
| Токены вариантов | Берётся первый токен каждой метки, проверяется уникальность, но в основном `Rationales` нет проверки, что кодировка метки состоит ровно из одного токена. Для иной модели/набора меток предположение нужно проверять. [Строки 48–54][generation-code]. |

Для ориентира по реальному объёму reasoning: опубликованный run GSM8K stage 2
с seed 1017 хранит среднюю длину **174.44 токена**, долю достижения лимита
**0.2593**, лимит 320 и M=4. Это один авторский run, а не наша усреднённая
оценка latency; он ещё раз показывает, почему *single query* нельзя переводить
как «без авторегрессионной генерации». [Опубликованный JSON][run-example].

## Что следует из теории для прямого System One

**Утверждение авторов.** Если обоснований нет и модель явно выдаёт распределение,
RLCD с данным reward в ожидании сводится к обычному Brier-обучению. На
ChaosNLI direct CE имеет JSD 0.074 против 0.075 у per-rationale без KL,
который выключил reasoning; смесь 16 обоснований имеет JSD 0.121,
одиночное обоснование той же mixture-модели — 0.342. Некоторые контрольные
варианты ChaosNLI имеют только **один**, а не три seeds.
[§5.3, таблица 3, §5.4][aleatoric].

**Наша интерпретация границ.** Формулировку abstract «RLCD provably cannot beat
cross-entropy» следует читать узко: при известной постановке с неизменяемым
$q$, одинаковой информацией и неограниченным optimum proper losses нет
лучшего распределения, чем $q$. **Градиент Brier не равен градиенту CE**,
а равный Bayes-optimum не доказывает равенство finite-sample обобщения,
оптимизации и устойчивости при misspecification. Аннотаторское разногласие
неустранимо как случайность отдельной метки, но это не означает, что
никакое рассуждение не может помочь конечной модели лучше оценить само $q$.
Основание — условия [proposition 2][theory], формулы [§2][setting]
и эмпирическая, а не универсальная проверка [§5.3][aleatoric].

Таким образом, для **прямого** типизированного scorer нельзя обосновать научную
новизну одним названием «RLCD» поверх Brier loss. А для reasoning-модели
отдельный вопрос — помогает ли оптимизация вероятностей обоснований сверх
proper-score обучения на собственных обоснованиях. OpenJev даёт содержательный
контроль этого различия, но его положительный результат ограничен выбранными
задачами. Это наш вывод из [градиента][estimators-paper] и [forked controls][stage2-results],
не готовое решение для узлов нашего агента.

## Ограничения и нерешённые вопросы источника

1. **Область эмпирики:** одна модель 1.7B, короткое обучение 400–800 шагов,
   две основные задачи, небольшое число seeds; перенос на другие размеры,
   бюджеты, домены, dataset shift и интерактивные tools не показан. Авторы
   прямо не знают, как предсказать пользу stage 2 без её запуска.
   [Limitations, §7][limitations].
2. **Разные вычислительные режимы:** direct SFT не генерирует rationale,
   RLCD и reasoning baselines генерируют; основной RLCD имеет 800 шагов
   против 400 у GRPO/RFT. Авторы проверили SFT-800 и forked controls,
   но это не единый quality–cost–latency Pareto-анализ.
   [§4][setup]; [§5.2][stage2-results].
3. **Ранжирование, калибровка, безопасность — не синонимы:** меньший AURC и
   более высокая oracle coverage не устанавливают корректность каждого
   уверенного решения или гарантию риска в эксплуатации.
   [Определения метрик][metrics-code].
4. **Отрицательные результаты существенны:** смесь стимулирует разнообразие
   без содержательности, без KL stage 2 может портить формат reasoning,
   а RL не оказался полезнее CE на данном aleatoric стенде.
   [§§5.3–5.4][aleatoric]; [абляции][ablations].
5. **Воспроизводимость неполная:** код и per-item результаты опубликованы,
   но pinned revisions внешних моделей/датасетов не заданы, веса checkpoint
   не входят в проверенное дерево, часть заявленного в abstract API-релиза
   в нём не обнаружена. Следовательно, «прочитан код» и «воспроизведены
   показатели» здесь строго различаются. [Дерево][tree]; [загрузка][training-code];
   [описание релиза][repo].

## Три разных подхода под похожим названием

RLCD здесь — **Reinforcement Learning for Calibrated Decisions**, не
[Reinforcement Learning from Contrastive Distillation](https://arxiv.org/abs/2307.12950)
(Yang et al., 2023/ICLR 2024): последняя работа создаёт preference pairs для alignment.

| Подход | Что опубликовано | Что нельзя заключать |
| --- | --- | --- |
| [TypeSafe Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) | Интерфейс typed decisions и название RLCD | Внутренний рецепт закрыт; OpenJev не его точная реплика |
| [Laya / SBERT2S1](https://arxiv.org/html/2610.02486v1) | Encoder/head, Gaussian noise в логитах, proper-score reward и policy gradient | Это не REINFORCE по рассуждениям и не RL полных агентных траекторий |
| [OpenJev-RLCD][paper] | Rationale-generation, readout после Answer, двухстадийный рецепт | Single query не равен одному forward pass |

**Калибровка простыми словами:** среди прогнозов уверенности около 0.8 правильными
должны быть примерно 80%, в явно выбранном смысле события и группирования.
Это не обещание правильности каждого отдельного ответа. Модель, всем выдающая
базовую частоту, может быть калибрована, но плохо разделять лёгкие и трудные случаи.
Поэтому нужны одновременно accuracy, proper-score metrics и risk–coverage,
а не только ECE. Основание: [Guo et al., ICML 2017](https://proceedings.mlr.press/v70/guo17a.html)
и [селективная классификация](https://arxiv.org/abs/1705.08500v2).

## Самая полезная дополнительная работа: SBERT2S1

Pritam Deka, *From Retrieval to Typed Decisions: Calibrated System One Models
from Biomedical Sentence Encoders*, [arXiv:2610.02486v1](https://arxiv.org/abs/2610.02486v1),
**01.10.2026**. Подтверждён препринт; peer review не установлен. Изучает
конверсию biomedical encoders в typed decision models и отдельно сравнивает
обучающие цели. Это важный отрицательный контроль, **не опровержение OpenJev**.

Факторная серия objectives: **один backbone S-PubMedBERT-MS-MARCO**, две головы
C/PFR, пять objectives, три seeds, одинаковый schedule. Общая работа содержит
больше encoders, но нельзя приписывать весь objective-grid всем из них.
C — cross-head, PFR — residual cross-head поверх retrieval prior.
[Полный текст, §§3–6](https://arxiv.org/html/2610.02486v1).

| Objective | PFR: seen acc_cn ×100 | C: seen acc_cn ×100 |
| --- | --- | --- |
| CE | 68.3 ± 0.4 | 70.2 ± 0.4 |
| Direct proper score | 68.5 ± 0.2 | 70.7 ± 0.3 |
| Released Gaussian-logit PG | 65.3 ± 1.5 | 67.7 ± 0.9 |
| PG-LOO | 67.8 ± 0.6 | 69.2 ± 0.6 |
| Reparameterized proper score | 68.5 ± 0.5 | 69.8 ± 1.6 |

Это **авторские chance-normalized accuracy**, не raw accuracy и не наши измерения.
Released PG проигрывает CE на 3.0/2.5 пункта; после temperature scaling
нет ясного преимущества PG по ECE. Незначимость различий не доказывает эквивалентности.
Порядок методов на held-out задачах иной; не переносить вывод «CE лучше» на все
OOD-распределения. Источник: [§6.3 и appendix E](https://arxiv.org/html/2610.02486v1).

### Причина: estimator, а не магическое свойство RL

При G=4 зашумлённых логитах baseline со средним, содержащим собственный reward,
без дополнительной нормировки даёт множитель (G−1)/G=0.75 относительно целевого
градиента. Дополнительное деление на случайное стандартное отклонение rewards
по minibatch меняет масштаб шумного score-function term относительно CE.
При уменьшении шума авторы измеряют усиление масштаба примерно 3.6–15×.

PG-LOO **одновременно** исключает собственный sample из baseline **и удаляет
reward-std normalization**. Это несмещённая оценка градиента noise-smoothed
objective, не доказательство калибровки конечной нейросети. Поскольку reward
дифференцируем по логитам, прямой reparameterization-gradient является важным
дешёвым контролем. Источники: [§3.3, appendices C–D](https://arxiv.org/html/2610.02486v1),
[закреплённый objectives-код](https://github.com/pritamdeka/sbert2s1/blob/a3a0637264adfb35c6b1c6544cb6392d69fcedb0/research/s1/objectives.py).
Практический log-score там имеет нижний floor; строгую proper-score гарантию
не следует без оговорки переносить на clipped область.

### Ограничения SBERT2S1

- Fixed budget и унаследованные настройки, без отдельного широкого tuning каждого
  objective; ограниченная область head×objective сравнения.
- Авторы обнаружили небольшое число дубликатов между training и calibration/test;
  sensitivity removal не меняет ranking, но не заменяет полного clean retraining.
- MEDLINE-S1 использует weak NLM indexing labels; clinical track имеет отдельные
  условия доступа. Перенос на сервисные диалоги и Mac не показан.
- Routing самых неуверенных 20% теста к Gemma — **ретроспективный test budget**,
  а не заранее установленный deployment threshold.
- Код Apache-2.0, но опубликованные веса имеют **CC BY-NC 2.0**: не считать
  их unrestricted open-source checkpoint. Released model — CE-вариант, не RLCD.
- В отличие от OpenJev, полные per-item predictions в research release не
  опубликованы; часть данных credentialed. Код и агрегаты не равны полной raw replay.

Источники: [статья, §§4–8 и приложения](https://arxiv.org/html/2610.02486v1),
[research README](https://github.com/pritamdeka/sbert2s1/blob/a3a0637264adfb35c6b1c6544cb6392d69fcedb0/research/README.md),
[model card](https://huggingface.co/pritamdeka/S1-PubMedBERT).
Дополнительный, более слабый первичный сигнал — [Laya issue #741](https://github.com/NandhaKishorM/laya/issues/741):
односидовое CE/RLCD-сравнение, self-report, не рецензированная независимая реплика.

## Что ещё читать и зачем

Даты/версии проверены 11.10.2026; численные claims соседних работ не воспроизведены.

| Работа | Статус / проверенная версия | Роль |
| --- | --- | --- |
| [Gneiting, Raftery. Strictly Proper Scoring Rules, Prediction, and Estimation](https://doi.org/10.1198/016214506000001437) | JASA, 2007; библиография подтверждена [Crossref](https://api.crossref.org/works/10.1198/016214506000001437), полный текст в этом обзоре не прочитан | Теоретическая основа proper scoring, общий optimum CE/Brier |
| [Guo et al. On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html) | ICML 2017, PMLR 70:1321–1330 | Temperature scaling — обязательный дешёвый baseline |
| [Geifman, El-Yaniv. Selective Classification for Deep Neural Networks](https://arxiv.org/abs/1705.08500v2) | Проверен arXiv v2, 01.06.2017 | Risk–coverage и отказ от части решений; не изобретать эту постановку заново |
| [Angelopoulos et al. Conformal Risk Control](https://arxiv.org/html/2208.02814v4) | Проверен arXiv v4, 13.06.2025, первая версия 2022 | Контроль ожидаемой монотонной loss; exchangeability и границы гарантий |
| [Lin, Hilton, Evans. Teaching Models to Express Their Uncertainty in Words](https://arxiv.org/abs/2205.14334v2) | Проверен arXiv v2, 13.06.2022 | Вербализованная уверенность как альтернативный интерфейс; не тождественна typed logits |
| [Zelikman et al. STaR: Bootstrapping Reasoning With Reasoning](https://arxiv.org/abs/2203.14465v2) | Проверен arXiv v2, 20.05.2022 | Обучение на собственных успешных rationale, содержательный контроль для RL |
| [Yu et al. Distilling System 2 into System 1](https://arxiv.org/html/2407.06023v3) | Проверен arXiv v3, 24.07.2024 | Мост к direct student; не все сложные математические задачи удалось дистиллировать |
| [Hu et al. JevAdvBench](https://arxiv.org/html/2609.31142v1) | Препринт v1, 25.09.2026; peer review не подтверждён | Устойчивость typed решений к изменениям входа, не причинная проверка RLCD loss |
| [Liu. Evaluating System One Models for Agent Security Decisions](https://arxiv.org/html/2609.33401v3) | Препринт **v3**, 03.10.2026; peer review не подтверждён | Уже есть TS, fixed thresholds и independent confirmation; важная граница новизны |
| [Rahman et al. Beyond Aggregate Risk: Role-Stratified Conformal Risk Control for LLM Tool Calls](https://arxiv.org/abs/2607.24343v2) | Препринт v2, 31.07.2026; проверены metadata/abstract | Отдельный риск семантических полей; ориентир для дальнейшего полного чтения |

[JevAdvBench](https://arxiv.org/html/2609.31142v1) исследует 812 typed questions и
9744 single-edit вариантов одного Jev checkpoint. Добавленное мнение меняет
12.1% решений, но flip относительно исходного ответа **не равен ошибке**:
значительная часть labels основана на согласии самого Jev. Нельзя переносить
результат на все RLCD-модели или выдавать за абсолютную accuracy.

[Liu v3](https://arxiv.org/html/2609.33401v3) особенно важен для наших гипотез:
рост automation может достигаться главным образом дополнительными блокировками,
а не полезным допуском; fallback по неуверенности не ловит уверенные ошибки.
Работа оценивает offline security decisions, не полный сервисный агент с
измерением стоимости траектории. Именно эту границу следует использовать
при уточнении собственного вклада, не называя всю тему «неизученной».

## Темы, подробный план и перспектива кандидатской

Пять формулировок, гипотезы, математическая постановка, grouped splits,
контроли, этапы экспериментов, бюджетные ограничения, календарь на 24 недели,
главы ВКР и долгосрочная программа собраны в [плане исследования](rlcd-study-plan.md).

**Статус после уточнения инициатора 11.10.2026:** его согласованное направление —
[адаптация модели](research.md#согласованные-направления-трёх-исследований).
RLCD-vs-без-RL выбирается как возможное уточнение после общей схемы агента.

**Если выбрана RLCD-ветка, рекомендуемый фокус:** не «доказать превосходство RLCD», а установить, когда
RL-компонент даёт пользу сверх proper-score обучения и calibration, и остаётся
ли эта польза после fixed-threshold routing и полного агентного исполнения.
Дистилляция reasoning-RLCD в одношаговый student — отдельная гипотеза, а не
уже установленный результат OpenJev.

## Метод и ограничения этого обзора

Использованы первичные arXiv abs/HTML, репозитории и закреплённый код, model
cards и первичное описание TypeSafe. Встроенный web_search вернул HTTP 401;
поиск продолжен через прямые страницы arXiv/GitHub. Это не систематический
обзор всех citation networks и не доказательство отсутствия иных работ.
Некоторые большие HTML дочитаны прямым HTTP-доступом к тем же URL в памяти.
Журнальная страница Gneiting/Raftery была недоступна (403); указана только
проверенная библиография, формулы Brier отдельно разобраны по OpenJev.

Обзор подготовлен с помощью AI-агентов, основные замечания проверены по формулам
и исходному коду; независимого человеческого review пока нет. Обучение,
пересчёт авторских таблиц и собственные benchmarks не запускались.

## Первичные источники и закреплённые ссылки

Для научного цитирования использовать версию **arXiv:2609.38850v1**,
а для реализации — полный SHA из раздела версий. Все численные результаты
выше — авторские; формальные пояснения и caveats, помеченные «наши»,
получены чтением формул и кода, не новым обучением.

[abs-current]: https://arxiv.org/abs/2609.38850
[abs-v1]: https://arxiv.org/abs/2609.38850v1
[abs-v2]: https://arxiv.org/abs/2609.38850v2
[html-v2]: https://arxiv.org/html/2609.38850v2
[paper]: https://arxiv.org/html/2609.38850v1
[setting]: https://arxiv.org/html/2609.38850v1#S2
[method]: https://arxiv.org/html/2609.38850v1#S3
[theory]: https://arxiv.org/html/2609.38850v1#S3.SS1
[estimators-paper]: https://arxiv.org/html/2609.38850v1#A1
[recipe]: https://arxiv.org/html/2609.38850v1#S3.SS3
[failure-modes]: https://arxiv.org/html/2609.38850v1#S3.SS2
[setup]: https://arxiv.org/html/2609.38850v1#S4
[results]: https://arxiv.org/html/2609.38850v1#S5.SS1
[stage2-results]: https://arxiv.org/html/2609.38850v1#S5.SS2
[aleatoric]: https://arxiv.org/html/2609.38850v1#S5.SS3
[ablations]: https://arxiv.org/html/2609.38850v1#S5.SS4
[limitations]: https://arxiv.org/html/2609.38850v1#S7
[commit]: https://github.com/ZimmyGao/openjev-rlcd/commit/22db40ad3333f5cf0bc5139097da70e0f8c05018
[commit-api]: https://api.github.com/repos/ZimmyGao/openjev-rlcd/commits/22db40ad3333f5cf0bc5139097da70e0f8c05018
[tree]: https://github.com/ZimmyGao/openjev-rlcd/tree/22db40ad3333f5cf0bc5139097da70e0f8c05018
[repo]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/README.md
[estimators-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/estimators.py#L24-L86
[generation-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/train.py#L48-L126
[readout-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/train.py#L134-L163
[training-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/train.py#L232-L320
[loss-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/train.py#L319-L367
[two-stage]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/scripts/two_stage.sh#L4-L24
[common]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/scripts/common.sh#L4-L16
[metrics-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/metrics.py#L12-L54
[evaluation-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/evaluation.py#L46-L80
[tables-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/final_tables.py#L66-L109
[gsm-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/tasks/gsm8k_verify.py#L40-L90
[mmlu-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/tasks/mmlu_pro.py#L25-L40
[chaos-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/openjev_rlcd/tasks/chaosnli.py#L1-L18
[tests-code]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/tests/test_estimators.py#L15-L131
[run-example]: https://github.com/ZimmyGao/openjev-rlcd/blob/22db40ad3333f5cf0bc5139097da70e0f8c05018/results/gv_fork_rl_seed17.json
