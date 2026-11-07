"""Render the two-model System One architecture overview as SVG and PNG.

Run: python3 scripts/draw_system_one_architecture.py
Detailed proposed contract: docs/gitmark/architecture.md#context-contract-v0.
The diagram is a design, not an implemented or empirically validated agent.
"""

import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="diplom-mpl-"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
W, H = 3000, 1910

C = {
    "bg": "#0A1020", "surface": "#101B2D", "runtime": "#16172B",
    "white": "#F8FAFF", "muted": "#A8B6CB", "outline": "#354661",
    "blue": "#65B5FF", "blue_dark": "#182B42",
    "violet": "#AF90FF", "violet_dark": "#281F46",
    "teal": "#4DDBBD", "teal_dark": "#173735",
    "amber": "#FFC46B", "amber_dark": "#41321E",
}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "svg.fonttype": "none",
    "figure.facecolor": C["bg"], "savefig.facecolor": C["bg"],
})
fig, ax = plt.subplots(figsize=(W / 120, H / 120), dpi=120)
fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
ax.set_xlim(0, W)
ax.set_ylim(H, 0)
ax.axis("off")


def txt(x, y, words, size=25, color="white", weight="normal", *, ha="left", va="top"):
    return ax.text(x, y, words, ha=ha, va=va, color=C.get(color, color),
                   fontsize=size, weight=weight, linespacing=1.32, zorder=6)


def box(x, y, w, h, *, fill="surface", edge="outline", r=23, lw=2.3):
    shape = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                           facecolor=C.get(fill, fill), edgecolor=C.get(edge, edge),
                           linewidth=lw, zorder=1)
    ax.add_patch(shape)
    return shape


def arrow(a, b, color, *, dashed=False, width=3.7, head=25):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=head,
                                 linewidth=width, linestyle="--" if dashed else "-",
                                 color=C[color], zorder=5, shrinkA=6, shrinkB=6))


def path(points, color, *, dashed=False, width=3.4):
    xs, ys = zip(*points)
    ax.plot(xs, ys, color=C[color], linewidth=width,
            linestyle="--" if dashed else "-", zorder=4)
    arrow(points[-2], points[-1], color, dashed=dashed, width=width)


def section(index, name, y, color, aside):
    box(145, y, 54, 44, fill=color, edge=color, r=12, lw=0)
    txt(172, y + 22, index, 20, "bg", "bold", ha="center", va="center")
    txt(215, y + 2, name, 29, "white", "bold")
    txt(2850, y + 8, aside, 18, "muted", ha="right")


def native(x, w, badge, title, desc):
    box(x, 348, w, 174, fill="blue_dark", edge="blue", r=26, lw=2.8)
    box(x + 24, 372, 122, 32, fill="blue", edge="blue", r=10, lw=0)
    txt(x + 85, 388, badge, 15, "bg", "bold", ha="center", va="center")
    txt(x + 28, 420, title, 31, "white", "bold")
    txt(x + 30, 474, desc, 21, "muted")


# The single-sentence answer comes before the details.
txt(100, 45, "Два System One. Три самостоятельные темы.", 49, "white", "bold")
txt(103, 126, "C выбирает KB; R оценивает риск принятия; основная LLM отвечает и вызывает tools.", 23, "muted")
box(2470, 112, 430, 60, fill="amber_dark", edge="amber", r=16, lw=1.7)
txt(2685, 142, "АРХИТЕКТУРА · ПРОЕКТ", 18, "amber", "bold", ha="center", va="center")

# Unmodified native environment.
box(92, 222, 2816, 350, fill="surface", edge="outline", r=30)
section("01", "ШТАТНЫЙ τ-KNOWLEDGE", 259, "blue", "policy · tools · KB · evaluator не меняем")
native(145, 590, "USER", "Пользователь", "Симулятор / сообщения")
native(1030, 660, "AGENT", "Основная LLM", "Ответ + native tool calls")
native(2070, 790, "TOOLS", "Поиск и операции", "KB_search → BM25 · банковские tools")
arrow((743, 435), (1020, 435), "blue")
arrow((1700, 435), (2060, 435), "blue")

# Agent-side boundary. Only already observed information enters either model.
box(92, 652, 2816, 838, fill="runtime", edge="violet_dark", r=30, lw=2.5)
section("02", "AGENT-SIDE КОНТРОЛЛЕР", 685, "violet", "один snapshot · одинаковый Bₜ · без скрытых данных")
box(145, 815, 505, 480, fill="surface", edge="teal", r=27, lw=2.8)
txt(176, 847, "НАБЛЮДЕНИЯ", 29, "white", "bold")
txt(177, 898, "RAW журнал сохранён", 20, "teal", "bold")
box(176, 959, 443, 106, fill="teal_dark", edge="teal_dark", r=16, lw=0)
txt(198, 977, "STATE", 22, "teal", "bold")
txt(198, 1014, "диалог + факты tools", 20)
box(176, 1091, 443, 106, fill="teal_dark", edge="teal_dark", r=16, lw=0)
txt(198, 1109, "EVIDENCE POOL", 21, "teal", "bold")
txt(198, 1147, "уже виденный KB", 20)
txt(177, 1245, "Без чтения корпуса", 18, "muted")

