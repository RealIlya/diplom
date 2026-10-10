# Full Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Устранить подтверждённые дефекты материалов и встроенных инструментов, конкретизировать проект протокола.
**Architecture:** Общие исследовательские требования остаются в существующих канонических docs.
Исправления генераторов ограничены их действующими интерфейсами; проверки запускаются из одного unittest suite.
**Tech Stack:** Python 3.12/3.13, unittest, jsonschema 4.26.0, PyYAML 6.0.3, MkDocs Material 9.7.7, Artifact Tool 2.8.85.
**Spec:** ../specs/2026-10-09-audit-remediation-design.md

## Global Constraints

- Автор Git-коммитов: RealIlya <61643012+RealIlya@users.noreply.github.com>.
- Рабочая ветка codex/full-audit-fixes от b20c917; main не изменяется напрямую.
- Документы и описание результатов на русском; файлы и идентификаторы кода на английском.
- Исследовательские решения сохраняют статус предложения, результаты не выдумываются.
- Ни платных API, ни аренды GPU, ни научной серии в этом изменении.
- Реальные дефекты кода исправляются после воспроизведения регрессионным тестом.
- Контрольные суммы сверяются с конечным Git blob, а не только файлом до передачи.

## Review Focus

- Обязательные nested object properties сохраняются массивом required; arrays сохраняют items/type.
- Planner для 1/2/10/20 не делит на ноль, сохраняет requested size и все IDs существуют.
- Отсутствующая per-action телеметрия не превращается в вымышленную tool latency.
- При invalid schema --validate возвращает ненулевой код, а валидные zero-parameter tools допустимы.
- Итоговый PPTX и tracked site проверяются после сохранения; исторические материалы не трактуются как current.

## Task 1: Презентационные артефакты

**Files:** presentations/advisor/{README.md,SHA256SUMS,speaker-notes-v4.txt,advisor-presentation-v3-team.pptx,advisor-presentation-v4-reviewed.pptx};
source/{content-v4.json,deck-current.mjs,runtime-versions.json}; scripts/check_presentations.py; tests/test_presentations.py.
**Interfaces:** Единый content-v4.json — вход генератора; checker проверяет ZIP/XML, count, notes и SHA256SUMS.

- [ ] Воспроизвести SHA/ZIP отказ v3; тест должен фиксировать integrity и восстановление.
- [ ] Восстановить v3 из оригинала с ожидаемым hash, создать v4 с portable notes и 18-минутным порядком.
- [ ] Документировать среду и полный путь текущей сборки; старые исходники оставить архивными.
- [ ] Запустить checker и визуально проверить конечные слайды; checksum всех файлов — PASS.
- [ ] Коммит законченного изменения.

## Task 2: Канонические темы и экспериментальная спецификация

**Files:** docs/{research.md,architecture.md,hotpotqa-protocol.md,research-overview.md,model-research.md,team.md,README.md,tau-bench-review.md};
docs/{agent-architecture-detail,agent-pipeline}.{excalidraw,png}.
**Interfaces:** Каноническая таблица тем в research; contracts и preflight gates в architecture; Hotpot-specific правила в hotpotqa-protocol.

- [ ] Заменить текущую тройку предложений и определить независимые primary contrasts.
- [ ] Закрепить tagged outcomes, видимость tools, hook/provenance, метки и evaluator/statistics gates.
- [ ] Согласовать модельные приоритеты, домен, стоимость и схематические обозначения.
- [ ] Проверить Markdown, ссылки, MkDocs --strict и изображения.
- [ ] Коммит законченного изменения.

## Task 3: Tool schema generator

**Files:** .agents/skills/agent-designer/tool_schema_generator.py; tests/test_tool_schema_generator.py; requirements-tools.txt.
**Interfaces:** Existing ToolDescription/generate_tool_schema; --validate проверяет metaschema и входные examples, сообщает отказ кодом 1.

- [ ] Написать tests для required object, UUID array, items, explicit formats и invalid examples.
- [ ] Запустить их на baseline: ожидаются ошибки схем/сохранения типов и ложный успех --validate.
- [ ] Исправить type/required/items handling и независимую JSON Schema validation.
- [ ] Выполнить полный suite; sample schemas должны быть валидны, invalid input — отказ.
- [ ] Коммит законченного изменения.

## Task 4: Planner

**Files:** .agents/skills/agent-designer/agent_planner.py; tests/test_agent_planner.py.
**Interfaces:** Existing SystemRequirements/plan_system CLI; JSON enum.value; --format yaml создаёт prefix.yaml.

- [ ] Написать tests для hierarchical10, swarm20, team 1/2, enums и YAML roundtrip.
- [ ] Запустить baseline: dangling dependency, 10 вместо 20 и отсутствие YAML должны быть обнаружены.
- [ ] Исправить распределение/валидацию размера, сериализацию и YAML export.
- [ ] Выполнить полный suite и CLI-примеры.
- [ ] Коммит законченного изменения.

## Task 5: Evaluator, samples и происхождение

**Files:** .agents/skills/agent-designer/{agent_evaluator.py,README.md,SOURCE.md,LICENSE,SKILL.md};
expected_outputs/*.json; tests/test_agent_evaluator.py.
**Interfaces:** Existing generate_report; tool usage metrics берутся из actions, unknown telemetry маркируется явно.

- [ ] Написать tests штатного report и action-level counts/latency/error; запустить RED.
- [ ] Исправить поля рекомендаций и расчёт tool metrics; сверить агрегаты sample.
- [ ] Исправить README inputs и пересоздать expected_outputs текущими CLI.
- [ ] Сверить исходную лицензию закреплённой ревизии, записать локальные изменения.
- [ ] Выполнить полный suite и коммит законченного изменения.

## Task 6: Сайт и CI

**Files:** scripts/check_site.py; tests/test_site.py; .github/workflows/ci.yml; requirements-tools.txt; mkdocs.yml; site/**.
**Interfaces:** Site checker сравнивает current build с tracked site; CI запускает tools tests, PPTX checker и site check.

- [ ] Регрессионная проверка missing architecture/hotpot pages должна отказать на baseline.
- [ ] Добавить содержательную синхронизацию и проверки CI; пересобрать tracked site.
- [ ] Выполнить unittest suite, Markdown/YAML, strict build, SHA/ZIP и git diff --check.
- [ ] Проверить конечные Git blobs и коммит законченного изменения.

## Task 7: Итоговый review и интеграция

**Files:** Итоговая ветка и описание PR; прогресс исполнения — в отдельном ledger.
**Interfaces:** Reviewer получает spec/plan, diff от baseline и фактические проверки.

- [ ] Выполнить независимый whole-branch review; воспроизвести и исправить существенные замечания.
- [ ] Повторить затронутые проверки после исправлений.
- [ ] Проверить автора коммитов, чистоту дерева и актуальный родительский main.
- [ ] Подготовить ветку/PR для review команды, без автоматического слияния.
