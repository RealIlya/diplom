"""Narrative data for the research atlas; all flows describe proposed work."""

PAGES = [
    ("index", "Вся картина", "System One · исследовательский атлас", "От исследовательского вопроса до воспроизводимого вывода. τ-knowledge · banking_knowledge · адаптация модели.", "system-one-atlas.md"),
    ("research-plan", "Общий план", "Вопрос → опыт → вывод", "Три главных варианта, дешёвые контроли и проверяемые гипотезы. Каждый переход требует отдельного свидетельства.", "system-one-atlas.md"),
    ("execution", "Реализация этапов", "Как выполнить исследование", "11 операционных рецептов: входы, действия, артефакты, проверки и альтернативы при неудаче.", "system-one-atlas-execution.md"),
    ("roadmap", "Roadmap", "Маршрут к защите", "Предлагаемые зависимости и 24-недельный сценарий. Даты и положение ползунка не являются фактическим статусом работ.", "system-one-atlas.md"),
    ("software", "Архитектура", "Один шаг агента", "Три политики отбора, общий packer для frozen/adapted C, один основной LLM-агент и неизменная native среда τ-bench.", "system-one-atlas-architecture.md"),
    ("material", "Сбор материала", "Источник → наблюдение", "Статьи, код, KB, задачи и траектории имеют разные роли. У каждого объекта — происхождение, версия и граница доступа.", "system-one-atlas-protocol.md"),
    ("dataset", "Датасеты", "От наблюдений к меткам", "Split до rollout. Полезность фрагмента, достаточность набора и успех эпизода — разные целевые события.", "system-one-atlas-protocol.md"),
    ("training", "Обучение", "CE, Brier и рассуждения", "Отделяем функцию потерь от источника targets, механизма RLCD и генерации rationale на inference.", "system-one-atlas-evidence.md"),
    ("experiments", "Измерения", "Честное сравнение A / B / C", "Offline качество узла и online результат агента. Полные расходы, неудачи и неопределённость входят в результат.", "system-one-atlas-protocol.md"),
    ("results", "Результаты и источники", "Что уже известно", "Наши новые модельные результаты ещё не получены. Внешние свидетельства и прежние измерения проекта подписаны отдельно.", "system-one-atlas-evidence.md"),
]

# id, title, weeks (inclusive), dependencies, deliverable, gate
PHASES = [
    ("P0", "Вопрос и контракт", 1, 2, [], "Гипотезы · arms · определение метки", "Ясно, какая операция заменяется и что остаётся неизменным"),
    ("P1", "Аудит стенда и моделей", 1, 2, ["P0"], "Версии · лицензии · runtime profile", "Проверены полный input, inference и один training step"),
    ("P2", "Минимальный harness", 2, 4, ["P1"], "Adapter · snapshot · scorer · trace", "History, tools и hidden-data boundary проходят проверку"),
    ("P3", "Разделение задач", 2, 4, ["P1"], "Split manifest · leak report", "Связанные task families не пересекают train/dev/test"),
    ("P4", "Сбор наблюдений", 4, 6, ["P2", "P3"], "Raw trajectories · snapshots · usage", "Snapshot восстанавливается из raw без будущих сообщений"),
    ("P5", "Разметка и датасет", 6, 8, ["P4"], "Rubric · labels · dataset card", "Проверены качество меток, lineage и неопределённость"),
    ("P6", "Baseline и default S1", 7, 8, ["P2", "P5"], "Native / BM25 / LLM / frozen report", "Работает весь путь измерения качества и полной цены"),
    ("P7", "Дообучение и абляции", 8, 13, ["P5", "P6"], "CE / Brier checkpoints · dev ledger", "Конфигурации выбраны по dev и заморожены до test"),
    ("P8", "Закрытая итоговая оценка", 14, 16, ["P7"], "Test runs · paired metrics · CI", "Все попытки и расходы включены; test не использован для выбора"),
    ("P9", "Устойчивость и экономика", 16, 18, ["P8"], "Sensitivity · failure taxonomy · N*", "Вывод выдерживает дешёвые контроли и учёт fallback"),
    ("P10", "Выводы и ВКР", 18, 22, ["P8", "P9"], "Evidence ledger · воспроизведение · текст", "Каждый вывод прослеживается до измерения или источника"),
]


def node(key, label, tech, role="orch"):
    return {"id": key, "label": label, "tech": tech, "role": role}


def step(a, b, title, desc, payload, role="orch", chips=None):
    return dict(from_=a, to=b, color=f"--c-{role}", title=title, route="", desc=desc,
                payload=payload, chips=chips or ["проект протокола"])


def flow(name, *steps, note="Анимация описывает предложенный процесс; это не запуск моделей."):
    return {"name": name, "note": note, "steps": [dict(("from" if k == "from_" else k, v) for k, v in s.items()) for s in steps]}


