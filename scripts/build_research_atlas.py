"""Build offline animated HTML research maps from the canonical GitMark notes.

Run with .venv/bin/python scripts/build_research_atlas.py, then mkdocs build.
Template: architecture-diagram skill v1.4.0 (MIT), vendored locally for rebuilds.
This builds documentation only; it never starts a model or an experiment.
"""

import html
import json
import re
from pathlib import Path

import markdown
from pymdownx.slugs import slugify

from research_atlas_data import PAGES, PHASES, diagram, phase_diagram

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research-atlas"
WIKI = ROOT / "docs/gitmark"
TEMPLATE = ROOT / "scripts/templates/research_atlas.html"

CSS = """
header{max-width:1540px;padding-top:24px} h1{font-size:clamp(27px,3.2vw,44px);line-height:1.15}
h1 .accent{background:none;color:var(--text)} .sub{max-width:92ch;line-height:1.6}
.atlas-nav{display:flex;gap:7px;flex-wrap:wrap;margin:18px 0 12px}
a{color:var(--c-orch);text-underline-offset:3px}.atlas-nav a{text-decoration:none;padding:7px 10px;border:1px solid var(--border);border-radius:8px;font-size:12px;color:var(--muted)}
.atlas-nav a[aria-current=page]{color:var(--text);background:var(--panel-2);border-color:var(--c-orch)}
.status-line{font-size:12px;color:var(--muted);line-height:1.6;border-left:3px solid var(--c-embed);padding:8px 13px;background:var(--panel)}
.controls{margin-top:16px}.stage{height:470px}.node{width:170px}.node .label{line-height:1.3}.node .tech{white-space:normal;line-height:1.45;max-width:155px}.node .port{font-size:10px}aside{min-width:0;max-width:100%}.panel-payload{max-width:100%;min-width:0}.panel-route{overflow-wrap:anywhere}
.atlas-content{position:relative;z-index:2;max-width:1416px;margin:32px auto;padding:0 24px 64px;line-height:1.75;overflow-wrap:anywhere;min-width:0}
.atlas-content h1{font-size:30px}.atlas-content h2{font-size:25px;margin-top:44px;color:var(--text);line-height:1.35}.atlas-content h3{margin-top:26px;line-height:1.4}
.atlas-content p,.atlas-content li{max-width:105ch;color:var(--muted)}.atlas-content strong{color:var(--text)}
.atlas-content table{border-collapse:collapse;min-width:640px;width:100%;font-size:13px;line-height:1.6}
.atlas-content th,.atlas-content td{padding:12px 14px;text-align:left;vertical-align:top;border:1px solid var(--border)}
.atlas-content th{background:var(--panel-2);color:var(--text)}.table-wrap{overflow:auto;margin:18px 0;border-radius:8px}
.atlas-content pre{background:var(--panel);border:1px solid var(--border);padding:16px;border-radius:9px;overflow:auto;font-size:12px;line-height:1.6}
.atlas-content code{font-family:var(--mono);font-size:.88em;overflow-wrap:anywhere}.atlas-content blockquote{border-left:3px solid var(--c-orch);margin-left:0;padding-left:18px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px;margin:20px 0}
.card{display:block;text-decoration:none;border:1px solid var(--border);border-radius:13px;padding:18px;background:var(--panel);color:var(--text)}
.card:hover{border-color:var(--c-orch);transform:translateY(-2px)}.card b{font-size:16px}.card small{display:block;margin-top:7px;color:var(--muted);line-height:1.6}
.card .tag{font-family:var(--mono);color:var(--c-embed);font-size:11px;display:block;margin-bottom:6px}
.guide{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:20px;color:var(--muted);font-size:12px}.guide span{border:1px solid var(--border);border-radius:8px;padding:8px 12px}
.timeline-controls{display:flex;gap:18px;align-items:center;flex-wrap:wrap;background:var(--panel);padding:18px;border:1px solid var(--border);border-radius:10px}
input,select{background:var(--panel-2);color:var(--text);border:1px solid var(--border-2);border-radius:6px;padding:7px;font:inherit}
input[type=range]{accent-color:var(--c-orch);width:210px}.timeline-scroll{overflow:auto;margin-top:20px}.timeline{min-width:800px}
.timeline-row{display:grid;grid-template-columns:235px 1fr;gap:12px;align-items:center;margin:8px 0}.timeline-name{font-size:12px;color:var(--text);text-decoration:none}
.track{height:32px;position:relative;background:repeating-linear-gradient(to right,var(--panel) 0,var(--panel) calc(100%/24 - 1px),var(--border) calc(100%/24 - 1px),var(--border) calc(100%/24));border-radius:5px}
.bar{position:absolute;top:4px;height:24px;border-radius:5px;border:1px solid var(--c-orch);background:color-mix(in srgb,var(--c-orch) 30%,var(--panel));color:var(--text);font-size:11px;display:flex;align-items:center;justify-content:center;white-space:nowrap;text-decoration:none}
.bar.is-active{border-color:var(--c-embed);background:color-mix(in srgb,var(--c-embed) 33%,var(--panel));box-shadow:0 0 14px #ffc14d25}
.bar.is-past{opacity:.55}.timeline-labels{display:grid;grid-template-columns:repeat(24,1fr);font-size:10px;color:var(--muted)}
.roadmap-detail{margin-top:18px;padding:18px;border:1px solid var(--border);border-radius:10px;background:var(--panel);min-height:100px}
.matrix{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.matrix button{text-align:left;border:1px solid var(--border);border-radius:12px;background:var(--panel);color:var(--text);padding:20px;cursor:pointer;font:inherit}
.matrix button[aria-pressed=true]{border-color:var(--c-embed)}.matrix small{display:block;color:var(--muted);margin-top:8px}.calc{display:flex;flex-wrap:wrap;gap:15px}.calc label{display:grid;gap:5px;font-size:12px}.calc-output{margin-top:15px;padding:15px;border:1px solid var(--border);border-radius:10px;color:var(--c-embed)}
.doc-source{padding:12px 16px;border:1px solid var(--border);border-radius:8px;color:var(--muted);font-size:12px}.toc ul{columns:2;column-gap:30px}.toc li{break-inside:avoid;font-size:13px}.toc a{color:var(--muted)}
footer{position:relative;z-index:2;max-width:1416px;margin:30px auto;padding:20px 24px;color:var(--muted);font-size:11px;border-top:1px solid var(--border)}
@media(max-width:1000px){.node{width:150px}.stage{min-width:700px}.canvas{overflow-x:auto}aside{min-height:300px}}
@media(max-width:720px){.atlas-content{padding:0 18px 40px}.matrix{grid-template-columns:1fr}.toc ul{columns:1}.stage{height:440px;min-width:680px}.node{width:145px}.atlas-nav a{font-size:11px;padding:6px}.atlas-content h2{font-size:23px}.atlas-content h1{font-size:27px}}
@media(prefers-reduced-motion:reduce){.card:hover{transform:none}}
"""


