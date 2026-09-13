/* Optional real-browser checks. Requires Playwright and a running local workbench.
 * All job API requests are intercepted; this never starts or approves an AI run.
 * See wiki/runbooks/web-workbench.md for invocation.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.FACTORY_TEST_URL || 'http://127.0.0.1:8765';
const output = path.resolve('.factory/visual-review');

(async () => {
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({headless: true,
    ...(process.env.FACTORY_BROWSER ? {executablePath: process.env.FACTORY_BROWSER} : {})});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 960}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
    const state = {
      idea:'历史测试需求', phase: 'plan_done', errors: [], build_dir: null, acceptance_report: null,
      requirements: ['中文界面', '手机上也能使用'],
      product_spec: {project_name: '个人作品集', one_liner: '一个展示个人介绍、项目与联系方式的中文网站。',
        target_users: '潜在合作伙伴', core_features: ['个人介绍与经历', '项目展示及筛选', '联系入口'],
        mvp_in_scope: ['响应式页面与键盘操作', '真实项目内容'], mvp_out_of_scope: ['账户注册和支付'],
        user_stories: [], success_metrics: ['可以快速找到项目和联系方式'], risks: ['需提供真实项目素材']},
      architecture: {stack: {frontend: 'Next.js', styling: 'CSS', database: '无需数据库'},
        data_model: '项目包含标题、描述与链接。', adrs: [], api_design: []},
      dag: {nodes: [{id: 'page', done_criteria: '完成介绍、项目和联系三个内容区域', risk: 'low', est_minutes: 20}]}
    };
    let snapshot = {id: 'visual-test', waiting: 'plan', done: false, logs: ['已整理需求', '等待确认方案'], state};
    let submitted, decision, rejectOnce = true;
    const archived={id:'archive-1',done:true,waiting:null,created_at:'2026-09-10T08:00:00Z',updated_at:'2026-09-10T09:00:00Z',logs:['历史日志'],decisions:[{stage:'plan',approved:true,feedback:'保留中文',at:'2026-09-10T08:10:00Z'}],state:{...state,phase:'gate_2_approved',gate_2_approved:true,build_dir:'generated/archive-1',generated_files:[{path:'app/page.tsx',content:'export default function Page(){return <main>作品集</main>}'}]}};
    let archivedPreview={status:'stopped',url:null,error:null};
    archived.state.delivery_mode=true;
    archived.state.project_id='archive-1';
    archived.state.business_cases=[{name:'保存后刷新',steps:[{action:'text',target:'作品集'}]}];
    archived.state.business_report={passed:true,cases:[{name:'保存后刷新',width:1440,steps:6,passed:true},{name:'保存后刷新',width:390,steps:6,passed:true}]};
    archived.state.model_calls=[{run_id:'archive-1',model:'test',status:'completed',reserved_tokens:2000,input_tokens:100,output_tokens:200,cost:.0019,price:{currency:'CNY'}}];
    let savedPrice=null,recoveries=0;
    const interrupted={...archived,id:'interrupted',state:{...archived.state,workspace_id:'archive-1',phase:'interrupted',gate_2_approved:false}};
    await page.route('**/api/**', async route => {
      const request = route.request();
      const pathname=new URL(request.url()).pathname;
      if(pathname==='/api/prices'){
        if(request.method()==='POST'){savedPrice=request.postDataJSON();return route.fulfill({json:savedPrice})}
        return route.fulfill({json:{workflow_version:2,model:'test',prices:{}}});
      }
      if(pathname==='/api/costs')return route.fulfill({json:{estimated:{CNY:.0019},calls:1,unpriced_calls:0,legacy_tasks_without_usage:0}});
      if(pathname==='/api/jobs/interrupted')return route.fulfill({json:interrupted});
      if(pathname==='/api/jobs/interrupted/changes')return route.fulfill({json:{files:[]}});
      if(pathname==='/api/jobs/interrupted/preview')return route.fulfill({json:{status:'stopped'}});
      if(pathname==='/api/jobs/interrupted/resume'){recoveries++;return route.fulfill({json:{id:'visual-test'}})}
      if(pathname==='/api/jobs/archive-1/bundle')return route.fulfill({contentType:'application/zip',body:Buffer.from('504b0506000000000000000000000000000000000000','hex')});
      if(pathname==='/api/projects/archive-1')return route.fulfill({json:{id:'archive-1',title:'历史作品集',current_version:'archive-1',client:'测试客户',versions:[{id:'archive-1',number:1,status:'accepted',updated_at:archived.updated_at}],events:[]}});
      if(pathname==='/api/jobs/archive-1/changes')return route.fulfill({json:{base_version:null,files:[{path:'app/page.tsx',kind:'added',diff:'+ export default function Page(){}'}]}});
      if(request.method()==='GET'&&pathname==='/api/jobs')return route.fulfill({json:{tasks:[{id:'archive-1',title:'历史作品集',status:'accepted',created_at:archived.created_at},{id:'interrupted',title:'中断的测试任务',status:'interrupted',created_at:archived.created_at}],total:2}});
      if(pathname==='/api/jobs/archive-1/preview'){
        if(request.method()==='POST')archivedPreview=request.postDataJSON().action==='start'?{status:'ready',url:'http://127.0.0.1:54321',error:null}:{status:'stopped',url:null,error:null};
        return route.fulfill({json:archivedPreview});
      }
      if(pathname==='/api/jobs/archive-1')return route.fulfill({json:archived});
      if (request.method() === 'POST' && request.url().endsWith('/api/jobs')) {
        submitted = request.postDataJSON();
        return route.fulfill({json: {id: 'visual-test'}});
      }
      if (request.method() === 'POST' && request.url().endsWith('/decision')) {
        decision = request.postDataJSON();
        if (rejectOnce) {rejectOnce = false; return route.abort('failed');}
        snapshot = {...snapshot, waiting: null, done: true, state: {...state, phase: 'plan_rejected'}};
        return route.fulfill({json: {ok: true}});
      }
      return route.fulfill({json: snapshot});
    });
    await page.goto(base, {waitUntil: 'networkidle'});
    await page.locator('#delivery-mode').selectOption('demo');
    await page.waitForTimeout(1800);
    // Include wide/short windows and CSS viewport sizes typical of browser zoom.
    for (const [width, height] of [[2558,1358],[2048,1086],[1920,900],[1536,720],[1366,650],[1280,720],[1024,600],[853,480],[1440,960],[768,1024],[390,844]]) {
      await page.setViewportSize({width, height});
      await page.evaluate(() => scrollTo(0, 0));
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}px overflow`);
      assert(await page.evaluate(() => {
        const word=document.querySelector('.display-word').getBoundingClientRect();
        return ['.hero-copy','.hero-about'].every(selector=>document.querySelector(selector).getBoundingClientRect().top > word.bottom+12);
      }), `${width}x${height}: hero word overlaps captions`);
      assert(await page.evaluate(() => [...document.images].every(image => image.complete && image.naturalWidth > 0)), 'missing artwork');
      await page.screenshot({path: path.join(output, `page-${width}.png`), fullPage: true});
    }
    await page.setViewportSize({width: 1440, height: 960});
    assert.equal(await page.locator('.study-selector').count(), 0);
    const tourTitles=['从你的原话开始。','先看清方向，再出发。','让实现过程看得见。','最后一步，由你亲手检验。'];
    for(const i of [1,2,3,0]){
      await page.locator('[data-tour]').nth(i).click();
      assert.equal(await page.locator('#tour-title').innerText(),tourTitles[i]);
      assert.equal(await page.locator('[data-tour]').nth(i).getAttribute('aria-pressed'),'true');
      assert(await page.locator('.scene').nth(i).evaluate(el=>el.classList.contains('active')));
    }
    await page.locator('.art-control').click();
    assert.equal(await page.locator('#tour-title').innerText(),tourTitles[1]);
    assert(await page.locator('.scene--tilt').evaluate(el => el.classList.contains('active')));
    await page.keyboard.press('ArrowRight');
    assert(await page.locator('.scene--reverse').evaluate(el => el.classList.contains('active')));
    const artBox=await page.locator('.art-control').boundingBox();
    await page.mouse.move(artBox.x+artBox.width*.65,artBox.y+artBox.height*.5);
    await page.mouse.down();
    await page.mouse.move(artBox.x+artBox.width*.35,artBox.y+artBox.height*.5,{steps:8});
    await page.mouse.up();
    assert(await page.locator('.scene--detail').evaluate(el => el.classList.contains('active')), 'drag switches exactly once');
    assert.equal(await page.locator('#tour-title').innerText(),tourTitles[3]);
    await page.mouse.move(900, 150);
    assert.equal(await page.locator('body').evaluate(el => getComputedStyle(el).cursor), 'none');
    assert(await page.locator('.cursor-aura').evaluate(el => el.classList.contains('visible')));
    await page.mouse.move(1100,250,{steps:18});
    await page.waitForTimeout(35);
    assert(await page.locator('.pointer-particles').evaluate(el=>el.getContext('2d').getImageData(0,0,el.width,el.height).data.some((v,i)=>i%4===3&&v>0)), 'no moving particles');
    await page.screenshot({path: path.join(output, 'particle-cursor.png')});
    await page.waitForTimeout(700);
    assert(await page.locator('.pointer-particles').evaluate(el=>el.getContext('2d').getImageData(0,0,el.width,el.height).data.every((v,i)=>i%4!==3||v===0)), 'particles remain after pointer stops');
    await page.locator('#open-manual').click();
    assert(await page.locator('#system-manual').evaluate(el => el.open));
    assert.equal(await page.locator('.manual-chapters details').count(), 6);
    assert.equal(submitted, undefined, 'manual started an actual task');
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:960});
      await page.screenshot({path:path.join(output,`manual-${width}.png`)});
      await page.locator('.manual-chapters details').evaluateAll(items=>items.forEach(item=>item.open=true));
      const headerTop=await page.locator('#system-manual .manual-head').evaluate(el=>el.getBoundingClientRect().top);
      for(const fraction of [.5,1]){
        await page.locator('#system-manual .manual-body').evaluate((el,f)=>{el.scrollTop=el.scrollHeight*f},fraction);
        assert(await page.evaluate(()=>document.querySelector('.manual-body').getBoundingClientRect().top>=document.querySelector('.manual-head').getBoundingClientRect().bottom), 'header covers scroll viewport');
        assert.equal(await page.locator('#system-manual .manual-head').evaluate(el=>el.getBoundingClientRect().top),headerTop);
        assert.equal(await page.locator('#system-manual').evaluate(el=>el.scrollTop),0);
        await page.screenshot({path:path.join(output,`manual-scroll-${width}-${fraction}.png`)});
      }
      await page.locator('.manual-chapters details').evaluateAll(items=>items.forEach((item,i)=>item.open=i===0));
      await page.locator('#system-manual .manual-body').evaluate(el=>el.scrollTop=0);
    }
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#system-manual').evaluate(el => el.open), false);
    assert(await page.locator('#open-manual').evaluate(el => el === document.activeElement));
    await page.locator('#open-manual').click();
    await page.locator('#manual-start').click();
    await page.waitForFunction(() => document.activeElement.id === 'idea');
    assert(await page.locator('#idea').evaluate(el => el === document.activeElement));
    await page.emulateMedia({reducedMotion: 'reduce'});
    await page.mouse.move(1200, 200);
    assert.equal(await page.locator('.art-parallax').evaluate(el => getComputedStyle(el).transform), 'none');
    assert.equal(await page.locator('.scene').first().evaluate(el => getComputedStyle(el).transitionDuration), '0s');
    const touchContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
    const touchPage=await touchContext.newPage();
    await touchPage.goto(base);
    await touchPage.locator('#open-manual').tap();
    assert(await touchPage.locator('#system-manual').evaluate(el=>el.open));
    assert.equal(await touchPage.locator('.cursor-aura').evaluate(el=>getComputedStyle(el).display),'none');
    await touchPage.locator('#close-manual').tap();
    await touchContext.close();

    assert.equal(await page.locator('#task-history').isVisible(),false);
    await page.locator('#open-history').click();
    await page.locator('#task-history').waitFor({state:'visible'});
    await page.screenshot({path:path.join(output,'history-list.png')});
    await page.locator('.history-row').first().click();
    await page.locator('#history-dialog').waitFor({state:'visible'});
    await page.locator('#project-meta').filter({hasText:'当前可用版本'}).waitFor({state:'attached'});
    assert.equal(await page.locator('#history-idea').innerText(),archived.state.idea||'');
    assert.equal(await page.locator('#history-resume').isVisible(),false);
    assert((await page.locator('#history-cost').textContent()).includes('CNY 0.001900'));
    await page.locator('#history-dialog').getByText('费用开销与业务测试',{exact:true}).click();
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:900});
      await page.locator('#history-cost').scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(output,`cost-business-${width}.png`)});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    const bundleEvent=page.waitForEvent('download');await page.locator('#history-bundle').click();
    assert.equal((await bundleEvent).suggestedFilename(),'delivery-archive-1.zip');
    await page.locator('#history-dialog').getByText('生成结果与重新预览',{exact:true}).click();
    await page.locator('#history-preview-start').click();
    await page.locator('#history-preview-link').waitFor({state:'visible'});
    await page.locator('#history-preview-stop').click();
    await page.waitForFunction(()=>document.getElementById('history-preview-link').hidden);
    await page.locator('#history-files summary').first().click();
    assert((await page.locator('#history-files pre').innerText()).includes('<main>作品集</main>'));
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:900});
      await page.screenshot({path:path.join(output,`history-detail-${width}.png`)});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    const historyDownloadEvent=page.waitForEvent('download');
    await page.locator('#history-download').click();
    const historyDownload=await historyDownloadEvent;
    assert.equal(JSON.parse(fs.readFileSync(await historyDownload.path(),'utf8')).id,'archive-1');
    await page.locator('#project-details').evaluate(el=>el.open=true);
    assert((await page.locator('#project-versions').innerText()).includes('版本 1'));
    await page.locator('#history-edit').click();
    assert(await page.locator('#revision-context').isVisible());
    assert((await page.locator('#revision-label').innerText()).includes('archive-1'));
    await page.locator('#revision-cancel').click();
    await page.locator('#delivery-mode').selectOption('demo');
    assert.equal(await page.locator('#revision-context').isVisible(),false);
    await page.locator('#open-history').click();
    await page.locator('.history-row').first().click();
    await page.locator('#history-dialog').waitFor({state:'visible'});
    await page.locator('#history-close').click();
    assert(await page.locator('#task-history').isVisible());
    await page.locator('#history-list-close').click();

    await page.locator('#idea').fill('建立我的中文作品集，保留所有原始要求。');
    await page.locator('#requirements').fill('中文界面\n\n  手机上也能使用  ');
    await page.locator('#start').click();
    await page.locator('#approval').waitFor({state: 'visible'});
    assert.deepEqual(submitted, {idea: '建立我的中文作品集，保留所有原始要求。', requirements: ['中文界面', '手机上也能使用']});
    assert(await page.locator('#plan').innerText().then(text => text.includes('个人作品集') && !text.includes('"core_features"')));
    await page.locator('#plan').getByText('查看技术方案', {exact: true}).click();
    await page.waitForTimeout(1650);
    assert(await page.locator('#plan details').last().getAttribute('open') !== null, 'poll collapsed technical details');
    // Model text must remain inert even when it contains HTML-like content.
    state.product_spec.core_features.push('<img src=x onerror="window.injected=true">');
    await page.waitForTimeout(1650);
    assert.equal(await page.locator('#plan img').count(), 0);
    assert.equal(await page.evaluate(() => window.injected), undefined);
    state.product_spec.core_features.pop();
    await page.waitForTimeout(1650);
    for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 960});
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({path: path.join(output, `approval-${width}.png`), fullPage: true});
      await page.locator('#execution').screenshot({path: path.join(output, `approval-detail-${width}.png`)});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'approval overflow');
    }
    const errorCount = errors.length;
    await page.locator('#feedback').fill('请补充项目详情页面');
    await page.locator('#reject').click();
    await page.locator('#error').filter({hasText: 'Failed to fetch'}).waitFor();
    assert(await page.locator('#reject').isEnabled(), 'failed decision cannot retry');
    await page.locator('#reject').click();
    await page.locator('#status').filter({hasText: '已拒绝'}).waitFor();
    assert.deepEqual(decision, {stage: 'plan', approved: false, feedback: '请补充项目详情页面'});
    assert(await page.locator('#start').isEnabled());
    await page.locator('#run-report > summary').click();
    const downloadEvent = page.waitForEvent('download');
    await page.locator('#download').click();
    const download = await downloadEvent;
    const report = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
    assert.equal(report.phase, 'plan_rejected');
    await page.locator('#open-history').click();
    await page.locator('#history-list .history-row').first().click();
    await page.locator('#project-meta').filter({hasText:'当前可用版本'}).waitFor({state:'attached'});
    await page.locator('#project-details').evaluate(el=>el.open=true);
    for(const width of [1440,390]){
      await page.setViewportSize({width,height:900});
      await page.screenshot({path:path.join(output,`project-versions-${width}.png`)});
    }
    await page.locator('#history-edit').click();
    await page.locator('#idea').fill('只修改页面标题，保留联系方式');
    await page.locator('#start').click();
    await page.waitForFunction(()=>document.getElementById('start').disabled===false);
    assert.equal(submitted.base_version,'archive-1');
    assert.equal(submitted.idea,'只修改页面标题，保留联系方式');
    await page.getByText('模型单价与费用口径',{exact:true}).click();
    await page.locator('#price-model').fill('test');await page.locator('#price-input').fill('2');await page.locator('#price-output').fill('8');
    await page.locator('#price-save').click();await page.locator('#price-status').filter({hasText:'已保存'}).waitFor();
    assert.equal(savedPrice.input_per_million,2);
    await page.locator('#open-history').click();await page.locator('#history-list').getByRole('button',{name:/中断的测试任务/}).click();
    await page.locator('#history-recover').click();await page.waitForFunction(()=>document.getElementById('history-dialog').open===false);
    assert.equal(recoveries,1);
    assert.equal(errorCount, 0, `Unexpected browser errors: ${errors.slice(0, errorCount)}`);
    console.log('PASS: 11 responsive sizes with caption separation, triangle cursor and particle decay, sculpture click/drag/keyboard, manual independent scroll/open/Escape/focus, touch, reduced motion, original instructions, readable approval, inert model text, decision retry, report download.');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