# Topic 2: one model scores candidates; a separate deterministic packer selects IDs.
box(735, 815, 455, 480, fill="violet_dark", edge="violet", r=27, lw=2.8)
txt(764, 849, "SYSTEM ONE C", 26, "white", "bold")
txt(766, 896, "ТЕМА 2 · ОТБОР", 19, "violet", "bold")
box(766, 959, 393, 101, fill="runtime", edge="outline", r=15, lw=1.6)
txt(786, 978, "МОДЕЛЬ", 20, "violet", "bold")
txt(786, 1014, "pᵢ: полезность KB", 19)
arrow((961, 1067), (961, 1095), "violet", width=2.8, head=18)
box(766, 1107, 393, 101, fill="runtime", edge="outline", r=15, lw=1.6)
txt(786, 1126, "PACKER", 20, "violet", "bold")
txt(786, 1161, "набор ≤ Bₜ", 20)
txt(766, 1245, "длина · дубли · бюджет", 17, "muted")

# Topic 1 has its OWN learned System One decision, not a re-labelled threshold.
box(1275, 815, 455, 480, fill="violet_dark", edge="amber", r=27, lw=2.8)
txt(1304, 849, "SYSTEM ONE R", 26, "white", "bold")
txt(1306, 896, "ТЕМА 1 · РИСК НАБОРА", 18, "amber", "bold")
box(1306, 959, 393, 115, fill="runtime", edge="outline", r=15, lw=1.6)
txt(1326, 978, "ВХОД МОДЕЛИ", 19, "amber", "bold")
txt(1326, 1014, "state + набор", 18)
txt(1326, 1042, "пропуски по пулу", 18)
box(1306, 1101, 393, 107, fill="runtime", edge="outline", r=15, lw=1.6)
txt(1326, 1119, "ВЫХОД МОДЕЛИ", 19, "amber", "bold")
txt(1326, 1155, "qₜ: риск accept", 19)
txt(1306, 1245, "Не среднее оценок pᵢ", 18, "muted")

# The router is a separately calibrated policy on top of the second model.
ax.add_patch(Polygon([(1975, 815), (2162, 1036), (1975, 1257), (1788, 1036)],
                     closed=True, facecolor=C["violet_dark"],
                     edgecolor=C["amber"], linewidth=3, zorder=2))
txt(1975, 950, "РОУТЕР", 26, "white", "bold", ha="center")
txt(1975, 1005, "qₜ + цена", 22, "amber", ha="center")
txt(1975, 1052, "accept / defer", 20, "muted", ha="center")
box(1800, 1310, 350, 132, fill="amber_dark", edge="amber", r=19, lw=2.5)
txt(1830, 1330, "LLM-СЕЛЕКТОР", 20, "amber", "bold")
txt(1830, 1375, "тот же snapshot", 19)

# Both paths produce one KB block, never a second native retrieval result.
box(2320, 820, 540, 201, fill="teal_dark", edge="teal", r=25, lw=2.8)
txt(2351, 852, "КОНТЕКСТ  Bₜ", 29, "white", "bold")
txt(2351, 907, "единый бюджет", 22, "teal")
txt(2351, 948, "accept / ID от LLM", 20, "muted")
box(2320, 1135, 540, 170, fill="teal_dark", edge="teal", r=25, lw=2.8)
txt(2351, 1168, "MODEL VIEW", 28, "white", "bold")
txt(2351, 1219, "история + KB один раз", 19, "muted")

arrow((655, 1036), (728, 1036), "teal")
arrow((1196, 1036), (1269, 1036), "violet")
arrow((1736, 1036), (1781, 1036), "amber")
path([(2168, 1036), (2245, 1036), (2245, 906), (2311, 906)], "teal")
txt(2175, 993, "ACCEPT", 16, "teal", "bold")
arrow((1975, 1262), (1975, 1303), "amber", head=19)
path([(2156, 1374), (2265, 1374), (2265, 986), (2312, 986)], "amber")
txt(2159, 1338, "DEFER", 17, "amber", "bold")
arrow((2590, 1027), (2590, 1128), "teal")

# Tool-observation feedback and derived-view return use thin outer routes.
path([(2460, 527), (2460, 602), (45, 602), (45, 1058), (136, 1058)],
     "blue", dashed=True, width=2.6)
path([(2865, 1216), (2940, 1216), (2940, 318), (1360, 318), (1360, 341)],
     "teal", dashed=True, width=2.6)
txt(153, 609, "НАБЛЮДАЕМЫЕ ОТВЕТЫ TOOLS", 17, "blue", "bold")

# Three separate research contributions; arrows would falsely imply a pipeline here.
box(92, 1530, 2816, 245, fill="surface", edge="outline", r=30)
section("03", "ТРИ НЕЗАВИСИМЫХ ИССЛЕДОВАНИЯ", 1556, "blue",
        "все сравнения — с исходным агентом и дешёвыми контролями")
for x, title, desc, color in (
    (151, "1 · МАРШРУТИЗАЦИЯ", "модель риска + калибровка", "amber"),
    (846, "2 · ОТБОР", "scoring + packer + бюджет", "violet"),
    (1541, "3 · АДАПТАЦИЯ", "frozen ↔ adapted C или R", "teal"),
    (2230, "ОБЩИЙ ТЕСТ", "успех · стоимость · задержка", "blue"),
):
    txt(x, 1653, title, 23, color, "bold")
    txt(x, 1696, desc, 19, "white")

box(92, 1808, 2816, 63, fill="#212336", edge="#212336", r=16, lw=0)
txt(1500, 1840,
    "РАЗНЫЕ ЦЕЛИ МОДЕЛЕЙ  ·  общие state / кандидаты / Bₜ  ·  raw ≠ model view  ·  ошибка / overflow ≠ defer",
    19, "muted", "bold", ha="center", va="center")

for p, kind in ((OUT / "system-one-context-architecture.svg", "svg"),
                (OUT / "system-one-context-architecture.png", "png")):
    fig.savefig(p, format=kind, dpi=120, bbox_inches=None, pad_inches=0)
    print(f"Saved {p} ({p.stat().st_size:,} bytes)")
plt.close(fig)
