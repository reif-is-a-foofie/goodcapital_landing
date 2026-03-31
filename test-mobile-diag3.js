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

  // Check what's blocking clicks
  const diag = await page.evaluate(function() {
    var tile = document.querySelector('.toc-tile[data-action="scripture-root"]');
    var rect = tile.getBoundingClientRect();
    var centerX = rect.left + rect.width / 2;
    var centerY = rect.top + rect.height / 2;
    var topEl = document.elementFromPoint(centerX, centerY);

    // Check all ancestors of the tile
    var parents = [];
    var el = tile;
    while (el) {
      var style = getComputedStyle(el);
      parents.push({
        tag: el.tagName,
        id: el.id,
        classes: el.className,
        pointerEvents: style.pointerEvents,
        display: style.display,
        visibility: style.visibility,
        zIndex: style.zIndex,
        position: style.position,
        overflow: style.overflow,
      });
      el = el.parentElement;
      if (parents.length > 10) break;
    }

    return {
      tileRect: rect,
      centerX: centerX,
      centerY: centerY,
      topElAtCenter: topEl ? { tag: topEl.tagName, id: topEl.id, classes: topEl.className } : null,
      parents: parents,
      windowInnerWidth: window.innerWidth,
      windowInnerHeight: window.innerHeight,
    };
  });
  console.log('Diagnostics:', JSON.stringify(diag, null, 2));

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
