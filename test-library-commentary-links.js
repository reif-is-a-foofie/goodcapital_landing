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
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 1 });
  await page.goto('http://127.0.0.1:4173/library/index.html', {
    waitUntil: 'networkidle0',
    timeout: 60000,
  });

  await page.waitForSelector('#splash.gone', { timeout: 60000 });
  await page.waitForSelector('#toc-grid .toc-tile', { timeout: 10000 });

  await page.click('.toc-tile[data-action="scripture-root"]');
  await page.waitForFunction(() => document.querySelector('#toc-subtitle')?.textContent === 'The Holy Scriptures');
  await page.click('.toc-tile[data-action="volume"][data-volume="Old Testament"]');
  await page.waitForFunction(() => document.querySelector('#toc-subtitle')?.textContent === 'Old Testament');
  await page.click('.toc-tile[data-action="book"][data-book="Genesis"]');
  await page.waitForFunction(() => document.querySelector('#toc-subtitle')?.textContent === 'Genesis');
  await page.click('.toc-tile[data-action="chapter"][data-id="genesis_1"]');

  await page.waitForSelector('#ch-genesis_1', { timeout: 20000 });
  await page.$eval('#ch-genesis_1', (el) => el.scrollIntoView({ block: 'start' }));
  await page.waitForFunction(() => {
    const verse = document.querySelector('#ch-genesis_1 .verse[id="v1"]');
    return !!verse && !!verse.querySelector('.ref-link');
  }, { timeout: 30000 });

  const commentaryState = await page.$eval('#ch-genesis_1 .verse[id="v1"]', (verse) => {
    const block = verse.querySelector('.lds-commentary-block, .donaldson-block, .semantic-quote');
    const style = block ? getComputedStyle(block) : null;
    return {
      hasBlock: !!block,
      borderRadius: style ? style.borderRadius : '',
      backgroundColor: style ? style.backgroundColor : '',
      firstRefText: verse.querySelector('.ref-link')?.textContent?.trim() || '',
    };
  });
  assert(commentaryState.hasBlock, 'commentary block did not load');
  assert(commentaryState.firstRefText.length > 0, 'commentary reference link did not render');

  await page.$eval('#ch-genesis_1 .verse[id="v1"] .ref-link', (el) => el.click());
  await page.waitForFunction(() => {
    const label = document.querySelector('#location-label')?.textContent || '';
    return /Genesis · 1/.test(label) || !!document.querySelector('#ch-genesis_1 .verse.verse-focus');
  }, { timeout: 15000 });

  const navState = await page.evaluate(() => ({
    location: document.querySelector('#location-label')?.textContent?.trim() || '',
    focusedVerse: document.querySelector('.verse.verse-focus')?.id || '',
  }));

  assert(navState.focusedVerse === 'v1', 'commentary reference did not focus the linked scripture verse');

  console.log(JSON.stringify({ commentaryState, navState }, null, 2));
  await browser.close();
}

run().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
