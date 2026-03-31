const puppeteer = require('puppeteer');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function existsVisible(page, selector) {
  return page.$eval(selector, (el) => {
    const style = getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden';
  });
}

async function run() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 1 });
  await page.goto('http://127.0.0.1:4173/library/index.html', {
    waitUntil: 'networkidle0',
    timeout: 60000,
  });

  const results = [];
  const pass = (name, details = '') => results.push({ name, ok: true, details });

  await page.waitForSelector('#splash.gone', { timeout: 60000 });
  await page.waitForSelector('#toc:not(.hidden)', { timeout: 10000 });
  await page.waitForSelector('#toc-grid .toc-tile', { timeout: 10000 });
  pass('initial load', 'reader and tile nav rendered');

  await page.click('#toc-btn');
  await page.waitForFunction(() => document.querySelector('#toc').classList.contains('hidden'));
  await page.click('#toc-btn');
  await page.waitForFunction(() => !document.querySelector('#toc').classList.contains('hidden'));
  pass('toc button', 'closes and reopens sidebar');

  const downloadHref = await page.$eval('#dl-btn', (el) => el.getAttribute('href'));
  assert(downloadHref === './LDS_Scriptures_Enriched.epub', 'download link href changed');
  pass('download button', downloadHref);

  await page.click('.toc-tile[data-action="volume"][data-volume="Old Testament"]');
  await page.waitForFunction(() => document.querySelector('#toc-title').textContent === 'Books');
  pass('volume tile', 'Old Testament opens books view');

  await page.click('.toc-tile[data-action="book"][data-book="Genesis"]');
  await page.waitForFunction(() => document.querySelector('#toc-title').textContent === 'Chapters' && document.querySelector('#toc-subtitle').textContent === 'Genesis');
  pass('book tile', 'Genesis opens chapters view');

  await page.click('.toc-tile[data-action="chapter"][data-id="genesis_1"]');
  await page.waitForSelector('#ch-genesis_1', { timeout: 20000 });
  pass('genesis tile', 'Genesis 1 loads from tile click');

  await page.$eval('#toc-back', (el) => el.click());
  await page.waitForFunction(() => document.querySelector('#toc-title').textContent === 'Books');
  await page.$eval('#toc-back', (el) => el.click());
  await page.waitForFunction(() => document.querySelector('#toc-title').textContent === 'Contents');
  await page.click('.toc-tile[data-action="volume"][data-volume="New Testament"]');
  await page.waitForFunction(() => document.querySelector('#toc-subtitle').textContent === 'New Testament');
  await page.click('.toc-tile[data-action="book"][data-book="Matthew"]');
  await page.waitForFunction(() => document.querySelector('#toc-subtitle').textContent === 'Matthew');
  await page.click('.toc-tile[data-action="chapter"][data-id="matthew_28"]');
  await page.waitForSelector('#ch-matthew_28', { timeout: 20000 });
  pass('chapter tile', 'Matthew 28 loads from tile click');

  await page.$eval('#ch-genesis_1', (el) => el.scrollIntoView({ block: 'center' }));
  await page.waitForFunction(() => {
    const chapter = document.querySelector('#ch-genesis_1');
    if (!chapter) return false;
    return !!chapter.querySelector('.lds-commentary-block, .etymology-block, .semantic-quote, .jst-block, .donaldson-block');
  }, { timeout: 30000 });
  await page.click('#ch-genesis_1 .verse');
  await page.waitForFunction(() => document.querySelector('#ch-genesis_1 .verse.expanded'));
  pass('notes lazy-load', 'commentary blocks present for Genesis 1');

  const filterChecks = [
    { key: 'scripture', hidden: ['.jst-block', '.donaldson-block', '.etymology-block', '.lds-commentary-block', '.semantic-quote'] },
    { key: 'jst', visible: '.jst-block', hidden: ['.donaldson-block'] },
    { key: 'donaldson', visible: '.donaldson-block', hidden: ['.jst-block'] },
    { key: 'wordstudy', visible: '.etymology-block', hidden: ['.jst-block'] },
    { key: 'sources', visible: '.lds-commentary-block', hidden: ['.jst-block'] },
    { key: 'connections', visible: '.semantic-quote', hidden: ['.jst-block'] },
  ];

  for (const spec of filterChecks) {
    await page.click(`.filter-pill[data-filter="${spec.key}"]`);
    await sleep(200);
    const filterState = await page.evaluate((spec) => {
      const displayStates = (selector) => Array.from(document.querySelectorAll(selector)).map((el) => getComputedStyle(el).display);
      return {
        active: Array.from(document.querySelectorAll('.filter-pill.active')).map((el) => el.dataset.filter),
        filterStyle: document.querySelector('#filter-style')?.textContent || '',
        hidden: (spec.hidden || []).map(displayStates),
      };
    }, spec);
    assert(filterState.active.length === 1 && filterState.active[0] === spec.key, `${spec.key} pill did not become active`);
    spec.hidden.forEach((selector) => {
      assert(filterState.filterStyle.includes(selector), `${spec.key} filter-style does not include ${selector}`);
    });
    filterState.hidden.forEach((values, idx) => {
      if (values.length === 0) return;
      assert(values.every((value) => value === 'none'), `${spec.key} did not hide ${spec.hidden[idx]}`);
    });
    pass(`filter ${spec.key}`, JSON.stringify(filterState));
    await page.click('.filter-pill[data-filter="all"]');
    await sleep(120);
  }

  await page.click('#search-btn');
  await page.waitForFunction(() => document.querySelector('#search-panel').classList.contains('open'));
  await page.type('#search-input', 'light');
  await page.waitForFunction(() => document.querySelectorAll('.search-result').length > 0, { timeout: 15000 });
  await page.click('.search-result');
  await page.waitForFunction(() => !document.querySelector('#search-panel').classList.contains('open'), { timeout: 10000 });
  pass('search result click', 'navigates and closes search panel');

  await page.click('#search-btn');
  await page.waitForFunction(() => document.querySelector('#search-panel').classList.contains('open'));
  await page.click('#search-close');
  await page.waitForFunction(() => !document.querySelector('#search-panel').classList.contains('open'));
  pass('search close button', 'closes panel');

  await page.click('#graph-btn');
  await page.waitForFunction(() => document.querySelector('#graph-panel').classList.contains('open'), { timeout: 15000 });
  await sleep(300);
  const graphVisible = await existsVisible(page, '#graph-panel');
  assert(graphVisible, 'graph panel opened but is not visible');
  pass('graph button', 'opens graph panel');
  await page.click('#graph-close');
  await page.waitForFunction(() => !document.querySelector('#graph-panel').classList.contains('open'));
  pass('graph close button', 'closes graph panel');

  await page.$eval('#ch-genesis_1', (el) => el.scrollIntoView({ block: 'center' }));
  await sleep(200);
  await page.waitForSelector('#ch-genesis_1 span.w', { timeout: 20000 });
  await page.click('#ch-genesis_1 span.w');
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });
  pass('word click', 'opens channel panel');

  const expandButton = await page.$('.ch-expand');
  if (expandButton) {
    await expandButton.click();
    await page.waitForFunction(() => !!document.querySelector('.ch-full-text.open'), { timeout: 10000 });
    pass('channel expand button', 'expands long excerpt');
  } else {
    pass('channel expand button', 'no expandable excerpt for first word selection');
  }

  await page.$eval('#ch-close', (el) => el.click());
  await page.waitForFunction(() => !document.querySelector('#channel').classList.contains('open'));
  pass('channel close button', 'closes panel');

  console.log(JSON.stringify(results, null, 2));
  await browser.close();
}

run().catch(async (error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