def esc(value):
    return html.escape(str(value), quote=True)


def md_text(filename):
    return re.sub(r"\A---\n.*?\n---\n", "", (WIKI / filename).read_text(), count=1, flags=re.S).strip()


def fix_links(rendered):
    """The delivered entry point lives at site/research-atlas/ after MkDocs build."""
    maps = {p[4]: p[0] + ".html" for p in PAGES}
    maps.update({"system-one-atlas.md": "index.html", "system-one-atlas-protocol.md": "dataset.html",
                 "system-one-atlas-evidence.md": "results.html"})

    def replace(m):
        href = html.unescape(m.group(1))
        path, sep, anchor = href.partition("#")
        if not path or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", path):
            return m.group(0)
        if path.startswith("../research-atlas/"):
            target = path.removeprefix("../research-atlas/")
        elif path.endswith(".md"):
            name = Path(path).name
            if name in maps:
                target = maps[name]
            else:
                resolved = (WIKI / path).resolve().relative_to(ROOT / "docs")
                pieces = list(resolved.with_suffix("").parts)
                if pieces[-1] == "README":
                    pieces = pieces[:-1]
                target = "../" + "/".join(pieces) + "/index.html"
        elif path.startswith("../"):
            target = path
        else:
            target = "../gitmark/" + path
        return 'href="' + esc(target + (sep + anchor if sep else "")) + '"'

    return re.sub(r'href="([^"]+)"', replace, rendered)