def overview():
    nodes = [node("question", "Вопрос", "эффект доменной адаптации", "user"),
             node("data", "τ-knowledge", "задачи · KB · observed pool", "vector"),
             node("train", "Обучение", "CE / Brier · train only", "embed"),
             node("agent", "Агент A / B / C", "selector + actor LLM", "compute"),
             node("eval", "Измерение", "native reward · цена · время", "orch"),
             node("claim", "Вывод", "эффект + CI + ограничения", "user")]
    flows = {
        "study": flow("Исследование целиком",
            step("question", "data", "Определить независимые задачи", "Одно и то же предметное поле; test не участвует в адаптации.", {"domain": "banking_knowledge", "split_unit": "task_family", "split_before": "rollout"}, "vector"),
            step("data", "train", "Получить проверенные targets", "Train snapshots дают пары state/candidate. Gold и rationale не попадают в student input.", {"input": ["observable_state", "candidate"], "target": "useful", "uncertain": "separate"}, "embed"),
            step("train", "agent", "Подключить адаптированный scorer", "В главном сравнении меняются веса compact C, а actor, state и packer фиксированы.", {"A": "LLM selector", "B": "frozen S1", "C": "adapted S1"}, "compute"),
            step("agent", "eval", "Измерить весь эпизод", "Учитываем actor, scorer, fallback и ошибки. Качество узла оценивается отдельно.", {"metrics": ["native_success", "cost/attempt", "p50/p95_latency", "technical_failures"]}),
            step("eval", "claim", "Ответить на исходный вопрос", "Вывод может быть положительным, отрицательным или неопределённым.", {"new_results": None, "requires": ["paired_effect", "CI", "scope", "reproducibility"]}, "user")),
        "inference": flow("Один агентный цикл",
            step("data", "agent", "Получить разрешённый snapshot", "В pool только KB, реально полученная в этом диалоге.", {"cutoff": "current_turn", "hidden_gold": "forbidden"}, "compute"),
            step("agent", "agent", "Отобрать и выполнить", "Selector выбирает context, основной LLM делает tool call или отвечает.", {"selector": "A/B/C", "packer": "same for B/C", "selection_validation": "shared", "actor": "fixed LLM"}, "compute"),
            step("agent", "data", "Получить новый tool result", "Новые наблюдения меняют состояние. Будущие сведения не доступны заранее.", {"append_only": True, "pool": "observed only"}, "vector"),
            step("agent", "eval", "Завершить native episode", "Штатный evaluator оценивает результат по исходному протоколу.", {"tasks": "unchanged", "tools": "unchanged", "evaluator": "unchanged"})),
        "evidence": flow("От источника к выводу",
            step("question", "data", "Зафиксировать основания", "Сохраняем первичные статьи, версии кода и происхождение данных.", {"source": "primary", "revision": "pinned", "checked": "2026-10-19"}, "vector"),
            step("data", "eval", "Отделить авторские результаты", "Чужая таблица служит мотивацией; её нельзя присвоить своей системе.", {"published_results": "external", "own_runs": "not_run"}),
            step("eval", "claim", "Связать утверждения с данными", "Каждому собственному утверждению нужны run IDs и пределы применимости.", {"claim_status": ["observation", "proposal", "hypothesis", "unknown"]}, "user"))}
    return nodes, flows


def software():
    nodes = [node("runner", "Native runner", "visible inbox · environment", "user"),
             node("state", "Snapshot", "raw history → state + pool", "vector"),
             node("score", "Отбор контекста", "LLM joint / C frozen / C adapted", "embed"),
             node("pack", "Packer + view", "budget · provenance · tool IDs", "orch"),
             node("actor", "Actor LLM", "ответы и tool calls", "compute"),
             node("eval", "Trace / evaluator", "usage · reward · failures", "seed")]
    flows = {}
    for key, title, method in [("llm", "A · LLM-селектор", "LLM joint selection"), ("frozen", "B · Default S1", "original checkpoint"), ("adapted", "C · Adapted S1", "train-only checkpoint")]:
        flows[key] = flow(title,
            step("runner", "state", "Принять видимые сообщения", "Raw history сохраняется; snapshot содержит только наблюдаемые события. Native policy остаётся в защищённом actor-входе.", {"allowed": ["agent-visible messages", "agent-visible tool observations"], "forbidden": ["Task gold", "private user tools", "future turns"]}, "vector"),
            step("state", "score", "Отобрать из того же пула" if key == "llm" else "Оценить тот же набор кандидатов", "Полная сериализация проверяется на окно. В разных arm одинаковые содержательные сведения.", {"method": method, "input": ["state", "all candidates", "budget"] if key == "llm" else ["state", "candidate"], "output": "ordered IDs" if key == "llm" else "p(useful) for each candidate"}, "embed"),
            step("score", "pack", "Проверить выбранный набор" if key == "llm" else "Выбрать набор в общем бюджете", "Проверить IDs, уникальность и готовый бюджет KB-блока; LLM pointwise с общим packer — отдельная абляция." if key == "llm" else "Детерминированный общий packer frozen/adapted соблюдает бюджет и правило tie-breaking.", {"selected_ids": "proposal", "budget_tokens": 2048, "budget_status": "pilot proposal", "operation": "validate joint selection" if key == "llm" else "common packer"}),
            step("pack", "actor", "Построить производный input", "Вставить выбранный KB блок один раз; сохранить роли, call IDs и non-KB результаты.", {"raw_history": "immutable", "actor_view": "derived", "rationale_from_teacher": "absent"}, "compute"),
            step("actor", "runner", "Сделать native действие", "Основной LLM сам выбирает инструмент и аргументы. System One этого не делает.", {"action": "native tool call or response", "policy": "unchanged"}, "user"),
            step("runner", "eval", "Оценить и учесть затраты", "Evaluator отделён от scorer; trace включает неудачи и полный usage.", {"native_reward": "measured at runtime", "trace": "all attempts"}, "seed"))
    flows["failure"] = flow("Технический fallback",
        step("state", "score", "Обнаружить ошибку scorer", "Переполнение или NaN — технический отказ, а не калиброванный риск.", {"reason": ["STATE_OVERFLOW", "CANDIDATE_OVERFLOW", "SCORER_ERROR"]}, "embed"),
        step("score", "score", "Передать тот же snapshot LLM", "Fallback не получает extra history, hidden gold или compact scores.", {"same_snapshot_hash": True, "fallback": "LLM selector if admissible"}, "embed"),
        step("score", "pack", "Проверить итоговый набор", "При повторной неудаче не использовать отвергнутый набор молча.", {"valid_ids": "required", "invalid_after_retry": "explicit failure"}),
        step("pack", "eval", "Сохранить исход и обе цены", "Все расходы до ошибки остаются в полном эпизоде.", {"technical_defer": True, "calibrated_defer": False, "cost": "S1 + fallback + retries"}, "seed"))
    return nodes, flows


