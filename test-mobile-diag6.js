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

  // Check toc state after chapter tap
  const tocState = await page.evaluate(function() {
    var toc = document.getElementById('toc');
    var style = getComputedStyle(toc);
    return {
      classes: toc.className,
      width: style.width,
      display: style.display,
      visibility: style.visibility,
      left: style.left,
      zIndex: style.zIndex,
    };
  });
  console.log('TOC state after chapter load:', JSON.stringify(tocState));

  // Check the channel area
  const channelState = await page.evaluate(function() {
    var channel = document.getElementById('channel');
    var style = getComputedStyle(channel);
    return {
      classes: channel.className,
      top: style.top,
      right: style.right,
      left: style.left,
      width: style.width,
      height: style.height,
      transform: style.transform,
      zIndex: style.zIndex,
    };
  });
  console.log('Channel state:', JSON.stringify(channelState));

  // Check toc-grid chapter tiles' position
  const chapterTileState = await page.evaluate(function() {
    var tiles = Array.from(document.querySelectorAll('#toc-grid .chapter-tile'));
    if (tiles.length === 0) return { count: 0 };
    var t = tiles[0];
    var rect = t.getBoundingClientRect();
    return {
      count: tiles.length,
      firstTileRect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
    };
  });
  console.log('Chapter tiles state:', JSON.stringify(chapterTileState));

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
