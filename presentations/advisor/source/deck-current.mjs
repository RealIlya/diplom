import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const sourceDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(sourceDir, '../../..');
const work = path.resolve(process.env.DECK_WORK_DIR || path.join(root, 'artifacts/advisor-current'));
const build = path.join(work, '.build');
const out = path.join(work, 'output');
const moduleDir = process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES;
const skill = process.env.PRESENTATIONS_SKILL_DIR;
const python = process.env.CODEX_PRIMARY_RUNTIME_PYTHON;
if (!moduleDir || !skill || !python) throw new Error('Set CODEX_PRIMARY_RUNTIME_NODE_MODULES, CODEX_PRIMARY_RUNTIME_PYTHON and PRESENTATIONS_SKILL_DIR.');
const versions = JSON.parse(await fs.readFile(path.join(sourceDir, 'runtime-versions.json'), 'utf8'));
const packageRoot = path.join(moduleDir, '@oai/artifact-tool');
const installed = JSON.parse(await fs.readFile(path.join(packageRoot, 'package.json'), 'utf8'));
if (installed.version !== versions.artifact_tool) throw new Error('Artifact Tool version mismatch: expected ' + versions.artifact_tool + ', got ' + installed.version);
const { Presentation, PresentationFile } = await import(pathToFileURL(path.join(packageRoot, 'dist/artifact_tool.mjs')).href);
const { finalizePresentation } = await import(pathToFileURL(path.join(skill, 'container_tools/artifact_tool_utils.mjs')).href);
await fs.mkdir(build, {recursive: true}); await fs.mkdir(out, {recursive: true});
const font = versions.font;
const colors={paper:'#F4F1EA',ink:'#182B3B',teal:'#236F6A',muted:'#5D686E',red:'#A44D3A',white:'#FFFFFF'};
const p=Presentation.create({slideSize:{width:1280,height:720}});
const content=JSON.parse(await fs.readFile(path.join(sourceDir,'content-v4.json'),'utf8'));
const data=content.slides; const times=data.map(d=>d.seconds); const mainCount=content.main_slide_count;
function text(slide,value,x,y,w,h,size=28,color=colors.ink,bold=false){
 const s=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 s.text=value;
 s.text.style={typeface:font,fontSize:size,color,bold,autoFit:'none',wrap:'square',insets:{left:0,right:0,top:0,bottom:0}};
 return s;
}
function title(slide,value){text(slide,value,72,58,1136,110,44,colors.ink,true);}
function bottom(slide,value){text(slide,value,72,594,1120,64,23,colors.teal);}
function table(slide,d){
 const t=slide.tables.add({rows:d.rows.length,columns:d.cols.length,left:72,top:d.top??181,width:1136,height:d.height??390,columnWidths:d.cols,values:d.rows});
 t.borders.assign({fill:'#D5D7D1',width:0.5,style:'solid'});
 for(let r=0;r<d.rows.length;r++){
  t.rows[r].height=r===0?58:(((d.height??390)-58)/(d.rows.length-1));
  for(let c=0;c<d.cols.length;c++){
   t.getCell(r,c).fill=r===0?colors.ink:colors.paper;
   t.getCell(r,c).text.style={typeface:font,fontSize:r===0?24:(d.fontSize??23),color:r===0?colors.white:colors.ink,bold:r===0||c===0,autoFit:'none',verticalAlignment:'middle'};
  }
 }
 t.cells.block({row:0,column:0,rowCount:d.rows.length,columnCount:d.cols.length}).assign({margins:{left:14,right:14,top:10,bottom:10},anchor:'center'});
}
let elapsed=0;
const script=[];
for(let i=0;i<data.length;i++){
 const d=data[i],s=p.slides.add(); s.background.fill=colors.paper;
 if(d.type==='cover'){
  try{s.images.add({blob:new Uint8Array(await fs.readFile(path.join(sourceDir,'cover.png'))),contentType:'image/png',alt:'Концептуальная иллюстрация выбора пути. Не экспериментальные данные',fit:'cover',position:{left:0,top:0,width:1280,height:720}});}catch{}
  text(s,d.title,72,140,770,240,61,colors.ink,true);
  text(s,d.subtitle,72,419,790,80,28,colors.teal);
  text(s,d.line,72,520,800,80,24,colors.muted);
 }else{
  title(s,d.title);
  if(d.type==='agent'){
   text(s,d.intro,72,174,1125,92,31);
   d.items.forEach(([a,b],n)=>{
    text(s,a,72,289+n*72,305,62,27,colors.teal,true);
    text(s,b,404,289+n*72,804,67,26);
   });
  }else if(d.type==='flow'){
   const flowRow=(labels,y)=>{
    const boxes=labels.map((value,n)=>{
     const box=s.shapes.add({geometry:'rect',position:{left:72+n*300,top:y,width:235,height:99},fill:colors.paper,line:{fill:colors.teal,width:1.5}});
     box.text=value;
     box.text.style={typeface:font,fontSize:24,color:colors.ink,alignment:'center',verticalAlignment:'middle',autoFit:'none',insets:{left:8,right:8,top:6,bottom:6}};
     return box;
    });
    boxes.slice(0,-1).forEach((box,n)=>s.shapes.connect(box,boxes[n+1],{kind:'straight',fromSide:'right',toSide:'left',line:{fill:colors.teal,width:2},tail:{type:'triangle',width:'med',length:'med'}}));
   };
   text(s,'Работа агента',72,174,700,45,29,colors.teal,true);
   flowRow(d.work,231);
   text(s,'Возвращаем результат в историю и повторяем выбор шага до завершения обращения',72,351,1136,58,24);
   text(s,'Проверка в тестовой среде',72,429,900,45,29,colors.teal,true);
   flowRow(d.test,481);
  }else if(d.type==='decision'){
   text(s,d.intro,72,174,1136,65,31);
   table(s,{...d,cols:[565,571],top:259,height:290});
  }else if(d.type==='math-v2'){
   text(s,d.intro,72,173,1136,65,30,colors.teal);
   text(s,'min',137,249,116,63,49,colors.ink);
   text(s,'π ∈ Π',129,310,137,41,24,colors.ink);
   text(s,'E[C_agent(π, x)]',290,249,780,73,49,colors.ink);
   text(s,'при',137,357,100,53,28,colors.ink);
   text(s,'E[L(π, x)] − E[L(π₀, x)] ≤ ε',290,350,900,61,38,colors.ink);
   d.definitions.forEach(([a,b],n)=>{
    text(s,a,72,435+n*37,265,36,24,colors.teal,true);
    text(s,b,355,435+n*37,853,36,26);
   });
  }else if(d.type==='split'){
   text(s,d.leftTitle,72,190,510,48,30,colors.teal,true);
   text(s,d.rightTitle,670,190,538,48,30,colors.teal,true);
   d.left.forEach((v,n)=>text(s,v,72,260+n*99,506,86,28));
   d.right.forEach((v,n)=>text(s,v,670,260+n*99,535,86,28));
  }else if(d.type==='table')table(s,d);
  else if(d.type==='rows')d.items.forEach(([a,b],n)=>{
   text(s,a,72,190+n*97,310,85,27,colors.teal,true);
   text(s,b,404,190+n*97,804,85,28);
  });
  else if(d.type==='example'){
   text(s,d.quote,72,180,1080,105,38,colors.teal);
   d.steps.forEach(([num,a,b],n)=>{
    const x=72+n*288;
    text(s,num,x,324,240,55,43,colors.teal);
    text(s,a,x,391,250,43,28,colors.ink,true);
    text(s,b,x,453,250,110,26);
   });
  }else if(d.type==='math'){
   text(s,d.equation,72,200,570,134,49,colors.teal,true);
   text(s,d.constraint,72,355,636,100,32,colors.ink);
   d.definitions.forEach(([a,b],n)=>{
    text(s,a,734,202+n*88,125,76,27,colors.teal,true);
    text(s,b,875,202+n*88,335,80,26);
   });
  }else if(d.type==='closing'){
   d.items.forEach((v,n)=>{text(s,String(n+1).padStart(2,'0'),72,193+n*94,80,60,38,colors.teal);text(s,v,183,193+n*94,980,76,31);});
  }else if(d.type==='sources'){
   d.items.forEach(([a,b,url],n)=>{const link=text(s,a,72,186+n*98,330,50,28,colors.teal,true);link.text.get(a).link={uri:url,isExternal:true};text(s,b,417,186+n*98,790,75,25);});
  }
  if(d.bottom)bottom(s,d.bottom);
 }
 text(s,i<mainCount?String(i+1).padStart(2,'0'):('В'+(i-mainCount+1)),1150,671,60,28,17,colors.muted);
 const seconds=times[i]??0;
 const timing=i<mainCount?`Время: ${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}. Начало: ${Math.floor(elapsed/60)}:${String(elapsed%60).padStart(2,'0')}.`:'Резервный слайд. В основное время не входит.';
 const sources=d.sources;
 s.speakerNotes.textFrame.setText(`${timing}\n\n${d.notes}\n\nИсточники:\n${sources.join('\n')}`);
 script.push(`${i+1}. ${d.title.replaceAll('\n',' ')}\n${timing}\n\n${d.notes}\n\nИсточники: ${sources.join('\n')}\n`);
 elapsed+=seconds;
}
if(elapsed!==content.total_seconds||data.length!==16)throw new Error('Неверный хронометраж или число слайдов');
await fs.writeFile(path.join(out,'speaker-notes-v4.txt'),'Предложение исследования. Основной доклад: 18 минут. Слайды 1–14, затем резерв 15–16.\n\n'+script.join('\n\n'));
await fs.writeFile(path.join(build,'content-v4-checked.json'),JSON.stringify(data,null,2));
const candidate=path.join(build,'candidate-v4.pptx');
await(await PresentationFile.exportPptx(p)).save(candidate);
const final=path.join(out,'advisor-presentation-v4-reviewed.pptx');
const tableOwners=[4,9,10,12,15];
const result=await finalizePresentation({workspaceDir:work,candidatePath:candidate,finalPath:final,pythonExecutable:python,integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),explicitTotalSlideCount:16,requiredNativeTableOwnerSlides:tableOwners,requiredNativeChartOwnerSlides:[],layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit',...tableOwners.flatMap(n=>['--require-native-table-slide',String(n)])],fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});
for (let i=0;i<p.slides.items.length;i++) {
 const png=await p.export({slide:p.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(build,'slide-'+(i+1)+'.png'),new Uint8Array(await png.arrayBuffer()));
}
console.log(JSON.stringify(result));

