# Презентация для научного руководителя

- [Текущая версия v4, 16 слайдов](advisor-presentation-v4-reviewed.pptx).
  Основной доклад — 18 минут, слайды 1–14; резерв — 15–16.
  Три предлагаемых исследования и границы личного вклада стоят перед заключением.
- [Заметки к v4 с хронометражем и источниками](speaker-notes-v4.txt).

V4 подготовлена 09.10.2026 по результатам полного аудита. Темы, назначения
авторам и пригодность стендов остаются предложениями для обсуждения и пилота.
Презентация не подтверждает согласование руководителем, работающий агент
или экспериментальные результаты. Канонические постановка и состояние —
в [исследовании](../../docs/research.md) и [wiki](../../docs/README.md).

## Сборка текущей версии

Единый вход: `source/content-v4.json`; генератор: `source/deck-current.mjs`.
Версии и шрифт: `source/runtime-versions.json`. Нужны Artifact Tool **2.8.85**,
Node.js, Python ≥3.12, шрифт **DejaVu Sans** и валидаторы презентаций из среды Codex.
V4 сохраняет цвета, обложку и композицию v2; шрифт заменён на доступный DejaVu Sans.
Это команда для указанной среды, а не универсальная сборка на любой машине:

```sh
export PRESENTATIONS_SKILL_DIR=/root/.codex/skills/builtins/presentations
# CODEX_PRIMARY_RUNTIME_NODE, CODEX_PRIMARY_RUNTIME_NODE_MODULES и
# CODEX_PRIMARY_RUNTIME_PYTHON предоставляет среда Codex.
DECK_WORK_DIR=artifacts/advisor-current \
  "$CODEX_PRIMARY_RUNTIME_NODE" presentations/advisor/source/deck-current.mjs
```

Результат — `artifacts/advisor-current/output/`; диагностические данные и превью —
`.build/` рядом. Для повторной сборки укажите новый `DECK_WORK_DIR`:
финализатор сохраняет проверенный результат без перезаписи.
После визуального просмотра копируйте PPTX и заметки в этот каталог,
обновляйте [SHA256SUMS](SHA256SUMS), затем запускайте из корня:

```sh
python scripts/check_presentations.py
```

Checker проверяет сохранённые ZIP/XML, внутренние ссылки, число слайдов,
portable notes, хронометраж источника и полный набор SHA-256. Он не заменяет
визуальный просмотр. V4 проверена импортом и рендером Artifact Tool,
структурным и геометрическим валидаторами; в PowerPoint не открывалась.

## Архив

- [V3, 16 слайдов](advisor-presentation-v3-team.pptx) и
  [её заметки](speaker-notes-v3.txt): оригинал от 02.10.2026,
  добавлен в Git 07.10.2026. Повреждённый Git-файл восстановлен 09.10.2026
  из полного оригинала с исходным SHA-256. Его старый хронометраж не относится к v4.
- [V2, 14 слайдов](advisor-presentation-v2-final.pptx) и
  [заметки](speaker-notes-v2.txt): 18 минут для основной части 1–12.
- [V1, 19 слайдов](advisor-research-proposal.pptx) и [заметки](speaker-notes.txt).

Старые `source/deck.mjs`, `deck-v2.mjs`, `deck-team-slides.mjs`,
`merge-team-slides.py` и их JSON сохранены как исторические исходники.
Они содержат пути прежней среды и не являются текущим способом сборки.
Обложка создана ImageGen 02.10.2026; это оформление, а не научная схема.