def dataset():
    nodes = [node("tasks", "Задачи / KB", "upstream manifest", "user"), node("split", "Group split", "train · dev · test", "orch"),
             node("rollout", "Наблюдения", "raw → snapshots", "vector"), node("labels", "Разметка", "rubric · teacher · audit", "embed"),
             node("dataset", "Dataset v1", "pairs · sets · episodes", "vector"), node("eval", "Training / test", "изолированные назначения", "compute")]
    return nodes, {
        "build": flow("Подготовка обучающего набора",
            step("tasks", "split", "Сначала разделить семьи задач", "Связанные шаблоны и производные примеры получают один split.", {"unit": "task_family", "ratio": "~60/20/20 proposal", "exact_counts": "after audit"}),
            step("split", "rollout", "Собирать train/dev траектории", "Test не используется для teacher prompts, поиска ошибок модели и HPO.", {"allowed": ["train", "dev"], "frozen_test": True}, "vector"),
            step("rollout", "labels", "Разметить полезность пары", "Успех эпизода не назначает метку всем chunks. Неоднозначные примеры сохраняются отдельно.", {"key": ["snapshot_id", "candidate_id"], "label": ["useful", "irrelevant", "uncertain"]}, "embed"),
            step("labels", "dataset", "Собрать versioned corpus", "Включить provenance, аудит меток и sampling policy; исключить rationale из student inputs.", {"lineage": "source → episode → snapshot → label", "hashes": "required"}, "vector"),
            step("dataset", "eval", "Обучать только на train", "Dev выбирает конфигурации; отдельный test применяется после заморозки.", {"train": "gradient", "dev": "selection", "test": "final evaluation"}, "compute")),
        "labels": flow("Проверка качества меток",
            step("rollout", "labels", "Независимый audit subset", "Рубрика требует текстового основания и применимости к наблюдаемому состоянию.", {"reviewers": "independent where available", "disagreement": "keep"}, "embed"),
            step("labels", "labels", "Проверить трудные случаи", "Исключения, дубли и контрфактическое удаление evidence проверяются отдельно.", {"episode_success_is_chunk_label": False, "counterfactual": "stochastic evidence, not oracle"}, "embed"),
            step("labels", "dataset", "Опубликовать качество разметки", "Размер и доля ошибок labels ограничивают силу будущих выводов.", {"audit_size": "measured", "label_error": None, "status": "not_measured"}, "vector")),
        "leak": flow("Защита от утечки",
            step("tasks", "split", "Зафиксировать происхождение", "Парафразы и синтетические потомки наследуют исходную task family.", {"ancestry_split": "single", "near_duplicates": "audit"}),
            step("split", "dataset", "Проверить manifests", "Текст KB может быть общим, но test tasks/targets не входят в обучение.", {"shared_domain_KB": "declared", "test_task_labels_in_train": False}, "vector"),
            step("dataset", "eval", "Сверить входы модели", "Gold, будущие сообщения, rationale и hidden allowlist запрещены на scorer input.", {"input_audit": "required", "test_tuning": "forbidden"}, "compute"))}


def training():
    nodes = [node("data", "Train pairs", "проверенные полезность/targets", "vector"), node("teacher", "Учитель", "без / с reasoning", "compute"),
             node("ce", "CE", "прямой градиент", "embed"), node("brier", "Brier", "прямой градиент", "embed"),
             node("model", "Compact student", "тот же checkpoint / head", "orch"), node("dev", "Dev → freeze", "выбор до final test", "user")]
    return nodes, {
        "loss": flow("Основной опыт CE ↔ Brier",
            step("data", "ce", "CE на hard labels", "Базовая линия: одинаковый train и отсутствие rationale в student input.", {"loss": "-mean[y log p + (1-y) log(1-p)]", "reasoning_inference": False}, "embed"),
            step("data", "brier", "Brier-only на тех же labels", "Штатный KEV brier_w добавляет term к CE; pure Brier требует проверки отдельной ветки.", {"loss": "mean[(p-y)^2]", "not": "CE + lambda*Brier"}, "embed"),
            step("ce", "model", "Обновить одинаковые параметры", "Одна инициализация и сопоставимый train/HPO budget.", {"paired_initialization": True, "trainable_layers": "recorded"}),
            step("brier", "model", "Сопоставить альтернативный objective", "Масштаб градиента отличается; dev search должен быть равноправным.", {"hpo_budget": "equal opportunity", "learning_rate": "recorded per arm"}),
            step("model", "dev", "Выбрать и заморозить", "Checkpoint выбирается на dev_tune; raw и matched temperature-scaled результаты frozen/CE/Brier сравниваются с калибровкой на dev_cal. Test не выбирает температуру.", {"frozen": ["checkpoint", "prompt", "packer", "budget"], "calibration_split": "dev_cal", "test_used": False}, "user")),
        "teacher": flow("Рассуждения только у учителя",
            step("data", "teacher", "Два режима одной модели", "Учитель видит одинаковую наблюдаемую информацию; mode и расходы фиксируются.", {"teacher_modes": ["direct", "reasoning"], "same_input": True}, "compute"),
            step("teacher", "data", "Проверить targets", "Reasoning не считается доказательством правильности. Нужен независимый аудит.", {"teacher_label": "weak until checked", "rationale": "lineage only"}, "vector"),
            step("data", "model", "Дистиллировать решения", "Student обучается выдавать вероятность напрямую, без генерируемого текста рассуждения.", {"factorial": "teacher mode × student loss", "student_rationale": False}),
            step("model", "dev", "Измерить эффект targets", "Отделяем качество учителя от поведения и цены компактного student.", {"compare": ["label quality", "Brier/NLL", "native reward", "adaptation cost"]}, "user")),
        "rlcd": flow("RLCD — дополнительная ветка",
            step("data", "teacher", "Выбрать конкретный механизм", "OpenJev обучает rationale policy; Laya/SBERT2S1 использует noise-based estimator без текста rationale.", {"OpenJev": "readout + rationale RL", "Laya": "noisy-logit score estimator"}, "compute"),
            step("teacher", "model", "Отделить механизм от loss", "RLCD и Brier не взаимоисключающие названия: proper score может быть reward.", {"factor": ["objective", "gradient estimator", "architecture", "rationale"]}),
            step("model", "dev", "Проверить выполнимость и цену", "Этот блок не обязателен для завершения ВКР. При недостатке ресурсов сохраняется отрицательное заключение.", {"critical_path": False, "go_gate": "working core + budget + data"}, "user"))}


