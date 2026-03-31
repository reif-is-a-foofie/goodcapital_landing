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

  // Add event monitoring
  await page.evaluate(function() {
    var tile = document.querySelector('.toc-tile[data-action="scripture-root"]');
    if (tile) {
      tile.addEventListener('click', function(e) {
        console.log('TILE CLICK fired, target:', e.target.tagName, e.target.dataset.action);
      });
      tile.addEventListener('touchstart', function(e) {
        console.log('TILE TOUCHSTART fired');
      });
      tile.addEventListener('touchend', function(e) {
        console.log('TILE TOUCHEND fired');
      });
      console.log('Tile found and listeners added, rect:', JSON.stringify(tile.getBoundingClientRect()));
    } else {
      console.log('ERROR: tile not found');
    }

    // Monitor the grid click listener
    var grid = document.getElementById('toc-grid');
    grid.addEventListener('click', function(e) {
      console.log('GRID CLICK fired, target:', e.target.tagName, 'action:', e.target.closest('.toc-tile') ? e.target.closest('.toc-tile').dataset.action : 'none');
    }, true);
  });

  console.log('Tapping scripture-root tile...');
  await page.tap('.toc-tile[data-action="scripture-root"]');

  await new Promise(function(r) { setTimeout(r, 2000); });

  // Try direct click
  console.log('Trying direct click...');
  await page.click('.toc-tile[data-action="scripture-root"]');
  await new Promise(function(r) { setTimeout(r, 2000); });

  const afterClick = await page.evaluate(function() {
    return {
      subtitle: document.querySelector('#toc-subtitle') ? document.querySelector('#toc-subtitle').textContent : null,
      tileCount: document.querySelectorAll('#toc-grid .toc-tile').length,
    };
  });
  console.log('After click:', JSON.stringify(afterClick));

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