def render_md(content, toc=False):
    if toc:
        content = "[TOC]\n\n" + content
    rendered = markdown.markdown(content, extensions=["tables", "fenced_code", "toc", "sane_lists"],
                                 extension_configs={"toc": {"toc_depth": "2-3", "slugify": slugify(case="lower")}})
    rendered = fix_links(rendered)
    return rendered.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")


def cards(phases=False):
    if phases:
        return '<div class="cards">' + "".join(
            f'<a class="card" href="phase-{i:02}.html"><span class="tag">{p[0]} · недели {p[2]}–{p[3]}</span><b>{esc(p[1])}</b><small>{esc(p[5])}</small></a>'
            for i, p in enumerate(PHASES)) + "</div>"
    return '<div class="cards">' + "".join(
        f'<a class="card" href="{key}.html"><span class="tag">{i:02} · АНИМИРОВАННАЯ КАРТА</span><b>{esc(label)}</b><small>{esc(subtitle)}</small></a>'
        for i, (key, label, title, subtitle, doc) in enumerate(PAGES[1:], 1)) + "</div>"


def roadmap():
    rows = []
    for i, p in enumerate(PHASES):
        start, end = p[2], p[3]
        rows.append(f'<div class="timeline-row"><a class="timeline-name" href="phase-{i:02}.html">{p[0]} · {esc(p[1])}</a><div class="track"><a class="bar" data-phase="{i}" href="phase-{i:02}.html" style="left:{(start-1)/24*100:.4f}%;width:{(end-start+1)/24*100:.4f}%">{start}–{end}</a></div></div>')
    payload = json.dumps(PHASES, ensure_ascii=False)
    return f"""<h2>Интерактивный roadmap</h2><p>Сценарий сроков: работа ещё запланирована. Нажмите полосу этапа для зависимостей, затем откройте его рецепт. Недели 23–24 — резерв.</p>
<div class="timeline-controls"><label>Начало <input id="roadStart" type="date" value="2026-10-19"></label><label>Неделя сценария <input id="roadWeek" type="range" min="1" max="24" value="1"></label><strong id="roadDate"></strong></div>
<div class="timeline-scroll"><div class="timeline"><div class="timeline-row"><span>Этап / недели от начала</span><div class="timeline-labels">{''.join(f'<span>{i}</span>' for i in range(1,25))}</div></div>{''.join(rows)}</div></div>
<div class="roadmap-detail" id="roadDetail" aria-live="polite"></div>
<script>(()=>{{const phases={payload};const start=document.getElementById('roadStart'),week=document.getElementById('roadWeek'),date=document.getElementById('roadDate'),detail=document.getElementById('roadDetail');let chosen=0;
function draw(){{if(!start.value)return;const w=Number(week.value),d=new Date(start.value+'T12:00:00');d.setDate(d.getDate()+7*(w-1));date.textContent='Неделя '+w+' · '+d.toLocaleDateString('ru-RU');document.querySelectorAll('.bar').forEach(b=>{{const p=phases[Number(b.dataset.phase)];b.classList.toggle('is-active',w>=p[2]&&w<=p[3]);b.classList.toggle('is-past',w>p[3]);}});show(chosen);}}
function show(i){{chosen=i;const p=phases[i];detail.replaceChildren();const h=document.createElement('strong');h.textContent=p[0]+' · '+p[1];detail.append(h);for(const text of ['Зависимости: '+(p[4].join(', ')||'поручение и контекст'),'Артефакт: '+p[5],'Критерий: '+p[6],'Статус: запланировано. Подсветка отражает выбранную неделю сценария.']){{const el=document.createElement('p');el.textContent=text;detail.append(el);}}const a=document.createElement('a');a.href='phase-'+String(i).padStart(2,'0')+'.html';a.textContent='Открыть подробный план и анимацию →';detail.append(a);}}
document.querySelectorAll('.bar').forEach(b=>b.addEventListener('click',e=>{{e.preventDefault();show(Number(b.dataset.phase));}}));start.addEventListener('change',draw);week.addEventListener('input',draw);draw();}})();</script>"""


