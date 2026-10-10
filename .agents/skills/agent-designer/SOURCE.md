Источник: https://github.com/borghei/Claude-Skills/tree/5318eda16c134c500c237425404975545c0eedd2/engineering/agent-designer
Коммит: `5318eda16c134c500c237425404975545c0eedd2`; версия навыка: `1.1.0`.
Установлено в проект 01.10.2026 без изменений исходных файлов (историческое
состояние на дату импорта).

Исходная лицензия закреплённой ревизии: [корневой LICENSE](https://github.com/borghei/Claude-Skills/blob/5318eda16c134c500c237425404975545c0eedd2/LICENSE),
Git blob `9d84f9e269c910c4ba7e636f6c3febce1c468ac4`. Это MIT с условием
Commons Clause License Condition v1.0 и уведомлением Copyright (c) 2025–2026
Amin Borghei. Полный текст и уведомление сохранены в [LICENSE](LICENSE).

Локальные изменения 09.10.2026 после импорта: `agent_planner.py` исправляет
размеры команд и отсутствующие ссылки между агентами, сериализует значения enum
и экспортирует YAML; `tool_schema_generator.py` сохраняет JSON Schema типы,
`required` и `items`, проверяет schema/examples при `--validate`;
`agent_evaluator.py` исправляет конструирование рекомендаций и считает метрики
инструментов по наблюдаемым actions, отдельно отмечая отсутствующую телеметрию.
`README.md` дополняет исполняемые примеры входов; `expected_outputs/` пересозданы
из текущих `assets/`. Регрессионные проверки находятся в `tests/`.
Зависимости локальной проверки устанавливаются из корня репозитория командой
`python -m pip install -r requirements-tools.txt`.
