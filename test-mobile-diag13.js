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

  // Monitor click events and what we can find
  await page.evaluate(function() {
    document.addEventListener('click', function(e) {
      var fromPoint = document.elementFromPoint(e.clientX, e.clientY);
      var spanW = fromPoint ? fromPoint.closest('span.w') : null;

      // Try finding nearest span.w by distance from click
      var allSpanW = Array.from(document.querySelectorAll('.chapter-block span.w'));
      var nearest = null;
      var minDist = Infinity;
      allSpanW.forEach(function(s) {
        var r = s.getBoundingClientRect();
        var cx = r.left + r.width/2;
        var cy = r.top + r.height/2;
        var dist = Math.sqrt(Math.pow(e.clientX - cx, 2) + Math.pow(e.clientY - cy, 2));
        if (dist < minDist) { minDist = dist; nearest = s; }
      });

      console.log('CLICK: target=' + e.target.tagName + '.' + e.target.className.substring(0,20) +
        ' coords=(' + e.clientX + ',' + e.clientY + ')' +
        ' fromPoint=' + (fromPoint ? fromPoint.tagName + '.' + fromPoint.className.substring(0,20) : 'null') +
        ' spanW_via_closest=' + (spanW ? spanW.dataset.st : 'null') +
        ' nearest_w=' + (nearest ? nearest.dataset.st + ' dist=' + Math.round(minDist) : 'null')
      );
    }, true);
  });

  console.log('Tapping span.w...');
  await page.tap('#ch-genesis_1 span.w');
  await new Promise(function(r) { setTimeout(r, 2000); });

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
