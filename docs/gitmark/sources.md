---
node_type: reference
title: Научные источники
service: _platform
status: active
updated: 2026-10-25
links:
  relates_to: [docs/gitmark/README.md]
---

# Научные источники

Сверено с первичными страницами **30.09.2026**. Здесь указана роль работы в нашем исследовании, а не подтверждение её результатов собственным экспериментом. Подробный разбор стенда — в [обзоре τ-bench](tau-bench-review.md), границы постановки — в [исследовании](research.md).

| Работа и первичный источник | Год и статус | Зачем используем | Разбор |
| --- | --- | --- | --- |
| Yao, Shinn, Razavi, Narasimhan. [τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains](https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html) | 2025; статья в proceedings ICLR 2025 | Исходная оценка сервисного агента с инструментами и симуляцией пользователя. | [Состав и оценивание](tau-bench-review.md#семейство-и-состав) |
| Barres, Dong, Ray, Si, Narasimhan. [τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment](https://arxiv.org/abs/2506.07982) | 2025; [в программе ICML 2026](https://icml.cc/Downloads/2026), препринт arXiv v1 | Расширение семейства: взаимодействие агента и пользователя с общей средой. | [Семейство](tau-bench-review.md#семейство-и-состав) |
| Shi, Zytek, Razavi, Narasimhan, Barres. [τ-Knowledge: Evaluating Conversational Agents over Unstructured Knowledge](https://arxiv.org/abs/2603.04370v1) | 2026; [в программе ICML 2026](https://icml.cc/Downloads/2026), препринт arXiv v1 | Источник для выбранного основного стенда `banking_knowledge` с поиском по базе знаний. | [Корпус и ограничения](tau-bench-review.md#семейство-и-состав) |
| Kapoor и соавт. [Holistic Agent Leaderboard: The Missing Infrastructure for AI Agent Evaluation](https://arxiv.org/abs/2510.11977) | 2026; [статья ICLR 2026](https://hal.cs.princeton.edu/), препринт arXiv v1 | Внешняя оценка агентов с учётом затрат; HAL включает TAU-bench Airline. | [Научный статус](tau-bench-review.md#научный-статус) |
| Cuadron, Yu, Liu, Gupta. [SABER: Small Actions, Big Errors — Safeguarding Mutating Steps in LLM Agents](https://arxiv.org/abs/2512.07850v1) | 2025; препринт arXiv v1, статус рецензирования не подтверждён | Анализ ошибок заданий τ-bench и значимости действий, меняющих состояние. | [Научный статус](tau-bench-review.md#научный-статус) |
| Liu. [Evaluating System One Models for Agent Security Decisions: Reliability, Calibration, and Selective Automation](https://arxiv.org/abs/2609.33401v3) | 2026; arXiv v3 от 03.10.2026, перепроверено 11.10.2026; статус рецензирования не подтверждён | Уже включает калибровку, фиксированные пороги allow/block/escalate и независимую проверку. Калибровка System One вообще не является незанятой нишей. | [Обзор RLCD и границы новизны](rlcd-review.md) |

## RLCD и калиброванные решения

Дополнение от **11.10.2026**. Полный разбор, дополнительная литература, ограничения
новизны и предлагаемые эксперименты — в [обзоре RLCD](rlcd-review.md).

| Работа и первичный источник | Версия и статус | Роль и граница вывода |
| --- | --- | --- |
| Gao, Wang. [OpenJev-RLCD: A Working RLCD Implementation](https://arxiv.org/abs/2609.38850v1) | 30.09.2026, arXiv v1; рецензирование не подтверждено | Proper score после сгенерированного rationale, двухстадийное обучение. Не раскрытие закрытого Jev и не доказательство одношагового inference. |
| Deka. [From Retrieval to Typed Decisions: Calibrated System One Models from Biomedical Sentence Encoders](https://arxiv.org/abs/2610.02486v1) | 01.10.2026, arXiv v1; рецензирование не подтверждено | SBERT2S1: контролируемое сравнение CE и рецепта Laya с шумом логитов; отрицательный результат для конкретного estimator, не опровержение reasoning-варианта OpenJev. |
| Yu, Xu, Weston, Kulikov. [Distilling System 2 into System 1](https://arxiv.org/abs/2407.06023v3) | 2024, проверен arXiv v3 от 24.07.2024 | Дистилляция ответов без промежуточных рассуждений; сложное математическое reasoning не всегда переносится. Не доказательство сохранения калибровки. |
| Guo, Pleiss, Sun, Weinberger. [On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html) | ICML 2017, PMLR 70:1321–1330 | Temperature scaling как обязательный дешёвый контроль; не гарантия при произвольном сдвиге данных. |

## Обучение и дообучение System One

Подборка проверена **19.10.2026** после сообщения инициатора о поддержке
направления руководителем. [Карточки восьми работ, порядок чтения и предлагаемые
сравнения](system-one-training-review.md) дополняют обзор RLCD выше.
Это результаты авторов и основания для выбора опыта, не наши измерения.

| Работа и первичный источник | Версия / публикация | Роль в исследовании |
| --- | --- | --- |
| Tunstall и соавт. [Efficient Few-Shot Learning Without Prompts](https://arxiv.org/abs/2209.11055v1) | Проверен arXiv v1, 22.09.2022 | SetFit: дообучение sentence encoder при малом числе меток; дешёвый обучаемый контроль. |
| Stepanov и соавт. [GLiClass: Generalist Lightweight Model for Sequence Classification Tasks](https://arxiv.org/abs/2508.07662v1) | Проверен arXiv v1, 11.08.2025 | Компактная классификация с описаниями меток; источник альтернативы типизированным оценщикам, не гарантия калибровки. |
| Ren и соавт. [RocketQAv2: A Joint Training Method for Dense Passage Retrieval and Passage Re-ranking](https://aclanthology.org/2021.emnlp-main.224/) | EMNLP 2021, pp. 2825–2835 | Listwise distillation для поиска/ранжирования. Распределение по кандидатам не равно вероятности достаточности выбранного контекста. |
| Dettmers и соавт. [QLoRA: Efficient Finetuning of Quantized LLMs](https://arxiv.org/abs/2305.14314v1) | Проверен arXiv v1, 23.05.2023 | Способ уменьшения памяти адаптации decoder-моделей; не отдельная цель обучения System One и не замер на нашем Mac. |

Три наиболее близкие работы — SBERT2S1, OpenJev-RLCD и *Distilling System 2
into System 1* — уже перечислены в предыдущем разделе; Guo и соавт. дают
контроль post-hoc калибровки. Их роль в новом сравнении уточнена в подборке.

## Другие типы источников

**25.10.2026:** по поручению инициатора подготовлены
[полные неофициальные русские переводы OpenJev-RLCD и SBERT2S1](../translations/README.md)
закреплённых версий v1, включая приложения, формулы и числовые таблицы.
Оригиналы имеют лицензию CC BY 4.0; авторы переводы не проверяли.
[Происхождение, расходы и контроль перевода](../translations/translation-record.md)
зафиксированы отдельно. Для научного цитирования используются оригиналы выше.

[Карточки KEV и Laya, исходный код и документация поставщиков](model-research.md) нужны для проверки конкретных моделей и версий, но сами по себе не подтверждают статус рецензируемой статьи. Код и документация τ-bench перечислены в [подробном обзоре стенда](tau-bench-review.md); заявления поставщиков и численные результаты авторов не являются нашими измерениями.
