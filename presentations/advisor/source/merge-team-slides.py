from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E

root=Path(__file__).resolve().parent
source=Path(sys.argv[1]); new_deck=Path(sys.argv[2]); target=Path(sys.argv[3])
P='http://schemas.openxmlformats.org/presentationml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PK='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
def xml(b):return E.fromstring(b.lstrip(b'\xef\xbb\xbf'))
def out(x):return E.tostring(x,xml_declaration=True,encoding='utf-8')
with ZipFile(source) as z: files={n:z.read(n) for n in z.namelist()}
pres=xml(files['ppt/presentation.xml'])
ids=pres.find('{'+P+'}sldIdLst')
rels=xml(files['ppt/_rels/presentation.xml.rels'])
ct=xml(files['[Content_Types].xml'])
with ZipFile(new_deck) as z:
 for old,new in [(1,15),(2,16)]:
  for folder,prefix in [('slides','slide'),('notesSlides','notesSlide')]:
   dest=f'ppt/{folder}/{prefix}{new}.xml'
   files[dest]=z.read(f'ppt/{folder}/{prefix}{old}.xml')
   rr=xml(z.read(f'ppt/{folder}/_rels/{prefix}{old}.xml.rels'))
   for rel in rr:
    typ=rel.get('Type').rsplit('/',1)[-1]
    if typ=='slideLayout':rel.set('Target','/ppt/slideLayouts/slideLayout1.xml')
    if typ=='notesMaster':rel.set('Target','/ppt/notesMasters/notesMaster1.xml')
    if typ=='slide':rel.set('Target',f'/ppt/slides/slide{new}.xml')
    if typ=='notesSlide':rel.set('Target',f'/ppt/notesSlides/notesSlide{new}.xml')
   files[f'ppt/{folder}/_rels/{prefix}{new}.xml.rels']=out(rr)
   E.SubElement(ct,'{'+CT+'}Override',PartName='/'+dest,ContentType='application/vnd.openxmlformats-officedocument.presentationml.'+('slide' if folder=='slides' else 'notesSlide')+'+xml')
  rid=f'RteamSlide{new}'
  E.SubElement(rels,'{'+PK+'}Relationship',Id=rid,Type=R+'/slide',Target=f'/ppt/slides/slide{new}.xml')
  el=E.Element('{'+P+'}sldId',id=str(300+new));el.set('{'+R+'}id',rid);ids.insert(12+old-1,el)
files['ppt/presentation.xml']=out(pres)
files['ppt/_rels/presentation.xml.rels']=out(rels)
files['[Content_Types].xml']=out(ct)
if 'docProps/app.xml' in files:
 app=xml(files['docProps/app.xml'])
 for e in app.iter():
  if E.QName(e).localname=='Slides':e.text='16'
 files['docProps/app.xml']=out(app)
target.parent.mkdir(parents=True,exist_ok=True)
# Align the existing reserve slide with the new proposed third topic.
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
reserve=xml(files['ppt/slides/slide13.xml'])
cells=reserve.findall('.//a:tc',ns)
for cell,values in [(cells[9],['Адаптация модели']),(cells[10],['Как объём разметки влияет на качество','и перенос на новые задачи?']),(cells[11],['Кандидат,','проверить пилотом'])]:
 for node,value in zip(cell.findall('.//a:t',ns),values):node.text=value
files['ppt/slides/slide13.xml']=out(reserve)
note=xml(files['ppt/notesSlides/notesSlide13.xml'])
for node in note.findall('.//a:t',ns):
 if node.text and ('связ' in node.text.lower() or 'граф' in node.text.lower()):
  node.text='Предлагаем три самостоятельных исследования: политика маршрутизации, отбор контекста и адаптация decision-модели. Подробности и границы личного вклада на слайдах 13–14. Назначения авторам, пригодность данных и окончательные темы требуют пилота и согласования. GraphRAG остаётся возможным будущим направлением.'
files['ppt/notesSlides/notesSlide13.xml']=out(note)
with ZipFile(target,'w',ZIP_DEFLATED) as z:
 for n,b in files.items():z.writestr(n,b)
with ZipFile(source) as a,ZipFile(target) as b:
 for n in a.namelist():
  if n not in ['ppt/slides/slide13.xml','ppt/notesSlides/notesSlide13.xml'] and n.startswith(('ppt/slides/','ppt/notesSlides/','ppt/media/','ppt/slideLayouts/','ppt/slideMasters/','ppt/theme/')):
   assert a.read(n)==b.read(n),n
assert len(ids)==16
print('16 slides. Original parts preserved except the third topic on the reserve slide and its notes.')