def experiments():
    nodes = [node("manifest", "Manifest", "tasks · seeds · versions", "vector"), node("arms", "A / B / C + N/H", "общие ограничения", "orch"),
             node("node", "Offline узел", "вероятности · evidence", "embed"), node("episode", "Online агент", "native задачи и reward", "compute"),
             node("stats", "Парный анализ", "task/family clusters · CI", "orch"), node("result", "Результат", "качество · цена · задержка", "user")]
    return nodes, {
        "offline": flow("Оценка одного узла",
            step("manifest", "arms", "Заморозить snapshots", "Все оценщики видят одинаковые state, candidates и бюджет.", {"snapshot_hash": "shared", "labels": "held-out"}),
            step("arms", "node", "Посчитать вероятности и набор", "Brier/NLL — для вероятностей, ranking — для всех scorers. BM25 score не является p.", {"metrics": ["Brier", "NLL", "PR-AUC", "evidence coverage"]}, "embed"),
            step("node", "stats", "Учесть зависимость примеров", "Много turns одной задачи не превращаются в независимые task samples.", {"cluster": "task/family", "training_seed": "separate variability"}),
            step("stats", "result", "Опубликовать effect + CI", "Этот вывод относится к узлу; успех полного агента ещё требует online серии.", {"scope": "fixed snapshot distribution", "episode_claim": False}, "user")),
        "online": flow("Оценка полного агента",
            step("manifest", "arms", "Парная task-seed матрица", "Одинаковые actor, simulator и evaluator; порядок arm сбалансирован.", {"primary_contrast": "adapted vs frozen", "controls": ["native", "BM25", "LLM"]}),
            step("arms", "episode", "Выполнить независимые диалоги", "Разные решения меняют последующие истории. Это и есть closed-loop эффект.", {"fixed_history": False, "native_contract": "preserved"}, "compute"),
            step("episode", "stats", "Не потерять ошибки и расходы", "В знаменатель успеха входят все назначенные task-trial, включая timeout и failures; retries сохраняются как попытки с расходами, не как независимые задачи. Simulator/evaluator price показана отдельно.", {"success_denominator": "assigned task-trials", "cost": ["actor", "selector", "fallback", "all retry attempts"], "research_cost": ["simulator", "evaluator"]}),
            step("stats", "result", "Сопоставить качество и цену", "Non-inferiority δ закрепляется заранее. Отсутствие значимости не доказывает равенство.", {"outputs": ["paired ΔQ with CI", "cost/attempt", "cost/success", "p50/p95"]}, "user")),
        "economics": flow("Окупаемость адаптации",
            step("manifest", "stats", "Собрать полную цену адаптации", "Teacher labels, ручная проверка, GPU и HPO должны быть видны.", {"C_adapt": "data + annotation + training + HPO"}),
            step("episode", "stats", "Проверить экономию эпизода", "Неподтверждённое соблюдение ограничения качества или неположительная экономия не позволяют заявить выгоду.", {"delta_cost": "C_ref - C_adapted", "quality_constraint": "predeclared delta with uncertainty"}),
            step("stats", "result", "Вычислить границу окупаемости", "Только при положительной экономии; иначе конечного N* нет.", {"N_star": "C_adapt / delta_cost", "measured_here": False}, "user"))}


def material():
    nodes = [node("sources", "Первичные источники", "papers · repos · model cards", "user"), node("registry", "Реестр", "version · license · claim", "orch"),
             node("native", "Native assets", "tasks · KB · policy · tools", "vector"), node("collect", "Collector", "train/dev only", "compute"),
             node("store", "Хранилище", "raw · snapshots · provenance", "vector"), node("audit", "Аудит", "качество · утечки · расходы", "embed")]
    return nodes, {
        "sources": flow("Сбор научных оснований",
            step("sources", "registry", "Проверить утверждение у автора", "Статья, код и model card могут говорить о разных версиях; сохраняем область применимости.", {"fields": ["URL", "date", "revision", "claim", "scope", "license"]}),
            step("registry", "native", "Зафиксировать стенд", "Основная линия — τ-knowledge banking_knowledge, а не произвольный retail benchmark.", {"repo": "sierra-research/tau2-bench", "domain": "banking_knowledge"}, "vector"),
            step("native", "audit", "Проверить пригодность", "Исходные tasks — сценарии среды, а не готовый supervised dataset для scorer.", {"training_rows": "must derive from permitted observations"}, "embed")),
        "collect": flow("Сбор собственного корпуса",
            step("native", "collect", "Выбрать train/dev IDs", "Предварительный grouped split предшествует любому целевому rollout.", {"split_manifest": "required", "test_in_collector": False}, "compute"),
            step("collect", "store", "Сохранить все попытки", "Не фильтровать неудачные эпизоды; записать стоимость и причину остановки.", {"raw_trace": "append-only", "outcome": "success or failure", "usage": "all calls"}, "vector"),
            step("store", "audit", "Восстановить snapshots", "Каждый фрагмент имеет observation ID, cutoff и content hash.", {"future_leak": False, "hidden_corpus_lookup": False}, "embed"),
            step("audit", "registry", "Зафиксировать dataset lineage", "В Git — разрешённые metadata и checksums. Объёмные тела хранятся отдельно с доступом команды.", {"storage": "to be selected", "backup": "required", "Git": "metadata only"}))}


