// Exercise real UI functions with delayed network responses, without a browser or API.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
let js = fs.readFileSync('scripts/system_one_pilot/review.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
js = js.slice(0, js.indexOf('(async()=>{try{state='));
const fields = {note:{value:'A original'}, disposition:{value:'decision'}, adopted:{value:'independent'}, filter:{value:'all'}, statusFilter:{value:'all'}, search:{value:''}, inspector:{inert:false}};
const ctx = {document:{getElementById:id=>fields[id]??(fields[id]={}),createElement:tag=>({tag,children:[],append(...nodes){this.children.push(...nodes)}})},window:{addEventListener(){}},setTimeout,clearTimeout,console,assert};
vm.createContext(ctx); vm.runInContext(js,ctx);
vm.runInContext(`
current={translation:{strings:{'Original condition':'Русское условие'}}};
const panel=el('section');bilingual(panel,'Original condition');
assert.equal(panel.children[0].textContent,'Русское условие');
assert.equal(panel.children[1].children[1].textContent,'Original condition');
const formatted=el('section');bilingual(formatted,'Original condition',text=>'['+text+']');
assert.equal(formatted.children[0].textContent,'[Русское условие]');
assert.equal(formatted.children[1].children[1].textContent,'Original condition');
current={translation:null};const fallback=el('section');bilingual(fallback,'English fallback');
assert.equal(fallback.children[0].textContent,'English fallback');
assert.equal(fallback.children.length,1);
console.log('PASS: Russian text, exact original disclosure and missing-translation fallback');
`,ctx);
vm.runInContext(`
const a={card:{id:'A',input_sha256:'ha'},review:{revision:0,draft:{note:'A original'}}};
const b={card:{id:'B',input_sha256:'hb'},review:{revision:0,draft:{note:'B original'}}};
current=a; state.queue=[{id:'A'},{id:'B'}];
localDraft={label:'useful',note:'A original',disposition:'decision',adopted:'independent'};
renderQueue=()=>{}; error=()=>{};
renderCard=()=>{localDraft={...localDraft,...current.review.draft};$('note').value=localDraft.note};
let release,entered; const enteredPromise=new Promise(r=>entered=r); const pending=new Promise(r=>release=r); let sent=[];
api=async(url,body)=>{if(url.startsWith('/api/card')){entered();return pending};if(url==='/api/session')return {};sent.push(body);return b};
(async()=>{
 const n=navigate('B'); await enteredPromise;
 const blocked=$('inspector').inert;
 if(!blocked){$('note').value='A new UNSAVED';dirty=true;localDraft=draft()}
 release(b); await n; await flush();
 assert(blocked || sent.some(r=>r.id==='A'&&r.draft.note==='A new UNSAVED'), 'input during navigation was lost');
 assert(!$('inspector').inert, 'navigation left inspector locked');
 // Failed session persistence must leave both current identity and visible draft on A.
 current=a;renderCard();
 api=async(url)=>{if(url.startsWith('/api/card'))return b;throw Error('session write failed')};
 await navigate('B');
 assert.equal(current.card.id,'A');assert.equal($('note').value,'A original');
 assert(!$('inspector').inert);
 // Provenance follows the exact bundle displayed, including old English-only tabs.
 for(const shown of ['shown-ru-bundle',null]){
   state={queue:[{id:'A'}],session:{}};
   current={...a,translation:shown?{bundle_sha256:shown}:null};localDraft={label:'useful',note:'my reason',disposition:'decision',adopted:'independent'};
   $('note').value='my reason';dirty=true;let actions=[];
   api=async(url,body)=>{if(url==='/api/act'){actions.push(body);return current}if(url==='/api/state')return {queue:[],session:{}};return {}};
   await flush();await mutate('confirm');
   assert.equal(actions[0].translation_bundle_sha256,shown);
   assert.equal(actions[1].translation_bundle_sha256,shown);
 }
 console.log('PASS: draft/confirm audit records the displayed translation hash or null');
 console.log('PASS: delayed navigation and failed session persistence preserve card identity/draft');
})();
`,ctx);
