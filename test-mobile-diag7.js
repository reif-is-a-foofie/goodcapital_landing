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

  // Wait for TOC to be fully hidden (after transition)
  await new Promise(function(r) { setTimeout(r, 500); });

  // Check various states
  const state = await page.evaluate(function() {
    var toc = document.getElementById('toc');
    var tocStyle = getComputedStyle(toc);
    var spanW = document.querySelector('#ch-genesis_1 span.w');
    var spanRect = spanW ? spanW.getBoundingClientRect() : null;
    var topEl = spanRect ? document.elementFromPoint(spanRect.left + spanRect.width/2, spanRect.top + spanRect.height/2) : null;
    var chTiles = Array.from(document.querySelectorAll('#toc-grid .chapter-tile'));
    var firstTileRect = chTiles.length ? chTiles[0].getBoundingClientRect() : null;

    return {
      tocClass: toc.className,
      tocWidth: tocStyle.width,
      tocOverflow: tocStyle.overflow,
      tocTransform: tocStyle.transform,
      spanRect: spanRect ? {x: spanRect.x, y: spanRect.y, w: spanRect.width, h: spanRect.height} : null,
      topElTag: topEl ? topEl.tagName : null,
      topElClass: topEl ? topEl.className : null,
      chapterTileCount: chTiles.length,
      firstTileRect: firstTileRect ? {x: firstTileRect.x, y: firstTileRect.y, w: firstTileRect.width, h: firstTileRect.height} : null,
    };
  });
  console.log('State after 500ms wait:', JSON.stringify(state, null, 2));

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