def results():
    nodes = [node("external", "Внешние работы", "результаты авторов", "vector"), node("prior", "Прежние наблюдения", "703 момента выбора / 52 истории", "vector"),
             node("planned", "Новые опыты", "A/B/C · CE/Brier", "embed"), node("ledger", "Evidence ledger", "источник · run ID · статус", "orch"),
             node("claim", "Вывод ВКР", "эффект и область применимости", "user"), node("limits", "Ограничения", "смещение · n · стоимость", "seed")]
    return nodes, {
        "now": flow("Состояние на 19.10.2026",
            step("external", "ledger", "Записать авторские результаты", "Внешние цифры не являются результатами нашей реализации на banking.", {"owner": "paper authors", "transfer_to_tau": "unverified"}),
            step("prior", "ledger", "Отдельно отметить прежнее измерение", "Это аудит длины опубликованных историй, не оценка качества модели. Здесь он не повторялся.", {"observations": 703, "published_trajectories": 52, "metric": "context size"}),
            step("planned", "ledger", "Не заполнять отсутствующие метрики", "Нет run manifest — нет численного результата. Анимация только объясняет протокол.", {"Q_A": None, "Q_B": None, "Q_C": None, "status": "not_run"}),
            step("ledger", "limits", "Зафиксировать неизвестное", "Ещё нужны labels, выбранные checkpoint, final split, API budget и runtime pilot.", {"winner": "unknown", "next": "P0/P1 feasibility"}, "seed")),
        "future": flow("Как появится научный вывод",
            step("planned", "ledger", "Приложить реальные run IDs", "После эксперимента сохраняются сырые данные и неизменяемая сводка.", {"link": "claim → analysis → runs → manifests"}),
            step("ledger", "claim", "Оценить знак и неопределённость", "Положительный, отрицательный и неопределённый исходы одинаково допустимы.", {"outcome": ["supported", "not_supported", "insufficient_evidence"]}, "user"),
            step("claim", "limits", "Ограничить обобщение", "Same-domain данные не доказывают перенос в новую область; дорогой baseline не заменяет дешёвый.", {"scope": "pinned domain/tasks/models", "cheap_control": "required"}, "seed"))}


def phases_overview():
    nodes = [node("scope", "P0–P1 · Основание", "контракт · версии", "user"), node("infra", "P2–P3 · Стенд", "harness · split", "orch"),
             node("data", "P4–P5 · Данные", "сбор · разметка", "vector"), node("fit", "P6–P7 · Модели", "baseline · адаптация", "embed"),
             node("test", "P8–P9 · Измерение", "test · устойчивость", "compute"), node("thesis", "P10 · ВКР", "выводы · воспроизведение", "user")]
    return nodes, {"core": flow("Основной маршрут",
        step("scope", "infra", "Из постановки в проверяемый контракт", "Рабочий extension point и sealed split нужны до сбора материала.", {"phases": ["P0", "P1", "P2", "P3"], "weeks": "1–4"}),
        step("infra", "data", "Получить независимые данные", "Истории → snapshots → проверенные метки, с lineage и аудитом.", {"phases": ["P4", "P5"], "weeks": "4–8"}, "vector"),
        step("data", "fit", "Сначала контроль, затем обучение", "Frozen и дешёвые baseline предшествуют CE/Brier; reasoning — расширение.", {"phases": ["P6", "P7"], "weeks": "7–13"}, "embed"),
        step("fit", "test", "Заморозить и оценить", "Test не выбирает checkpoint, budget, prompt или threshold.", {"phases": ["P8", "P9"], "weeks": "14–18"}, "compute"),
        step("test", "thesis", "Довести до воспроизведения", "Связать измерения с выводами, личным вкладом и ограничениями.", {"phase": "P10", "weeks": "18–22", "buffer": "23–24"}, "user")),
        "stop": flow("Если гипотеза не подтверждается",
        step("fit", "test", "Сохранить отрицательный опыт", "Нет прироста после ограниченного dev search — измеримый результат, а не повод бесконечно подбирать.", {"stop": ["budget", "invalid labels", "no dev gain", "runtime infeasible"]}, "compute"),
        step("test", "scope", "Пересмотреть объяснение", "Отделить ограничение метода от ошибки данных или реализации.", {"distinguish": ["bug", "measurement error", "negative effect", "underpowered study"]}, "user"),
        step("scope", "thesis", "Завершить честное исследование", "Положительный эффект, RLCD и публикация не являются обязательным исходом.", {"required": ["formal question", "reproducible agent", "measurements", "comparison"]}, "user"))}


