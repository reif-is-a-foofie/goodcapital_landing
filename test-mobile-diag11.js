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

  // Investigate hit testing at various y coordinates around span.w
  const hitTest = await page.evaluate(function() {
    var span = document.querySelector('#ch-genesis_1 span.w');
    var rect = span.getBoundingClientRect();
    var cx = rect.left + rect.width / 2;
    var results = [];
    // Test various y values
    for (var y = rect.top - 5; y <= rect.bottom + 5; y += 2) {
      var el = document.elementFromPoint(cx, y);
      results.push({ y: Math.round(y*10)/10, el: el ? el.tagName + '.' + el.className.substring(0,25) : 'null' });
    }
    return {
      spanRect: { top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right, cx: cx },
      hitTests: results
    };
  });
  console.log('Hit tests:', JSON.stringify(hitTest, null, 2));

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
