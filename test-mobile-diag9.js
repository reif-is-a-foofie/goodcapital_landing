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
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

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

  // Monitor click events with detailed info
  await page.evaluate(function() {
    document.addEventListener('click', function(e) {
      var fromPoint = document.elementFromPoint(e.clientX, e.clientY);
      console.log('CLICK: target=' + e.target.tagName + '.' + e.target.className.substring(0,20) +
        ' clientX=' + e.clientX + ' clientY=' + e.clientY +
        ' fromPoint=' + (fromPoint ? fromPoint.tagName + '.' + fromPoint.className.substring(0,20) : 'null') +
        ' spanW_from_point=' + (fromPoint ? !!fromPoint.closest('span.w') : false));
    }, true);
  });

  console.log('Tapping span.w...');
  await page.tap('#ch-genesis_1 span.w');
  await new Promise(function(r) { setTimeout(r, 2000); });

  const state = await page.evaluate(function() {
    return {
      channelOpen: document.getElementById('channel').classList.contains('open'),
    };
  });
  console.log('Channel state:', JSON.stringify(state));

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