def phase_diagram(p):
    key, title, first, last, deps, deliverable, gate = p
    nodes = [node("input", "Вход", " + ".join(deps) or "поручение и контекст", "user"), node("work", key + " · Работа", title, "orch"),
             node("artifact", "Артефакт", deliverable, "vector"), node("check", "Проверка", "свидетельство готовности", "embed"),
             node("next", "Следующий этап", "при выполненном критерии", "user"), node("repair", "Альтернативный путь", "причина · ограничение · новый run", "seed")]
    recipes = {
        "P0": [
            step("input", "work", "Определить событие useful", "Оценивать применимость каждой наблюдаемой KB-единицы к текущей потребности. Несколько документов могут быть полезны одновременно; uncertain не превращается в 0.", {"unit": "state/candidate pair", "labels": ["useful", "irrelevant", "uncertain"], "probabilities": "independent binary"}),
            step("work", "artifact", "Зафиксировать сравнение и вклад", "Главный контраст — default C против adapted C. Actor, state и packer фиксированы; R выключен в основном опыте.", {"primary": "B vs C", "arms": ["LLM joint", "frozen", "adapted"], "anchors": ["native", "recency", "BM25"]}, "vector"),
            step("artifact", "check", "Проверить рубрику на примерах", "Два читателя независимо разбирают 10–20 учебных пар и объясняют расхождения. Одновременно фиксируются Q и научно обоснованная допустимая потеря δ до test.", {"audit_size": "10–20 proposal", "primary_Q": "to preregister", "delta": "before test", "disagreements": "retain"}, "embed"),
            step("check", "next", "Выпустить protocol v0", "К аудиту стенда переходят с операциональной меткой, таблицей arms и условиями опровержения гипотез; нерешённые числа помечены предложениями.", {"outputs": ["rubric", "hypotheses", "arms", "metric definitions"], "next": "P1"}, "user")],
        "P1": [
            step("input", "work", "Закрепить источники и разрешения", "Проверить commit τ, реальные task IDs, KB/policy/tools/evaluator и лицензии кода, данных и весов по отдельности.", {"manifest": ["URI", "revision", "SHA256", "license", "scope"], "domain": "banking_knowledge"}),
            step("work", "artifact", "Измерить полный модельный вход", "Прогнать сериализованную пару state/candidate с инструкциями и labels; измерить tokens, память и latency, включая точную границу окна без truncation.", {"input": "fully serialized payload", "profile": ["tokens", "peak memory", "batch latency"], "silent_truncation": False}, "vector"),
            step("artifact", "check", "Проверить один training step", "Finite loss, ненулевой gradient и обновление параметров проверяются до длинной серии. Сохранённый checkpoint должен загружаться и воспроизводить прогноз.", {"checks": ["finite loss", "nonzero gradient", "weight update", "save/reload"], "quality_improvement_claim": False}, "embed"),
            step("check", "next", "Выбрать совместимый runtime", "Закрепить один compact candidate и резерв; проверить LLM provider, reasoning/tool history и отдельные роли actor/simulator/evaluator.", {"outputs": ["compatibility report", "hardware profile", "model manifest"], "next": ["P2", "P3"]}, "user")],
        "P2": [
            step("input", "work", "Воспроизвести native эпизод", "Получить штатные trajectory и reward до вмешательства. Подключить текстовый agent factory, не передавая Task/gold в agent state.", {"extension": "HalfDuplexAgent", "native_evaluator": "unchanged", "Task_in_agent": False}),
            step("work", "artifact", "Собрать snapshot из наблюдений", "Append-only raw, детерминированный state и весь observed pool хранятся отдельно. ID+content version сохраняет происхождение и изменения текста.", {"objects": ["raw_history", "observed_pool", "snapshot"], "hash": "semantic", "LLM_summary": False}, "vector"),
            step("artifact", "check", "Проверить projection и ошибки", "Смешанный KB/business batch сохраняет roles и call IDs. Выбранный блок вставляется один раз, raw не мутирует; NaN, overflow, invalid IDs и exhausted fallback различимы.", {"tests": ["mixed batch", "hidden sentinel", "token boundary", "failure cases"], "raw_mutation": False}, "embed"),
            step("check", "next", "Открыть сбор только с ledger", "No-op fixture совпадает с native входом, а каждая попытка и её расходы сохраняются даже при исключении runner. Adapted checkpoint пока только точка подключения.", {"outputs": ["adapter", "selection", "projection", "attempt ledger"], "next": "P4 after P3"}, "user")],
        "P3": [
            step("input", "work", "Построить граф родства задач", "Связать одинаковые шаблоны, policy scenarios, entities и близкие формулировки; компоненты проверить вручную до rollout и labels.", {"edges": ["template", "scenario", "entities", "near duplicate"], "split_unit": "ancestry group"}),
            step("work", "artifact", "Назначить split целым группам", "Ориентир 60/20/20 — предложение; крупную связанную группу не разрезают ради пропорции. Все turns, retries и синтетические потомки наследуют split.", {"splits": ["train", "dev_tune", "dev_cal", "locked test"], "descendants": "inherit group split", "counts": "after audit"}, "vector"),
            step("artifact", "check", "Проверить manifest на утечки", "Сохранить IDs, family IDs, seed, hashes и ручные исключения. Искать exact/near duplicates и test IDs в teacher/HPO jobs; общий KB описать отдельным пересечением.", {"assertions": ["no cross-split ancestry", "no test in teacher train", "no test in HPO"], "shared_KB": "declared"}, "embed"),
            step("check", "next", "Запечатать test до генерации", "Collector получает разрешённый split manifest. Если независимых групп мало, сохранить честный holdout и широкие CI; опубликованные 97 задач после обучения на части не являются независимым test.", {"output": "split manifest + leak report", "next": "P4", "synthetic_rows_add_independent_tasks": False}, "user")],
        "P4": [
            step("input", "work", "Назначить разрешённые rollout", "Выбрать только train/dev IDs, collector policy, actor/simulator versions, seeds и retry policy. До запуска задать cap расходов и остановку.", {"inputs": ["working harness", "sealed split"], "collectors": ["native", "cheap or LLM baseline"], "test": "excluded"}),
            step("work", "artifact", "Записать все эпизоды и попытки", "Сохранять ошибки и ранние остановки вместе с успешными историями. Запись включает raw tool results, outcome и usage каждого вызова.", {"outputs": ["raw trajectories", "episode manifests", "attempt ledger"], "success_filter": False}, "vector"),
            step("artifact", "check", "Восстановить snapshot по cutoff", "Перед actor call из полученного KB batch выделить state, полный observed pool и exact serialization. Повторная сборка из raw должна дать тот же hash без будущих сообщений.", {"checks": ["same snapshot hash", "source spans", "no future", "content versions"], "hidden_lookup": False}, "embed"),
            step("check", "next", "Передать корпус с диагностикой", "Опубликовать доли повреждений, пустых пулов, переполнений и покрытие сценариев. Collector bias записать в dataset card; тела хранить вне Git с checksums.", {"outputs": ["snapshot index", "parser diagnostics", "coverage report"], "stop": ["budget", "test leak", "provider drift", "parser regression"], "next": "P5"}, "user")],
        "P5": [
            step("input", "work", "Создать проверенный audit set", "Разметить полезные, нерелевантные и неоднозначные пары по рубрике. Часть читают независимо два человека; disagreement и adjudication сохраняются.", {"input": "train/dev snapshots", "unit": "state/candidate", "uncertain": "separate", "teacher_is_gold": False}),
            step("work", "artifact", "Масштабировать метки с provenance", "Teacher размечает ту же наблюдаемую пару; сохраняются prompt, model, reasoning mode, ответ и цена. Hard negatives берутся из observed pool, а sampling и веса документируются.", {"labels": "weak until audited", "negatives": "observed pool only", "sampling_policy": "versioned"}, "vector"),
            step("artifact", "check", "Проверить пары и наборы отдельно", "Counterfactual inclusion/removal на subset оценивает вклад evidence стохастически. Дубли и взаимодействия не позволяют переносить episode success на каждый документ.", {"tables": ["candidate usefulness", "set sufficiency", "episode outcome"], "counterfactual": "estimate, not oracle", "label_audit": "required"}, "embed"),
            step("check", "next", "Выпустить dataset v1", "Сохранить lineage, class balance, ambiguity, sampling weights и независимые назначения train/dev. Неуверенные labels не заменяются отрицательными; их обработка явно задана.", {"outputs": ["dataset card", "label audit", "versioned rows", "row hashes"], "next": "P6"}, "user")],
        "P6": [
            step("input", "work", "Сравнить frozen и опорные методы", "На одинаковых snapshots выполнить recency, BM25, LLM joint и frozen C; native agent остаётся отдельным online anchor. LLM pointwise с тем же packer — диагностика scorer.", {"offline_information": "same state/pool/budget", "native_history": "unchanged", "adaptation": "not yet"}),
            step("work", "artifact", "Разделить raw и calibrated метрики", "Brier/NLL считать только для вероятностей; BM25 оценить по ranking/set. Сохранить published temperature и matched raw/TS результаты с fit на dev_cal.", {"metrics": ["Brier", "NLL", "PR-AUC", "evidence coverage"], "BM25_probability": False, "TS_fit": "dev_cal"}, "vector"),
            step("artifact", "check", "Проверить dev online pilot", "При фиксированных actor/simulator/evaluator и seed schedule измерить native success, latency, fallback и полную цену. Порядок arms сбалансировать; failures не терять.", {"split": "dev, not final test", "ledger": "all calls and attempts", "roles": "fixed across arms"}, "embed"),
            step("check", "next", "Оценить цену основной серии", "Baseline report должен объяснять, зачем нужна модель относительно дешёвых методов, и дать оценку расходов дальнейшего обучения и теста.", {"outputs": ["baseline report", "latency distributions", "cost forecast"], "cheap_control_removal": False, "next": "P7"}, "user")],
        "P7": [
            step("input", "work", "Проверить CE и Brier на smoke step", "Одна инициализация и hard labels без student rationale. Сверить формулы на ручном примере, finite gradients и реальные обновления; CE+λBrier не называть pure Brier.", {"losses": ["binary CE", "(p-y)^2"], "initialization": "paired", "input_rationale": False}),
            step("work", "artifact", "Обучить и сохранить checkpoints", "Записать trainable modules, seeds, optimizer, schedule, precision, порядок данных и hardware. Число примеров/шагов и бюджет HPO сопоставимы; одинаковый LR сам по себе не гарантирует честный tuning.", {"arms": ["frozen", "adapted CE", "adapted Brier"], "lineage": "base → train rows → checkpoint", "HPO": "equal opportunity"}, "vector"),
            step("artifact", "check", "Выбрать на dev и откалибровать", "Early stopping и checkpoint выбираются на dev_tune, matched TS — на dev_cal. Сохранить learning curves, стоимость и отрицательные результаты; teacher-mode×loss остаётся отдельным расширением.", {"dev_tune": "checkpoint/HPO", "dev_cal": "temperature scaling", "test": "unused", "extensions": "separate factors"}, "embed"),
            step("check", "next", "Заморозить итоговые конфигурации", "До final test закрепить веса, prompts, packer, budgets и analysis plan. OOM, плохие labels или исчерпанный cap останавливают расширения, а не стирают опыт.", {"outputs": ["checkpoint manifests", "loss audit", "dev selection ledger", "frozen configs"], "next": "P8"}, "user")],
        "P8": [
            step("input", "work", "Сверить sealed configs и test", "Проверить hashes и отсутствие test в train/HPO. Зафиксировать первичный контраст, δ, анализ, расход и правило остановки перед открытием результатов.", {"checks": ["checkpoint hash", "split hash", "no test tuning"], "primary": "adapted vs frozen"}),
            step("work", "artifact", "Выполнить парную task-seed матрицу", "Все arms получают одинаковое назначение задач и simulator seeds. Offline snapshots и самостоятельные online диалоги оцениваются раздельно; различия будущих историй допустимы.", {"arms": ["A", "B", "C", "native", "cheap"], "paired_unit": "task/trial", "identical_future_history": False}, "vector"),
            step("artifact", "check", "Считать эффекты с кластерными CI", "Native success, полная цена и задержка включают все назначенные эпизоды; retries остаются в расходах. Bootstrap группируется по task/family, training и simulator variability различаются.", {"analysis": "paired effects + clustered CI", "independent_unit": "task/family, not chunk", "cost_per_success_if_zero": "not finite"}, "embed"),
            step("check", "next", "Зафиксировать неизменяемый отчёт", "У графиков есть split, версии, число задач/групп/seeds и метод CI. Ошибка измерения требует нового run с причиной; просмотр test не разрешает скрытый выбор гиперпараметров.", {"outputs": ["run manifest", "metrics", "95% CI", "failure inventory", "analysis code"], "next": "P9/P10"}, "user")],
        "P9": [
            step("input", "work", "Выполнить заранее заданные срезы", "Проверить budgets 1024/2048/4096 как предложенные профили, длинные входы, policy exceptions, пустой retrieval и несколько необходимых evidence units. Не менять primary по лучшему test срезу.", {"plan": "predeclared sensitivity", "budgets_status": "proposal", "test_best_to_primary": False}),
            step("work", "artifact", "Разложить время и расходы", "Отдельно измерить scorer, packer, actor, tools, сеть, retries и двойную работу fallback; cold start, steady-state, batch throughput и online latency не смешивать.", {"costs": ["service inference", "teacher/labels", "HPO/training", "simulator/evaluator"], "timing": ["wall-clock", "component spans"]}, "vector"),
            step("artifact", "check", "Проверить качество и окупаемость", "Построить quality–cost/latency графики с CI. N* имеет смысл лишь при подтверждённом соблюдении ограничения качества и положительной экономии; иначе сообщить отсутствие устойчивой оценки.", {"N_star": "C_adapt / (C_ref - C_adapted)", "requires": ["quality constraint with uncertainty", "positive savings"], "not_measured_here": True}, "embed"),
            step("check", "next", "Ограничить обобщение вывода", "Неустойчивые срезы входят в итог. Другой домен — отдельная external validation; learned R — отдельная серия при фиксированном C и независимой calibration.", {"outputs": ["robustness report", "cost model", "failure taxonomy", "scope limits"], "next": "P10"}, "user")],
        "P10": [
            step("input", "work", "Связать каждое утверждение с опытом", "Собрать цепочку claim → график/таблица → analysis version → run IDs → manifests. По каждой гипотезе отделить поддержку, отсутствие поддержки и недостаток данных.", {"evidence_types": ["own measurement", "external result", "interpretation", "unknown"], "non_significance_is_equality": False}),
            step("work", "artifact", "Собрать воспроизводимый пакет", "Включить environment lock, конфигурации, разрешённые assets, происхождение, hashes и команды уже существующего кода. Секреты, веса и большие raw dumps не добавляются в Git.", {"outputs": ["lockfile", "configs", "data/model/split hashes", "smoke example", "real commands"], "Git": "permitted metadata"}, "vector"),
            step("artifact", "check", "Повторить из чистого окружения", "Другой участник проверяет smoke и ключевой анализ; если доступен только автор, ограничение явно записывается. Проверяются личный вклад, источники, CI и требования ВКР.", {"review": "independent where available", "checks": ["reproduction", "claims provenance", "personal contribution", "VKR rules"]}, "embed"),
            step("check", "next", "Завершить ВКР и обновить карты", "HTML получает фактические статусы и ссылки на raw-derived результаты. Постановка, воспроизводимый агент, измерения и сравнение обязательны; положительный эффект, RLCD и статья — нет.", {"outputs": ["thesis", "talk", "reproduction package", "updated atlas"], "negative_results": "retained", "publishing": "separate authorization"}, "user")],
    }
    return nodes, {"recipe": flow(title, *recipes[key]),
        "failure": flow("Если критерий не пройден",
        step("artifact", "check", "Зафиксировать фактическую проблему", "Сохранить версии и наблюдение; отделить ошибку реализации от отрицательного результата.", {"keep": ["failed artifact", "reason", "cost", "revision"]}, "embed"),
        step("check", "repair", "Выбрать ограниченный ответ", "Исправление, уменьшение scope или остановка расширения описываются в протоколе.", {"options": ["repair", "narrow scope", "report infeasible"]}, "seed"),
        step("repair", "work", "Повторить с новой версией", "Не подменять старые данные и не использовать test для скрытого выбора.", {"new_run_id": "required when rerun", "silent_overwrite": False}))}


def diagram(key):
    if key == "index":
        return overview()
    if key in {"research-plan", "execution", "roadmap"}:
        return phases_overview()
    return {"software": software, "dataset": dataset, "training": training,
            "experiments": experiments, "material": material, "results": results}[key]()