def matrix():
    cases = [("CE + direct teacher", "Базовый контроль: teacher выдаёт решение без генерируемого rationale. Student обучается CE и выдаёт p напрямую."),
             ("Brier + direct teacher", "Те же train pairs и targets; меняется objective. Проверить, что это Brier-only, а не CE + λBrier."),
             ("CE + reasoning teacher", "Teacher рассуждает только при подготовке targets. Их качество проверяется независимо; student не получает rationale."),
             ("Brier + reasoning teacher", "Позволяет проверить взаимодействие teacher mode и objective при том же compact student. Цена teacher включается в адаптацию.")]
    buttons = ''.join(f'<button data-case="{i}" aria-pressed="{str(i==0).lower()}">{esc(t)}<small>Student inference: прямое p(useful), без генерации reasoning</small></button>' for i,(t,d) in enumerate(cases))
    return '<h2>Матрица дополнительных опытов 2 × 2</h2><p>Основной опыт CE/Brier проводится на одном проверенном наборе. Эта матрица добавляет источник targets как независимый фактор; она ещё не выполнена.</p><div class="matrix">'+buttons+'</div><div class="roadmap-detail" id="matrixDetail" aria-live="polite"></div><script>(()=>{const cases='+json.dumps(cases, ensure_ascii=False)+';const detail=document.getElementById("matrixDetail");document.querySelectorAll("[data-case]").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll("[data-case]").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));detail.textContent=cases[Number(b.dataset.case)][1];}));detail.textContent=cases[0][1];})();</script>'


def calculator():
    return """<h2>Калькулятор окупаемости — сценарий, не результат</h2><p>Все поля изначально пусты. Введите измеренные или явно предполагаемые суммы в одной валюте; результат применим только при выполненном ограничении качества.</p>
<div class="calc"><label>Цена адаптации <input id="adaptCost" type="number" min="0" step="any" placeholder="нет измерения"></label><label>Цена baseline / эпизод <input id="baseCost" type="number" min="0" step="any" placeholder="нет измерения"></label><label>Цена adapted / эпизод <input id="newCost" type="number" min="0" step="any" placeholder="нет измерения"></label><label>Ограничение качества <select id="qualityGate"><option value="unknown">ещё не проверено</option><option value="yes">выполнено по протоколу</option><option value="no">не выполнено</option></select></label></div><div class="calc-output" id="calcResult" aria-live="polite">Нет данных для расчёта.</div>
<script>(()=>{const ids=['adaptCost','baseCost','newCost'],out=document.getElementById('calcResult'),gate=document.getElementById('qualityGate');function calc(){const fields=ids.map(i=>document.getElementById(i));if(fields.some(x=>x.value==='')){out.textContent='Нет данных для расчёта.';return;}const [a,b,c]=fields.map(x=>Number(x.value));if([a,b,c].some(x=>!Number.isFinite(x)||x<0)){out.textContent='Нужны конечные неотрицательные значения.';return;}if(gate.value!=='yes'){out.textContent='Вывод о выгоде недопустим: ограничение качества '+(gate.value==='no'?'не выполнено.':'ещё не проверено.');return;}const delta=b-c;out.textContent=delta<=0?'Экономия на эпизод неположительна: конечной окупаемости нет.':'Сценарная граница N* = '+(a/delta).toLocaleString('ru-RU',{maximumFractionDigits:1})+' эпизодов (до целого: '+Math.ceil(a/delta).toLocaleString('ru-RU')+'). Не включает неопределённость введённых оценок.';}ids.forEach(i=>document.getElementById(i).addEventListener('input',calc));gate.addEventListener('change',calc);})();</script>"""


