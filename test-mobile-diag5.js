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

  // Open TOC on mobile
  await page.tap('#toc-btn');
  await page.waitForSelector('#toc-grid .toc-tile', { timeout: 10000 });
  await page.tap('.toc-tile[data-action="scripture-root"]');
  await page.waitForFunction(function() { return document.querySelector('#toc-subtitle') && document.querySelector('#toc-subtitle').textContent === 'The Holy Scriptures'; }, { timeout: 5000 });
  await page.tap('.toc-tile[data-action="volume"][data-volume="Old Testament"]');
  await page.waitForFunction(function() { return document.querySelector('#toc-subtitle') && document.querySelector('#toc-subtitle').textContent === 'Old Testament'; }, { timeout: 5000 });
  await page.tap('.toc-tile[data-action="book"][data-book="Genesis"]');
  await page.waitForFunction(function() { return document.querySelector('#toc-subtitle') && document.querySelector('#toc-subtitle').textContent === 'Genesis'; }, { timeout: 5000 });
  await page.tap('.toc-tile[data-action="chapter"][data-id="genesis_1"]');

  await page.waitForSelector('#ch-genesis_1', { timeout: 20000 });
  await page.waitForSelector('#ch-genesis_1 span.w', { timeout: 20000 });
  console.log('Chapter loaded!');

  // Add event monitoring before tapping
  await page.evaluate(function() {
    var spanW = document.querySelector('#ch-genesis_1 span.w');
    if (!spanW) { console.log('NO span.w found'); return; }
    var rect = spanW.getBoundingClientRect();
    console.log('span.w rect:', JSON.stringify(rect));
    console.log('span.w stem:', spanW.dataset.st);
    spanW.addEventListener('click', function(e) {
      console.log('span.w click fired!');
    });
    // Check what's on top of it
    var topEl = document.elementFromPoint(rect.left + rect.width/2, rect.top + rect.height/2);
    console.log('element at center:', topEl ? topEl.tagName + '.' + topEl.className : 'null');

    // Check if channel is in DOM
    var channel = document.getElementById('channel');
    console.log('channel exists:', !!channel, 'open:', channel ? channel.classList.contains('open') : 'N/A');

    // Check if search.json is loaded (needed for openChannel)
    console.log('searchIndex type:', typeof window.searchIndex);
  });

  console.log('Tapping span.w...');
  await page.tap('#ch-genesis_1 span.w');

  await new Promise(function(r) { setTimeout(r, 3000); });

  const state = await page.evaluate(function() {
    var channel = document.getElementById('channel');
    return {
      channelOpen: channel ? channel.classList.contains('open') : null,
      channelClass: channel ? channel.className : null,
    };
  });
  console.log('After tap state:', JSON.stringify(state));

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
