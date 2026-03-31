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
  await page.waitForSelector('#toc-grid .toc-tile', { timeout: 10000 });

  const state = await page.evaluate(function() {
    var tiles = Array.from(document.querySelectorAll('#toc-grid .toc-tile'));
    return {
      subtitle: document.querySelector('#toc-subtitle') ? document.querySelector('#toc-subtitle').textContent : null,
      tileCount: tiles.length,
      tiles: tiles.map(function(t) { return { action: t.dataset.action, text: t.textContent.trim().substring(0, 30) }; })
    };
  });
  console.log('Initial state:', JSON.stringify(state, null, 2));

  console.log('Tapping scripture-root tile...');
  await page.tap('.toc-tile[data-action="scripture-root"]');

  await new Promise(function(r) { setTimeout(r, 3000); });

  const afterTap = await page.evaluate(function() {
    return {
      subtitle: document.querySelector('#toc-subtitle') ? document.querySelector('#toc-subtitle').textContent : null,
      tileCount: document.querySelectorAll('#toc-grid .toc-tile').length,
    };
  });
  console.log('After tap:', JSON.stringify(afterTap));

  await browser.close();
}
run().catch(function(e) { console.error(e.message); process.exit(1); });
