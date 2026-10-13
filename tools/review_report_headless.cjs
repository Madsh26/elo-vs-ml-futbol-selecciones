// UI checks only: load the generated offline report; never run ML pipelines.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {pathToFileURL} = require('node:url');
let playwright;
try { playwright = require('playwright'); }
catch { playwright = require(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')); }
const root = path.resolve(__dirname, '..');
const htmlPath = path.join(root, 'reports/final_evaluation/football_report.html');
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

(async () => {
  const options = {headless:true};
  if (process.env.REPORT_BROWSER_BIN) options.executablePath = process.env.REPORT_BROWSER_BIN;
  else if (process.platform === 'win32') options.channel = 'msedge';
  const browser = await playwright.chromium.launch(options);
  const context = await browser.newContext({acceptDownloads:true});
  const page = await context.newPage();
  const errors=[], external=[];
  page.on('pageerror', e=>errors.push(e.message));
  page.on('console', m=>{ if(m.type()==='error') errors.push(m.text()); });
  await context.route('**/*', route=>{
    const url = route.request().url();
    if (/^https?:/.test(url)) {external.push(url);return route.abort();}
    return route.continue();
  });
  const widths=[];
  try {
    await page.goto(pathToFileURL(htmlPath).href);
    await page.waitForSelector('#matches tr');
    assert.equal(await page.locator('#matches tr').count(),72);
    assert.equal(await page.locator('#method option').count(),8);
    for (const width of [390,768,1366]) {
      await page.setViewportSize({width,height:950});
      const result=await page.evaluate(()=>({viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
      if(result.scrollWidth>result.viewport)console.log(await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,12).map(e=>({tag:e.tagName,id:e.id,class:e.className,right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width,text:e.textContent.slice(0,80)}))));
      assert(result.scrollWidth<=result.viewport,JSON.stringify(result));
      widths.push(result);
      if(width===1366){
        const bounds=await page.evaluate(()=>{
          const cell=document.querySelector('#matches tr td:last-child').getBoundingClientRect();
          const scroll=document.querySelector('#matches').closest('.scroll').getBoundingClientRect();
          const detail=document.querySelector('#detail').getBoundingClientRect();
          return {resultRight:cell.right,containerRight:scroll.right,detailLeft:detail.left};
        });
        assert(bounds.resultRight<=bounds.containerRight+1,JSON.stringify(bounds));
        assert(bounds.resultRight<bounds.detailLeft,JSON.stringify(bounds));
      }
      if(width!==768)await page.screenshot({path:path.join(root,`assets/report_${width}.png`),fullPage:true});
    }
    await page.locator('#search').fill('Colombia');
    assert.equal(await page.locator('#matches tr').count(),3);
    await page.locator('#matches tr').filter({hasText:'Portugal'}).click();
    assert.match(await page.locator('#detail').innerText(),/2060/);
    assert.match(await page.locator('#detail').innerText(),/2023/);
    assert.match(await page.locator('#detail').innerText(),/Elo solo conoce resultados/);
    const colors=await page.evaluate(()=>[...document.querySelectorAll('#detail .minibar i')].map(e=>getComputedStyle(e).backgroundColor));
    assert.equal(new Set(colors).size,3);
    const before=await page.locator('#detail').innerText();
    await page.locator('#method').selectOption('poisson');
    assert.notEqual(await page.locator('#detail').innerText(),before);
    await page.locator('#method').selectOption('logistic');
    for(const method of await page.locator('#method option').evaluateAll(options=>options.map(o=>o.value))){
      await page.locator('#method').selectOption(method);
      assert.equal(await page.locator('#matches tr').count(),3);
    }
    await page.locator('#method').selectOption('logistic');
    await page.locator('#search').fill('');
    await page.locator('#group').selectOption('K');
    assert.equal(await page.locator('#matches tr').count(),6);
    await page.locator('#search').fill('Colombia');
    assert.equal(await page.locator('#matches tr').count(),3);
    await page.locator('#group').selectOption('A');
    assert.equal(await page.locator('#matches tr').count(),0);
    assert.match(await page.locator('#detail').innerText(),/No hay partidos/);
    await page.locator('#group').selectOption('');
    await page.locator('#search').fill('');
    for(const sort of ['error','draw','date']){
      await page.locator('#sort').selectOption(sort);
      const ordered=await page.evaluate(()=>shown.map(f=>({id:f.id,date:f.date,loss:f.models[$('method').value].loss,draw:f.models[$('method').value].p[1]})));
      for(let i=1;i<ordered.length;i++){
        if(sort==='error')assert(ordered[i-1].loss>=ordered[i].loss);
        if(sort==='draw')assert(ordered[i-1].draw>=ordered[i].draw);
        if(sort==='date')assert(ordered[i-1].date<=ordered[i].date);
      }
    }
    await page.locator('#search').fill('Colombia');
    const downloadPromise=page.waitForEvent('download');
    await page.locator('#export').click();
    const download=await downloadPromise;
    assert.equal(download.suggestedFilename(),'probabilidades_mundial.csv');
    const stream=await download.createReadStream();
    const chunks=[];for await(const chunk of stream)chunks.push(chunk);
    const csv=Buffer.concat(chunks).toString('utf8');
    assert.equal(csv.trim().split(/\r?\n/).length,4);
    assert(csv.includes('Colombia')&&csv.includes('Portugal'));
    const windows=[];
    for(const window of ['semi','selection','world']){
      await page.locator('#window').selectOption(window);
      assert.equal(await page.locator('#comparison tr').count(),8);
      assert.equal(await page.locator('#comparisonChart .delta-row').count(),6);
      const content=await page.locator('#comparisonChart').innerText();
      assert.match(content,/IC 95%/);
      windows.push({window,intervals:await page.locator('#comparisonChart svg').count(),content_sha256:crypto.createHash('sha256').update(content).digest('hex')});
    }
    assert.equal(new Set(windows.map(w=>w.content_sha256)).size,3);
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    const review={recorded_at_utc:new Date().toISOString(),method:'Playwright Chromium headless; offline file URL',
      presentation_after_evaluation:true,models_rerun:false,metrics_protocols_conclusions_changed:false,
      html_sha256:hash(htmlPath),browser_version:browser.version(),viewport_checks:widths,
      observed_matches:72,observed_model_options:8,console_errors:errors,external_requests:external,
      verified_controls:['search','group and combined filters','empty search result','all eight methods','date/error/draw sorting','CSV download content','all three evaluation windows','neutral Elo explanation','three probability colors','desktop result column visible'],
      evaluation_windows:windows,screenshots:[390,1366].map(width=>({file:`assets/report_${width}.png`,sha256:hash(path.join(root,`assets/report_${width}.png`))}))};
    fs.writeFileSync(path.join(root,'reports/final_evaluation/html_review.json'),JSON.stringify(review,null,2),'utf8');
    console.log(JSON.stringify(review,null,2));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
