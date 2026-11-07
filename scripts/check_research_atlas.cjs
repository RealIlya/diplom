/* Browser verification of the generated atlas, with local Playwright + Chrome.
 * Set NODE_PATH to an installed Playwright package directory; no download needed.
 * Run: node scripts/check_research_atlas.cjs [output-directory]
 */
const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
const {chromium} = require('playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const dir = path.join(root, 'site/research-atlas');
  const out = path.resolve(process.argv[2] || path.join(root, 'artifacts/research-atlas-check'));
  fs.mkdirSync(out, {recursive: true});
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    chromiumSandbox: true,
  });
  const page = await browser.newPage({viewport: {width: 1480, height: 1080}});
  const errors = [], network = [], warnings = [], results = [];
  let current = '';
  page.on('pageerror', e => errors.push({page: current, error: e.message}));
  page.on('console', m => {if(['error', 'warning'].includes(m.type())) warnings.push({page: current, message: m.text()});});
  await page.route(/^https?:/, route => {network.push(route.request().url());return route.abort();});
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.html')).sort();
  for (const file of files) {
    current = file;
    await page.goto(pathToFileURL(path.join(dir, file)).href);
    const meta = await page.evaluate(() => ({
      warnings: window.archValidate(),
      flows: [...document.querySelectorAll('.flowtab')].map(b => b.dataset.flow),
      ids: [...document.querySelectorAll('[id]')].map(x => x.id),
      overflow: document.documentElement.scrollWidth > innerWidth,
    }));
    if(meta.warnings.length) errors.push({page:file,integrity:meta.warnings});
    const duplicates = meta.ids.filter((id, i) => meta.ids.indexOf(id) !== i);
    if(duplicates.length) errors.push({page:file,duplicateIds:duplicates});
    if(meta.overflow) errors.push({page:file,bodyOverflow:true});
    let steps = 0;
    for(const flow of meta.flows) {
      await page.locator(`[data-flow="${flow}"]`).click();
      const count = Number(await page.locator('#panelStepTotal').textContent());
      for(let i=0;i<count;i++) {
        const state = await page.evaluate(() => ({
          title: document.getElementById('panelTitle').textContent,
          active: document.querySelectorAll('.node.active,.node.active-from').length,
          wires: document.querySelectorAll('.wire.active').length,
        }));
        if(!state.title || state.title==='—' || state.active===0 || state.wires===0) errors.push({page:file,flow,step:i,state});
        steps++;
        if(i<count-1) await page.locator('#btnNext').click();
      }
    }
    await page.locator('.flowtab').first().click();
    await page.locator('#btnPlay').click();
    if(await page.locator('#btnPlay').getAttribute('aria-pressed')!=='true') errors.push({page:file,playFailed:true});
    await page.locator('#btnPlay').click();
    const lightBefore = (await page.locator('body').getAttribute('class') || '').includes('light');
    await page.locator('#btnTheme').click();
    if((await page.locator('body').getAttribute('class') || '').includes('light')===lightBefore) errors.push({page:file,themeFailed:true});
    await page.locator('#btnTheme').click();
    if(['index.html','software.html','roadmap.html','training.html','dataset.html'].includes(file)) {
      await page.screenshot({path:path.join(out,file.replace('.html','-desktop.png'))});
    }
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(100);
    if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) errors.push({page:file,mobileBodyOverflow:true});
    if(['index.html','roadmap.html','software.html'].includes(file)) await page.screenshot({path:path.join(out,file.replace('.html','-mobile.png'))});
    await page.setViewportSize({width:1480,height:1080});
    results.push({file,flows:meta.flows.length,steps});
  }
  current='roadmap.html';
  await page.goto(pathToFileURL(path.join(dir,current)).href);
  await page.locator('#roadStart').fill('2027-01-04');
  await page.locator('#roadWeek').fill('8');
  await page.locator('[data-phase="7"]').click();
  if(!(await page.locator('#roadDetail').textContent()).includes('P7')) errors.push({roadmap:'phase selection failed'});
  if(!(await page.locator('#roadDate').textContent()).includes('22.02.2027')) errors.push({roadmap:'date calculation failed'});
  await page.locator('#roadWeek').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'roadmap-interaction.png')});
  current='training.html';
  await page.goto(pathToFileURL(path.join(dir,current)).href);
  await page.locator('[data-case="3"]').click();
  if(!(await page.locator('#matrixDetail').textContent()).includes('взаимодействие')) errors.push({matrix:'selection failed'});
  current='results.html';
  await page.goto(pathToFileURL(path.join(dir,current)).href);
  await page.locator('#adaptCost').fill('100');await page.locator('#baseCost').fill('3');await page.locator('#newCost').fill('2');
  if(!(await page.locator('#calcResult').textContent()).includes('недопустим')) errors.push({calculator:'missing quality gate'});
  await page.locator('#qualityGate').selectOption('yes');
  if(!(await page.locator('#calcResult').textContent()).includes('100')) errors.push({calculator:'wrong break-even'});
  await page.locator('#newCost').fill('4');
  if(!(await page.locator('#calcResult').textContent()).includes('неположительна')) errors.push({calculator:'nonpositive savings failed'});
  current='index.html';
  await page.goto(pathToFileURL(path.join(dir,current)).href);
  await page.emulateMedia({reducedMotion:'reduce'});
  if(await page.locator('.packet').first().evaluate(el=>getComputedStyle(el).display)!=='none') errors.push({reducedMotion:'packet still visible'});
  await browser.close();
  const report = {pages:results.length,flows:results.reduce((s,r)=>s+r.flows,0),steps:results.reduce((s,r)=>s+r.steps,0),results,errors,warnings,networkRequests:network};
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({pages:report.pages,flows:report.flows,steps:report.steps,errors,warnings,networkRequests:network,output:out},null,2));
  if(errors.length||warnings.length||network.length) process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