def body_content(key, doc, phase=None):
    source = md_text(doc)
    extras = '<div class="guide"><span>▶ Пуск / пауза</span><span>← → Переход по шагам</span><span>Нажмите узел для пояснения</span><span>Сценарии — над схемой</span><span>Тема: T · экран: F</span></div>'
    if phase is not None:
        sections = re.split(r"(?=^## P\d+\.)", source, flags=re.M)
        source = next(s for s in sections if s.startswith(f"## P{phase}."))
        extras += '<p><a href="execution.html">← Все этапы</a> · <a href="roadmap.html">Roadmap</a></p>'
    elif key == "index":
        extras += '<h2>Открыть отдельную карту</h2>' + cards()
    elif key == "execution":
        extras += '<h2>Каждый этап — отдельная страница</h2>' + cards(True)
    elif key == "roadmap":
        extras += roadmap() + cards(True)
    elif key == "training":
        extras += matrix()
    elif key == "results":
        main = md_text("system-one-atlas.md")
        result_section = main.split("## Реестр результатов на 19.10.2026",1)[1]
        extras += render_md("## Наши результаты: статус\n" + result_section) + calculator()
    elif key == "experiments":
        extras += calculator()
    extras += f'<div class="doc-source">Подробный текст ниже встроен из <code>docs/gitmark/{esc(doc)}</code>. Канонические решения — в wiki; схема является объясняющим представлением.</div>'
    return '<section class="atlas-content">' + extras + render_md(source, toc=phase is None) + '</section>'


