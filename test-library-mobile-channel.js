const puppeteer = require('puppeteer');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function run() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox'],
  });

  const page = await browser.newPage();
  await page.setViewport({
    width: 390,
    height: 844,
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  });

  await page.goto('http://127.0.0.1:4173/library/index.html', {
    waitUntil: 'networkidle0',
    timeout: 60000,
  });

  await page.waitForSelector('#splash.gone', { timeout: 60000 });

  // On mobile (<900px) the TOC panel starts hidden; open it via the hamburger button.
  await page.tap('#toc-btn');
  await page.waitForSelector('#toc-grid .toc-tile', { timeout: 10000 });

  await page.tap('.toc-tile[data-action="scripture-root"]');
  await page.waitForFunction(() => document.querySelector('#toc-subtitle')?.textContent === 'The Holy Scriptures');
  await page.tap('.toc-tile[data-action="volume"][data-volume="Old Testament"]');
  await page.waitForFunction(() => document.querySelector('#toc-subtitle')?.textContent === 'Old Testament');
  await page.tap('.toc-tile[data-action="book"][data-book="Genesis"]');
  await page.waitForFunction(() => document.querySelector('#toc-subtitle')?.textContent === 'Genesis');
  await page.tap('.toc-tile[data-action="chapter"][data-id="genesis_1"]');

  await page.waitForSelector('#ch-genesis_1', { timeout: 20000 });
  await page.waitForSelector('#ch-genesis_1 span.w', { timeout: 20000 });
  await page.tap('#ch-genesis_1 span.w');
  await page.waitForFunction(() => document.querySelector('#channel')?.classList.contains('open'), { timeout: 15000 });

  const initial = await page.evaluate(() => {
    const list = document.querySelector('#ch-list');
    const channel = document.querySelector('#channel');
    const style = getComputedStyle(list);
    return {
      channelOpen: channel.classList.contains('open'),
      count: document.querySelectorAll('#channel .ch-morsel').length,
      clientHeight: list.clientHeight,
      scrollHeight: list.scrollHeight,
      overflowY: style.overflowY,
      touchAction: style.touchAction,
      webkitOverflowScrolling: style.webkitOverflowScrolling,
    };
  });

  assert(initial.channelOpen, 'mobile channel did not open');
  assert(initial.count > 3, 'mobile channel did not render enough references to test scrolling');
  assert(initial.scrollHeight > initial.clientHeight, 'mobile channel list is not scrollable');
  assert(initial.overflowY === 'auto', 'mobile channel list overflow-y is not auto');

  const scrolled = await page.evaluate(() => {
    const list = document.querySelector('#ch-list');
    list.scrollTop = 0;
    list.scrollBy({ top: 400, behavior: 'instant' });
    return {
      scrollTop: list.scrollTop,
      maxScroll: list.scrollHeight - list.clientHeight,
    };
  });

  assert(scrolled.maxScroll > 0, 'mobile channel max scroll is not positive');
  assert(scrolled.scrollTop > 0, 'mobile channel list did not move when scrolled');

  console.log(JSON.stringify({ initial, scrolled }, null, 2));
  await browser.close();
}

run().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
