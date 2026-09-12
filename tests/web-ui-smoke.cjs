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
      phase: 'plan_done', errors: [], build_dir: null, acceptance_report: null,
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
    await page.route('**/api/**', async route => {
      const request = route.request();
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
    await page.waitForTimeout(1800);
    for (const [width, height] of [[1440, 960], [1024, 900], [768, 1024], [390, 844]]) {
      await page.setViewportSize({width, height});
      await page.evaluate(() => scrollTo(0, 0));
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}px overflow`);
      assert(await page.evaluate(() => [...document.images].every(image => image.complete && image.naturalWidth > 0)), 'missing artwork');
      await page.screenshot({path: path.join(output, `page-${width}.png`), fullPage: true});
    }
    await page.setViewportSize({width: 1440, height: 960});
    await page.locator('.scene-button').nth(1).click();
    assert.equal(await page.locator('.scene-button').nth(1).getAttribute('aria-pressed'), 'true');
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('.scene-button').nth(2).getAttribute('aria-pressed'), 'true');
    await page.keyboard.press('Home');
    assert.equal(await page.locator('.scene-button').first().getAttribute('aria-pressed'), 'true');
    await page.emulateMedia({reducedMotion: 'reduce'});
    await page.mouse.move(1200, 200);
    assert.equal(await page.locator('.art-parallax').evaluate(el => getComputedStyle(el).transform), 'none');
    assert.equal(await page.locator('.scene').first().evaluate(el => getComputedStyle(el).transitionDuration), '0s');

    await page.locator('#idea').fill('建立我的中文作品集，保留所有原始要求。');
    await page.locator('#requirements').fill('中文界面\n\n  手机上也能使用  ');
    await page.locator('#start').click();
    await page.locator('#approval').waitFor({state: 'visible'});
    assert.deepEqual(submitted, {idea: '建立我的中文作品集，保留所有原始要求。', requirements: ['中文界面', '手机上也能使用']});
    assert(await page.locator('#plan').innerText().then(text => text.includes('个人作品集') && !text.includes('"core_features"')));
    await page.getByText('查看技术方案', {exact: true}).click();
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
    assert.equal(errorCount, 0, `Unexpected browser errors: ${errors.slice(0, errorCount)}`);
    console.log('PASS: 4 responsive sizes, artwork, scene keyboard controls, reduced motion, original instructions, readable approval, inert model text, decision retry, report download.');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
