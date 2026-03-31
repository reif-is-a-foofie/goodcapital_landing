const puppeteer = require('puppeteer');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function openSearch(page, query) {
  await page.click('#search-btn');
  await page.waitForFunction(() => document.querySelector('#search-panel').classList.contains('open'));
  await page.$eval('#search-input', (el) => {
    el.value = '';
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await page.type('#search-input', query);
  await page.waitForFunction(() => document.querySelectorAll('.search-result').length > 0, { timeout: 20000 });
  return page.$$eval('.search-result', (els) =>
    els.slice(0, 5).map((el) => ({
      kind: el.dataset.kind || '',
      ref: el.querySelector('.search-result-ref')?.textContent.trim() || '',
      text: el.querySelector('.search-result-text')?.textContent.trim() || '',
    }))
  );
}

async function closeSearch(page) {
  await page.click('#search-close');
  await page.waitForFunction(() => !document.querySelector('#search-panel').classList.contains('open'));
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

  const john = await openSearch(page, 'John 3:16');
  assert(john[0].kind === 'verse', 'John 3:16 did not rank a scripture verse first');
  assert(/John 3:16/.test(john[0].ref), 'John 3:16 did not return the exact verse first');
  await closeSearch(page);

  const best = await openSearch(page, 'Good Better Best');
  assert(best[0].kind === 'source', 'Good Better Best did not rank a source first');
  assert(/Good, Better, Best/.test(best[0].ref), 'Good Better Best did not return the expected General Conference talk first');
  await page.$eval('.search-result', (el) => el.click());
  await page.waitForFunction(() =>
    document.querySelector('.source-doc .source-title')?.textContent?.trim() === 'Good, Better, Best',
    { timeout: 20000 }
  );
  await page.waitForFunction(() => document.querySelectorAll('.source-doc span.w').length > 0, { timeout: 30000 });
  const sourceState = await page.evaluate(() => ({
    title: document.querySelector('.source-doc .source-title')?.textContent.trim() || '',
    subtitle: document.querySelector('.source-doc .source-subtitle')?.textContent.trim() || '',
    location: document.querySelector('#location-label')?.textContent.trim() || '',
    cwCount: document.querySelectorAll('.source-doc span.w').length,
  }));
  assert(sourceState.title === 'Good, Better, Best', 'Source search result did not open the source document');
  assert(sourceState.cwCount > 0, 'Source search result did not render clickable source words');

  const enuma = await openSearch(page, 'Enuma Elish');
  assert(enuma[0].kind === 'source', 'Enuma Elish did not rank a source first');
  assert(/Enuma Elish/.test(enuma[0].ref), 'Enuma Elish did not return the expected ancient text first');
  await closeSearch(page);

  const chapter = await openSearch(page, '1 Nephi 8');
  assert(chapter[0].kind === 'verse', '1 Nephi 8 did not rank a scripture verse first');
  assert(/^1 Nephi 8:/.test(chapter[0].ref), '1 Nephi 8 did not return the correct chapter first');
  await closeSearch(page);

  console.log(JSON.stringify({
    john,
    best,
    sourceState,
    enuma,
  }, null, 2));
  await browser.close();
}

run().catch(async (error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