def build(key, title, subtitle, doc, nodes, flows, phase=None):
    template = TEMPLATE.read_text()
    template = re.sub(r"<!--.*?-->", "", template, flags=re.S)
    template = re.sub(r'<link[^>]+>', '', template)
    template = re.sub(r'<noscript>\s*</noscript>', '', template)
    template = template.replace('<html lang="en">', '<html lang="ru">')
    template = re.sub(r'<title>.*?</title>', '<title>'+esc(title)+' · Атлас ВКР</title>', template)
    template = template.replace('{{PROJECT_LABEL}}', 'НГТУ · ФПМИ · ВКР 2027')
    template = template.replace('{{SYSTEM_NAME}}', esc(title)).replace('{{TAGLINE}}', '')
    template = template.replace('{{SUBTITLE}}', esc(subtitle))
    template = template.replace('{{PLACEHOLDER}}', 'template-placeholder')
    template = template.replace('style-src \'unsafe-inline\' https://fonts.googleapis.com; font-src https://fonts.gstatic.com;', "style-src 'unsafe-inline'; font-src 'none';")
    template = template.replace('</style>', CSS+'\n</style>', 1)
    nav = '<nav class="atlas-nav" aria-label="Карты исследования">'+''.join(f'<a href="{p[0]}.html"'+(' aria-current="page"' if p[0]==key else '')+'>'+esc(p[1])+'</a>' for p in PAGES)+'</nav>'
    template = template.replace('</header>', nav+'<div class="status-line">Срез 19.10.2026 · Проект исследования. Новые модельные эксперименты не запускались. Значения в payload — примеры контрактов или отмеченные стартовые предложения.</div></header>',1)
    template = re.sub(r'<div class="modepick".*?</div>', '', template, count=1, flags=re.S)
    roles = [('user','Вопрос / результат'),('orch','Контракт / процесс'),('compute','Модель / прогон'),('embed','Обучение / проверка'),('vector','Данные / источник'),('seed','Ограничение / аудит')]
    legend = '<div class="legend" role="group" aria-label="Обозначения">'+''.join(f'<span class="item"><span class="swatch" style="background:var(--c-{r})"></span> {l}</span>' for r,l in roles)+'</div>'
    template = re.sub(r'<div class="legend".*?</div>', legend, template, count=1, flags=re.S)
    tabs = '<nav class="flowtabs" aria-label="Сценарии">'+''.join(f'<button class="flowtab" data-flow="{k}" aria-pressed="{str(i==0).lower()}"><span class="num">{i+1}</span> {esc(f["name"])}</button>' for i,(k,f) in enumerate(flows.items()))+'</nav>'
    template = re.sub(r'<nav class="flowtabs".*?</nav>', tabs, template, count=1, flags=re.S)
    template = re.sub(r'<p class="scenario-note">.*?</p>', '<p class="scenario-note"><kbd>Space</kbd> пуск / пауза · <kbd>←</kbd>/<kbd>→</kbd> шаг · <kbd>1</kbd>–<kbd id="kbFlowMax">3</kbd> сценарий · <kbd>T</kbd> тема · <kbd>F</kbd> экран · перетащите узел · <button type="button" class="linkbtn" id="btnShortcuts" aria-pressed="true">клавиши вкл.</button></p>', template, count=1, flags=re.S)
    positions = [(2,8),(38,8),(74,8),(74,66),(38,66),(2,66)]
    nodes_html = ''
    for i,n in enumerate(nodes):
        x,y = positions[i]
        nodes_html += f'<div class="node" data-role="{n["role"]}" data-id="{n["id"]}" style="left:{x}%;top:{y}%;"><div class="icon">{i+1:02}</div><div class="label">{esc(n["label"])}</div><div class="tech">{esc(n["tech"])}</div><div class="port">{esc(n["id"])}</div><span class="step-badge">·</span></div>\n'
    template = re.sub(r'(<div class="stage" id="stage">).*?(<svg class="wires")', lambda m: m[1]+nodes_html+m[2], template, count=1, flags=re.S)
    start = template.index('const flows = {')
    end = template.index('/* ─── state', start)
    serialized = json.dumps(flows, ensure_ascii=False, indent=2).replace('</','<\\/')
    template = template[:start]+'const flows = '+serialized+';\n\n'+template[end:]
    first = next(iter(flows))
    template = template.replace('flow: "flow_a"', f'flow: "{first}"').replace('fallbackFlow: "flow_a"', f'fallbackFlow: "{first}"')
    template = template.replace('stepMs: 1800', 'stepMs: 4200')
    translations = {'STEP <strong':'ШАГ <strong', 'Pipeline ·':'Сценарий ·', '&larr; Previous':'&larr; Назад', 'Next &rarr;':'Далее &rarr;', 'Select a flow and press Play to see details.':'Выберите сценарий и нажмите пуск.', 'This diagram is interactive and needs JavaScript. Enable it, or read the companion <code>architecture.md</code> for the same content as text.':'Для анимации нужен JavaScript. Подробный текст доступен ниже без JavaScript.', 'Shortcuts on':'Клавиши вкл.', 'Shortcuts off':'Клавиши выкл.', 'shortcuts on':'клавиши вкл.', 'shortcuts off':'клавиши выкл.', 'Previous step':'Предыдущий шаг', 'Next step':'Следующий шаг', 'Play/Pause':'Пуск/пауза', 'Toggle light/dark theme':'Переключить тему', 'Reset node positions':'Сбросить позиции', 'Reset layout':'Сбросить схему', 'Fullscreen':'На весь экран', 'Current step details':'Описание шага', 'Architecture diagram':'Схема исследования', 'Playback controls':'Воспроизведение'}
    translations.pop('Fullscreen')  # Do not rewrite JS identifiers such as btnFullscreen.
    for a,b in translations.items():
        template = template.replace(a,b)
    template = template.replace('title="Fullscreen (F)"', 'title="На весь экран (F)"').replace('aria-label="Fullscreen"', 'aria-label="На весь экран"')
    extra = body_content(key,doc,phase)
    template = template.replace('</body>', extra+'<footer>Атлас подготовлен как исследовательский план с AI-помощью · 19.10.2026. Схемы: architecture-diagram v1.4.0, MIT; содержательные документы — GitMark проекта. Страницы не выполняют запросы к моделям и не отправляют данные.</footer></body>')
    template = template.replace('window.archValidate = validateDiagram;', 'window.archValidate = validateDiagram;')
    # No template placeholders may remain in visible authored regions.
    if re.search(r'\{\{[A-Z_]+\}\}', re.sub(r'/\*.*?\*/', '', template, flags=re.S)):
        raise ValueError(f'Unresolved template placeholders: {key}: ' + str(re.findall(r'\{\{[A-Z_]+\}\}', re.sub(r'/\*.*?\*/', '', template, flags=re.S))))
    (OUT / f'{key}.html').write_text(template)


def main():
    OUT.mkdir(exist_ok=True)
    for key, label, title, subtitle, doc in PAGES:
        nodes, flows = diagram(key)
        build(key,title,subtitle,doc,nodes,flows)
    for i,p in enumerate(PHASES):
        nodes,flows=phase_diagram(p)
        build(f'phase-{i:02}',p[0]+' · '+p[1],p[5]+'. '+p[6]+'.', 'system-one-atlas-execution.md',nodes,flows,phase=i)
    print(f'Built {len(PAGES)+len(PHASES)} standalone HTML pages in {OUT}')


if __name__ == '__main__':
    main()
