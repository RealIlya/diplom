import fs from 'node:fs/promises';
import path from 'node:path';
const build=path.resolve(process.env.TEAM_BUILD_DIR ?? 'artifacts/team-slides');
await fs.mkdir(build,{recursive:true});
import {Presentation,PresentationFile} from '@oai/artifact-tool';
const p=Presentation.create({slideSize:{width:1280,height:720}});
const font='Helvetica Neue';
const c={paper:'#F4F1EA',ink:'#182B3B',teal:'#236F6A',muted:'#5D686E'};
function text(s,v,x,y,w,h,size=28,color=c.ink,bold=false){const o=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});o.text=v;o.text.style={typeface:font,fontSize:size,color,bold,autoFit:'none',wrap:'square',insets:{left:0,right:0,top:0,bottom:0}};}
const slides=[
 {title:'Три самостоятельных исследования',rows:[
 ['Направление','Исследовательский вопрос','Метод и личный результат'],
 ['1. Маршрутизация','Когда доверять компактной модели,\nа когда передавать решение LLM?','Калибровка и пороги\nВыбор метода с ограничением\nна потерю качества'],
 ['2. Отбор контекста','Какие документы передавать агенту\nпри ограничении бюджета токенов?','Выбор подмножества документов\nМетод отбора и зависимость\nкачества от бюджета'],
 ['3. Адаптация модели','Как объём разметки влияет\nна качество и перенос модели?','Дообучение и кривые обучения\nУсловия переноса\nи окупаемость адаптации']],
 bottom:'Предложение для обсуждения: назначения авторам и пригодность стендов проверяем пилотом',
 notes:'Предлагаем три самостоятельные ВКР на общем стенде. Первый автор исследует политику использования фиксированных моделей, включая калибровку уверенности и передачу решения в LLM. Второй исследует отбор документов при заданном бюджете контекста, сравнивая top-k, специализированный reranker и decision-модель. Третий исследует адаптацию decision-модели при фиксированной политике применения: объём разметки, обучение и перенос на новые задачи. Третье направление предлагается вместо пока не обоснованного GraphRAG. Имена авторов и окончательные темы ещё не назначены. Для переноса нужны независимые данные второго домена и согласованная схема решений. Результаты пока отсутствуют. Это предложение инициатора для обсуждения с командой и научным руководителем.'},
 {title:'Общий стенд и границы личного вклада',items:[
 ['Общая платформа','Агент, данные и логирование. Единая проверка успеха и учёт полной стоимости'],
 ['Автор 1: политика','Фиксирует модели. Исследует пороги, долю передачи в LLM и итоговый успех агента'],
 ['Автор 2: контекст','Фиксирует генератор и набор кандидатов. Исследует отбор при разных бюджетах'],
 ['Автор 3: модель','Фиксирует политику. Исследует эффект адаптации, объёма разметки и переноса']],
 bottom:'У каждого: собственная гипотеза, серия экспериментов и вывод. Совместные компоненты указываем',
 notes:'Общая инфраструктура делает сравнения воспроизводимыми, но не заменяет личный научный результат. Первый автор может выполнить работу на исходных фиксированных моделях, не ожидая дообучения третьего. Второй оценивает отбор контекста при одинаковом исходном наборе документов, генераторе и бюджете настройки. Третий оценивает модель до и после адаптации при одной политике, чтобы не смешивать эффект обучения и маршрутизации. Разбиение данных и финальный тест фиксируем заранее. Пороги и гиперпараметры выбираем только на данных настройки. Каждый сохраняет свою постановку, реализацию метода, протокол и анализ. Совместные эксперименты и компоненты описываем как общий вклад. Пилот должен проверить доступность эталонов решений, supporting facts и данных переноса. HotpotQA рассматриваем как вспомогательный стенд для контекста, τ-knowledge как сквозную проверку сервисного агента. Не усредняем их метрики. Достаточность тем и назначения согласует команда с руководителем.'}
];
for(const [i,d] of slides.entries()){
 const s=p.slides.add();s.background.fill=c.paper;
 text(s,d.title,72,58,1136,110,44,c.ink,true);
 if(d.rows){const t=s.tables.add({rows:4,columns:3,left:72,top:181,width:1136,height:390,columnWidths:[255,420,461],values:d.rows});t.borders.assign({fill:'#D5D7D1',width:.5,style:'solid'});for(let r=0;r<4;r++){t.rows[r].height=r===0?58:110.67;for(let col=0;col<3;col++){const cell=t.getCell(r,col);cell.fill=r===0?c.ink:c.paper;cell.text.style={typeface:font,fontSize:r===0?24:23,color:r===0?'#FFFFFF':c.ink,bold:r===0||col===0,autoFit:'none',verticalAlignment:'middle'};}}t.cells.block({row:0,column:0,rowCount:4,columnCount:3}).assign({margins:{left:14,right:14,top:10,bottom:10},anchor:'center'});}
 else d.items.forEach(([a,b],n)=>{text(s,a,72,190+n*97,310,85,27,c.teal,true);text(s,b,404,190+n*97,804,85,28);});
 text(s,d.bottom,72,594,1120,64,23,c.teal);text(s,String(13+i),1150,671,60,28,17,c.muted);
 s.speakerNotes.textFrame.setText(d.notes+'\n\nИсточники: docs/research.md; docs/team.md; docs/architecture.md; обсуждение с инициатором в проекте ВКР. Статус: предложение, экспериментальных результатов нет.');
 const png=await p.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(build,`new-slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
await(await PresentationFile.exportPptx(p)).save(path.join(build,'new-slides.pptx'));
await fs.writeFile(path.join(build,'content-team.json'),JSON.stringify(slides,null,2));
