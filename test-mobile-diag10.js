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

  // Get span.w rect and tap manually at its center
  const spanInfo = await page.evaluate(function() {
    var span = document.querySelector('#ch-genesis_1 span.w');
    var rect = span.getBoundingClientRect();
    return { x: rect.x, y: rect.y, w: rect.width, h: rect.height, cx: rect.x + rect.width/2, cy: rect.y + rect.height/2 };
  });
  console.log('span.w rect:', JSON.stringify(spanInfo));

  // Monitor touch events
  await page.evaluate(function() {
    document.addEventListener('touchstart', function(e) {
      var t = e.touches[0];
      var el = document.elementFromPoint(t.clientX, t.clientY);
      console.log('TOUCHSTART: clientX=' + t.clientX + ' clientY=' + t.clientY + ' pageX=' + t.pageX + ' pageY=' + t.pageY + ' el=' + (el ? el.tagName + '.' + el.className.substring(0,20) : 'null'));
    }, true);
    document.addEventListener('click', function(e) {
      console.log('CLICK: clientX=' + e.clientX + ' clientY=' + e.clientY + ' target=' + e.target.tagName + '.' + e.target.className.substring(0,20));
    }, true);
  });

  // Tap using Puppeteer's touchscreen API directly
  console.log('Tapping at span center coords:', spanInfo.cx, spanInfo.cy);
  await page.touchscreen.tap(spanInfo.cx, spanInfo.cy);
  await new Promise(function(r) { setTimeout(r, 2000); });

  const state = await page.evaluate(function() {
    return document.getElementById('channel').classList.contains('open');
  });
  console.log('Channel open:', state);

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
