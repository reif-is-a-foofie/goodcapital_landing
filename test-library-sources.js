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
  await page.waitForSelector('#toc:not(.hidden)', { timeout: 10000 });
  await page.waitForSelector('#toc-grid .toc-tile', { timeout: 10000 });

  const rootTiles = await page.$$eval('#toc-grid .toc-tile .toc-tile-title', (els) =>
    els.map((el) => el.textContent.trim())
  );
  assert(rootTiles.includes('Journal of Discourses'), 'Journal of Discourses missing from TOC root');
  assert(rootTiles.includes('History of the Church'), 'History of the Church missing from TOC root');
  assert(rootTiles.includes('General Conference'), 'General Conference missing from TOC root');

  await page.click('.toc-tile[data-action="source-collection"][data-collection="journal_of_discourses"]');
  await page.waitForFunction(() =>
    document.querySelector('#toc-title').textContent === 'Sources' &&
    document.querySelector('#toc-subtitle').textContent === 'Journal of Discourses'
  );

  await page.click('.toc-tile[data-action="source-doc"][data-doc="journal_of_discourses:vol_01"]');
  await page.waitForSelector('.source-doc .source-title', { timeout: 20000 });

  const sourceState = await page.evaluate(() => ({
    title: document.querySelector('.source-doc .source-title')?.textContent.trim(),
    location: document.querySelector('#location-label')?.textContent.trim(),
    activeTile: document.querySelector('.toc-tile.active .toc-tile-title')?.textContent.trim(),
    paragraphs: document.querySelectorAll('.source-doc .source-para').length,
  }));

  assert(sourceState.title === 'Journal of Discourses Vol. 1', 'source title did not load');
  assert(sourceState.location === 'Journal of Discourses · Journal of Discourses Vol. 1', 'source location label mismatch');
  assert(sourceState.activeTile === 'Journal of Discourses Vol. 1', 'source tile did not become active');
  assert(sourceState.paragraphs > 50, 'source document rendered too few paragraphs');

  await page.click('#toc-back');
  await page.waitForFunction(() => document.querySelector('#toc-title').textContent === 'Contents');
  await page.click('.toc-tile[data-action="volume"][data-volume="New Testament"]');
  await page.click('.toc-tile[data-action="book"][data-book="John"]');
  await page.click('.toc-tile[data-action="chapter"][data-id="john_3"]');
  await page.waitForSelector('#ch-john_3', { timeout: 20000 });

  const scriptureState = await page.evaluate(() => ({
    sourceVisible: !!document.querySelector('.source-doc'),
    chapterVisible: !!document.querySelector('#ch-john_3'),
    location: document.querySelector('#location-label')?.textContent.trim(),
    tocSubtitle: document.querySelector('#toc-subtitle')?.textContent.trim(),
  }));

  assert(!scriptureState.sourceVisible, 'source reader remained visible after returning to scripture');
  assert(scriptureState.chapterVisible, 'John 3 did not render after switching back from source');
  assert(scriptureState.location === 'John · 3', 'scripture location label did not recover after source view');
  assert(scriptureState.tocSubtitle === 'John', 'TOC did not return to scripture chapter view');

  console.log(JSON.stringify({ rootTiles, sourceState, scriptureState }, null, 2));
  await browser.close();
}

run().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
