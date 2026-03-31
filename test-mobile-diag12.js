const puppeteer = require('puppeteer');
async function run() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });

  page.on('console', msg => console.log('BROWSER:', msg.text()));

  await page.goto('http://127.0.0.1:4173/library/index.html', { waitUntil: 'networkidle0', timeout: 60000 });
  await page.waitForSelector('#splash.gone', { timeout: 60000 });

  await page.tap('#toc-btn');
  await page.waitForSelector('#toc-grid .toc-tile', { timeout: 10000 });
  await page.tap('.toc-tile[data-action="scripture-root"]');
  await page.waitForFunction(function() { return document.querySelector('#toc-subtitle').textContent === 'The Holy Scriptures'; }, { timeout: 5000 });
  await page.tap('.toc-tile[data-action="volume"][data-volume="Old Testament"]');
  await page.waitForFunction(function() { return document.querySelector('#toc-subtitle').textContent === 'Old Testament'; }, { timeout: 5000 });
  await page.tap('.toc-tile[data-action="book"][data-book="Genesis"]');
  await page.waitForFunction(function() { return document.querySelector('#toc-subtitle').textContent === 'Genesis'; }, { timeout: 5000 });
  await page.tap('.toc-tile[data-action="chapter"][data-id="genesis_1"]');

  await page.waitForSelector('#ch-genesis_1', { timeout: 20000 });
  await page.waitForSelector('#ch-genesis_1 span.w', { timeout: 20000 });

  const diag = await page.evaluate(function() {
    var span = document.querySelector('#ch-genesis_1 span.w');
    var rect = span.getBoundingClientRect();
    var cx = rect.left + rect.width / 2;
    var cy = rect.top + rect.height / 2;

    var elAtCenter = document.elementFromPoint(cx, cy);

    // Check graph-panel
    var graph = document.getElementById('graph-panel');
    var graphStyle = getComputedStyle(graph);

    // Check all elements at center point
    var els = document.elementsFromPoint(cx, cy);

    return {
      spanRect: { top: rect.top, bottom: rect.bottom, cx: cx, cy: cy },
      elAtCenter: elAtCenter ? elAtCenter.id + '.' + elAtCenter.className.substring(0,20) : 'null',
      graphClass: graph ? graph.className : 'N/A',
      graphPointerEvents: graphStyle.pointerEvents,
      graphTransform: graphStyle.transform,
      graphDisplay: graphStyle.display,
      allEls: els.map(function(el) { return el.tagName + '#' + el.id + '.' + el.className.substring(0,20); })
    };
  });
  console.log('Diagnostics:', JSON.stringify(diag, null, 2));

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
