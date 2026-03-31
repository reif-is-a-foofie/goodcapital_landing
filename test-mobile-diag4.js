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

  // Open TOC on mobile
  console.log('Opening TOC...');
  await page.tap('#toc-btn');
  await page.waitForSelector('#toc-grid .toc-tile', { timeout: 10000 });

  console.log('Tapping scripture-root...');
  await page.tap('.toc-tile[data-action="scripture-root"]');

  try {
    await page.waitForFunction(function() { return document.querySelector('#toc-subtitle') && document.querySelector('#toc-subtitle').textContent === 'The Holy Scriptures'; }, { timeout: 5000 });
    console.log('SUCCESS: subtitle = The Holy Scriptures');
  } catch(e) {
    var sub = await page.evaluate(function() { return document.querySelector('#toc-subtitle') ? document.querySelector('#toc-subtitle').textContent : 'NOT FOUND'; });
    console.log('FAILED: subtitle =', sub);
  }

  console.log('Tapping Old Testament...');
  await page.tap('.toc-tile[data-action="volume"][data-volume="Old Testament"]');
  try {
    await page.waitForFunction(function() { return document.querySelector('#toc-subtitle') && document.querySelector('#toc-subtitle').textContent === 'Old Testament'; }, { timeout: 5000 });
    console.log('SUCCESS: subtitle = Old Testament');
  } catch(e) {
    var sub = await page.evaluate(function() { return document.querySelector('#toc-subtitle') ? document.querySelector('#toc-subtitle').textContent : 'NOT FOUND'; });
    console.log('FAILED: subtitle =', sub);
  }

  console.log('Tapping Genesis...');
  await page.tap('.toc-tile[data-action="book"][data-book="Genesis"]');
  try {
    await page.waitForFunction(function() { return document.querySelector('#toc-subtitle') && document.querySelector('#toc-subtitle').textContent === 'Genesis'; }, { timeout: 5000 });
    console.log('SUCCESS: subtitle = Genesis');
  } catch(e) {
    var sub = await page.evaluate(function() { return document.querySelector('#toc-subtitle') ? document.querySelector('#toc-subtitle').textContent : 'NOT FOUND'; });
    console.log('FAILED: subtitle =', sub);
  }

  console.log('Tapping Genesis 1...');
  await page.tap('.toc-tile[data-action="chapter"][data-id="genesis_1"]');

  await page.waitForSelector('#ch-genesis_1', { timeout: 20000 });
  await page.waitForSelector('#ch-genesis_1 span.w', { timeout: 20000 });
  console.log('Chapter loaded!');

  console.log('Tapping word...');
  await page.tap('#ch-genesis_1 span.w');
  try {
    await page.waitForFunction(function() { return document.querySelector('#channel') && document.querySelector('#channel').classList.contains('open'); }, { timeout: 15000 });
    console.log('SUCCESS: channel is open!');
  } catch(e) {
    console.log('FAILED: channel did not open');
  }

  await browser.close();
}
run().catch(function(e) { console.error(e.stack || e.message); process.exit(1); });
