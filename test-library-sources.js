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

  await page.$eval('.toc-tile[data-action="source-collection"][data-collection="journal_of_discourses"]', (el) => el.click());
  await page.waitForFunction(() =>
    document.querySelector('#toc-title').textContent === 'Sources' &&
    document.querySelector('#toc-subtitle').textContent === 'Journal of Discourses'
  );

  await page.$eval('.toc-tile[data-action="source-doc"][data-doc="journal_of_discourses:vol_01"]', (el) => el.click());
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

  await page.waitForSelector('.source-doc .source-para span.w', { timeout: 20000 });
  await page.$eval('.source-doc .source-para span.w', (el) => el.click());
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });

  const jdWordState = await page.evaluate(() => ({
    word: document.querySelector('#ch-word')?.textContent.trim(),
    morsels: document.querySelectorAll('.ch-morsel').length,
    firstSource: document.querySelector('.ch-morsel .ch-src-name')?.textContent.trim(),
  }));

  assert(jdWordState.word, 'JD word click did not set channel word');
  assert(jdWordState.morsels > 0, 'JD word click opened an empty channel');
  assert(jdWordState.firstSource, 'JD word click did not render channel sources');
  await page.$eval('#ch-close', (el) => el.click());
  await page.waitForFunction(() => !document.querySelector('#channel').classList.contains('open'));

  await page.$eval('#toc-back', (el) => el.click());
  await page.waitForFunction(() =>
    document.querySelector('#toc-title').textContent === 'Sources' &&
    document.querySelector('#toc-subtitle').textContent.trim() === ''
  );
  await page.$eval('.toc-tile[data-action="source-collection"][data-collection="history_of_church"]', (el) => el.click());
  await page.waitForFunction(() =>
    document.querySelector('#toc-title').textContent === 'Sources' &&
    document.querySelector('#toc-subtitle').textContent === 'History of the Church'
  );

  await page.$eval('.toc-tile[data-action="source-doc"][data-doc="history_of_church:vol1"]', (el) => el.click());
  await page.waitForSelector('.source-doc .source-title', { timeout: 20000 });
  await page.waitForSelector('.source-doc .source-para span.w', { timeout: 20000 });
  await page.$eval('.source-doc .source-para span.w', (el) => el.click());
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });

  const hocWordState = await page.evaluate(() => ({
    word: document.querySelector('#ch-word')?.textContent.trim(),
    morsels: document.querySelectorAll('.ch-morsel').length,
    firstSource: document.querySelector('.ch-morsel .ch-src-name')?.textContent.trim(),
    firstText: document.querySelector('.ch-morsel .ch-morsel-text')?.textContent.trim() || '',
  }));

  assert(hocWordState.word, 'HoC word click did not set channel word');
  assert(hocWordState.morsels > 0, 'HoC word click opened an empty channel');
  assert(hocWordState.firstSource, 'HoC word click did not render channel sources');
  assert(!/Deutschland/i.test(hocWordState.firstText), 'HoC regression returned unrelated Gutenberg text');
  await page.$eval('#ch-close', (el) => el.click());
  await page.waitForFunction(() => !document.querySelector('#channel').classList.contains('open'));

  await page.$eval('#toc-back', (el) => el.click());
  await page.waitForFunction(() =>
    document.querySelector('#toc-title').textContent === 'Sources' &&
    document.querySelector('#toc-subtitle').textContent.trim() === ''
  );
  await page.$eval('.toc-tile[data-action="volume"][data-volume="New Testament"]', (el) => el.click());
  await page.$eval('.toc-tile[data-action="book"][data-book="John"]', (el) => el.click());
  await page.$eval('.toc-tile[data-action="chapter"][data-id="john_3"]', (el) => el.click());
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

  await page.click('#v1');
  await page.waitForSelector('#v1 span.w', { timeout: 20000 });
  await page.evaluate(() => {
    const spans = Array.from(document.querySelectorAll('#v1 span.w'));
    const target = spans.find((el) => /pharisees?/i.test(el.textContent || '')) || spans[0];
    if (target) target.click();
  });
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });
  await page.waitForFunction(() => {
    return Array.from(document.querySelectorAll('.ch-morsel .ch-src-name')).some((el) =>
      /Journal of Discourses|General Conference|History of the Church/i.test(el.textContent || '')
    );
  }, { timeout: 15000 });

  const sourceMorselIndex = await page.evaluate(() => {
    const morsels = Array.from(document.querySelectorAll('.ch-morsel'));
    return morsels.findIndex((el) =>
      /Journal of Discourses|General Conference|History of the Church/i.test(
        el.querySelector('.ch-src-name')?.textContent || ''
      )
    );
  });
  assert(sourceMorselIndex >= 0, 'scripture word click did not surface a source morsel');

  await page.$eval(`.ch-morsel[data-idx="${sourceMorselIndex}"]`, (el) => el.click());
  await page.waitForSelector('.source-doc .source-title', { timeout: 20000 });
  await page.waitForFunction(() => {
    const focused = document.querySelector('.source-para-focus');
    return !!(focused && (focused.textContent || '').trim().length > 80);
  }, { timeout: 15000 });

  const scriptureToSourceState = await page.evaluate(() => ({
    sourceTitle: document.querySelector('.source-doc .source-title')?.textContent.trim(),
    location: document.querySelector('#location-label')?.textContent.trim(),
    previewHidden: document.querySelector('#morsel-preview')?.hidden,
    focusedText: document.querySelector('.source-para-focus')?.textContent.trim() || '',
  }));

  assert(scriptureToSourceState.sourceTitle, 'source morsel click did not open a source doc');
  assert(scriptureToSourceState.previewHidden, 'source morsel click fell back to the preview card');
  assert(scriptureToSourceState.focusedText.length > 80, 'source morsel click did not focus a relevant paragraph');

  await page.$eval('#toc-back', (el) => el.click());
  await page.$eval('.toc-tile[data-action="volume"][data-volume="New Testament"]', (el) => el.click());
  await page.$eval('.toc-tile[data-action="book"][data-book="John"]', (el) => el.click());
  await page.$eval('.toc-tile[data-action="chapter"][data-id="john_3"]', (el) => el.click());
  await page.waitForSelector('#ch-john_3', { timeout: 20000 });
  await page.click('#v1');
  await page.waitForSelector('#v1 span.w', { timeout: 20000 });
  await page.evaluate(() => {
    const spans = Array.from(document.querySelectorAll('#v1 span.w'));
    const target = spans.find((el) => /pharisees?/i.test(el.textContent || '')) || spans[0];
    if (target) target.click();
  });
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });

  const rankingState = await page.evaluate(() => ({
    word: document.querySelector('#ch-word')?.textContent.trim(),
    firstSource: document.querySelector('.ch-morsel .ch-src-name')?.textContent.trim() || '',
    morsels: Array.from(document.querySelectorAll('.ch-morsel')).slice(0, 3).map((el) => ({
      src: el.querySelector('.ch-src-name')?.textContent.trim() || '',
      text: el.querySelector('.ch-morsel-text')?.textContent.trim() || '',
    })),
  }));

  assert(rankingState.word === 'pharisee', 'ranking regression used the wrong scripture word');
  assert(rankingState.firstSource === 'Journal Of Discourses', 'deep-link ranking regressed behind Donaldson echoing');

  console.log(JSON.stringify({ rootTiles, sourceState, jdWordState, hocWordState, scriptureState, scriptureToSourceState, rankingState }, null, 2));
  await browser.close();
}

run().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
