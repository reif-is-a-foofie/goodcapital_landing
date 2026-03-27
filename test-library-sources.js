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
  assert(rootTiles.includes('Times and Seasons'), 'Times and Seasons missing from TOC root');
  assert(rootTiles.includes('Millennial Star'), 'Millennial Star missing from TOC root');

  await page.$eval('.toc-tile[data-action="source-collection"][data-collection="times_and_seasons"]', (el) => el.click());
  await page.waitForFunction(() =>
    document.querySelector('#toc-title').textContent === 'Sources' &&
    document.querySelector('#toc-subtitle').textContent === 'Times and Seasons'
  );

  const timesState = await page.evaluate(() => {
    const first = document.querySelector('.toc-tile[data-action="source-doc"]');
    return {
      firstLabel: first?.querySelector('.toc-tile-title')?.textContent.trim() || '',
      docCount: document.querySelectorAll('.toc-tile[data-action="source-doc"]').length,
    };
  });

  assert(timesState.docCount >= 20, 'Times and Seasons did not split into issue-like source docs');
  assert(/Vol\.\s*\d+/.test(timesState.firstLabel) && /No\.\s*\d+/.test(timesState.firstLabel), 'Times and Seasons issue labels did not render with volume/number metadata');
  await page.$eval('#toc-back', (el) => el.click());
  await page.waitForFunction(() =>
    document.querySelector('#toc-title').textContent === 'Sources' &&
    document.querySelector('#toc-subtitle').textContent.trim() === ''
  );

  await page.$eval('.toc-tile[data-action="source-collection"][data-collection="millennial_star"]', (el) => el.click());
  await page.waitForFunction(() =>
    document.querySelector('#toc-title').textContent === 'Sources' &&
    document.querySelector('#toc-subtitle').textContent === 'Millennial Star'
  );

  const starState = await page.evaluate(() => {
    const first = document.querySelector('.toc-tile[data-action="source-doc"]');
    return {
      firstLabel: first?.querySelector('.toc-tile-title')?.textContent.trim() || '',
      docCount: document.querySelectorAll('.toc-tile[data-action="source-doc"]').length,
    };
  });

  assert(starState.docCount >= 100, 'Millennial Star did not split into issue-like source docs');
  assert(/Vol\.\s*\d+/.test(starState.firstLabel) && /No\.\s*\d+/.test(starState.firstLabel), 'Millennial Star issue labels did not render with volume/number metadata');
  await page.$eval('#toc-back', (el) => el.click());
  await page.waitForFunction(() =>
    document.querySelector('#toc-title').textContent === 'Sources' &&
    document.querySelector('#toc-subtitle').textContent.trim() === ''
  );

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
  assert(rankingState.firstSource === 'Standard Works', 'scripture-first ranking regressed behind commentary/source results');
  assert(rankingState.morsels.every((m) => m.src === 'Standard Works'), 'scripture-first ranking no longer pins the first scripture tranche');

  await page.$eval('#ch-close', (el) => el.click());
  await page.click('#v16');
  await page.waitForSelector('#v16 span.w', { timeout: 20000 });
  await page.evaluate(() => {
    const target = Array.from(document.querySelectorAll('#v16 span.w')).find((el) => /god/i.test(el.textContent || ''));
    if (target) target.click();
  });
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });
  await page.waitForFunction(() => {
    const study = document.querySelector('#ch-study');
    return !!(study && !study.hidden && /G2316|theos|god/i.test(study.textContent || ''));
  }, { timeout: 15000 });

  const strongsState = await page.evaluate(() => ({
    word: document.querySelector('#ch-word')?.textContent.trim(),
    study: document.querySelector('#ch-study')?.textContent.trim() || '',
  }));

  assert(/god/i.test(strongsState.word), 'word-study regression used the wrong scripture word');
  assert(/G2316|theos/i.test(strongsState.study), "Strong's word study did not appear for John 3:16");
  await page.$eval('#ch-close', (el) => el.click());
  await page.waitForFunction(() => !document.querySelector('#channel').classList.contains('open'));

  await page.evaluate(() => jumpTo('genesis_2'));
  await page.waitForSelector('#v6 .verse-text .w', { timeout: 20000 });
  await page.evaluate(() => {
    const target = Array.from(document.querySelectorAll('#v6 .verse-text .w')).find((el) => /mist/i.test(el.textContent || ''));
    if (target) target.click();
  });
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });
  const mistState = await page.evaluate(() => ({
    word: document.querySelector('#ch-word')?.textContent.trim(),
    firstSource: document.querySelector('.ch-morsel .ch-src-name')?.textContent.trim() || '',
  }));
  assert(/mist/i.test(mistState.word), 'scripture fallback regression used the wrong Genesis 2 word');
  assert(mistState.firstSource === 'Standard Works', 'Genesis 2 mist did not prioritize standard works fallback');
  await page.$eval('#ch-close', (el) => el.click());
  await page.waitForFunction(() => !document.querySelector('#channel').classList.contains('open'));

  await page.evaluate(() => jumpTo('john_3'));
  await page.waitForSelector('#v16 .verse-text .w', { timeout: 20000 });
  await page.evaluate(() => {
    const target = Array.from(document.querySelectorAll('#v16 .verse-text .w')).find((el) => /loved/i.test(el.textContent || ''));
    if (target) target.click();
  });
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });
  const loveState = await page.evaluate(() => ({
    word: document.querySelector('#ch-word')?.textContent.trim(),
    sources: Array.from(document.querySelectorAll('.ch-morsel .ch-src-name')).slice(0, 3).map((el) => el.textContent.trim()),
  }));
  assert(/lov/i.test(loveState.word), 'scripture fallback regression used the wrong John 3 word');
  assert(loveState.sources[0] === 'Standard Works', 'John 3 loved did not rank standard works first');
  await page.$eval('#ch-close', (el) => el.click());
  await page.waitForFunction(() => !document.querySelector('#channel').classList.contains('open'));

  await page.evaluate(() => jumpTo('john_1'));
  await page.waitForSelector('#v1 .verse-text', { timeout: 20000 });
  const johnCleanState = await page.evaluate(() => ({
    v1: document.querySelector('#v1 .verse-text')?.innerText || '',
    v17: document.querySelector('#v17 .verse-text')?.innerText || '',
    v1Html: document.querySelector('#v1 .verse-text')?.innerHTML || '',
  }));
  assert(/In the beginning was the Word/i.test(johnCleanState.v1), 'John 1:1 did not restore full canonical verse text');
  assert(/grace and truth came by Jesus Christ/i.test(johnCleanState.v17), 'John 1:17 did not restore full canonical verse text');
  assert(!/&lt;span class=|&amp;quot;cw/i.test(johnCleanState.v1Html), 'John 1 still leaks escaped critical-word wrappers');

  await page.evaluate(() => jumpTo('1_nephi_8'));
  await page.waitForSelector('#v23 .verse-text .w', { timeout: 20000 });
  await page.evaluate(() => {
    const target = Array.from(document.querySelectorAll('#v23 .verse-text .w')).find((el) => /mist/i.test(el.textContent || ''));
    if (target) target.click();
  });
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });
  const nephiMistState = await page.evaluate(() => ({
    word: document.querySelector('#ch-word')?.textContent.trim(),
    sources: Array.from(document.querySelectorAll('.ch-morsel .ch-src-name')).slice(0, 3).map((el) => el.textContent.trim()),
    texts: Array.from(document.querySelectorAll('.ch-morsel .ch-morsel-text')).slice(0, 3).map((el) => el.textContent.trim()),
  }));
  assert(/mist/i.test(nephiMistState.word), 'Book of Mormon fallback regression used the wrong 1 Nephi word');
  assert(nephiMistState.sources[0] === 'Standard Works', '1 Nephi mist did not rank standard works first');
  assert(nephiMistState.texts.some((text) => /mist of darkness|fell on him a mist/i.test(text)), '1 Nephi mist did not surface scripture fallback morsels');
  await page.$eval('#ch-close', (el) => el.click());
  await page.waitForFunction(() => !document.querySelector('#channel').classList.contains('open'));

  await page.evaluate(() => jumpTo('doctrine_and_covenants_121'));
  await page.waitForSelector('#v41 .verse-text .w', { timeout: 20000 });
  await page.evaluate(() => {
    const target = Array.from(document.querySelectorAll('#v41 .verse-text .w')).find((el) => /priesthood/i.test(el.textContent || ''));
    if (target) target.click();
  });
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });
  const dcPriesthoodState = await page.evaluate(() => ({
    word: document.querySelector('#ch-word')?.textContent.trim(),
    sources: Array.from(document.querySelectorAll('.ch-morsel .ch-src-name')).slice(0, 3).map((el) => el.textContent.trim()),
    texts: Array.from(document.querySelectorAll('.ch-morsel .ch-morsel-text')).slice(0, 3).map((el) => el.textContent.trim()),
  }));
  assert(/priesthood/i.test(dcPriesthoodState.word), 'D&C fallback regression used the wrong Doctrine and Covenants word');
  assert(dcPriesthoodState.sources[0] === 'Standard Works', 'Doctrine and Covenants priesthood did not rank standard works first');
  assert(dcPriesthoodState.texts.some((text) => /Priesthood of thy father|Melchizedek Priesthood|higher, or Melchizedek Priesthood/i.test(text)), 'Doctrine and Covenants priesthood did not surface scripture fallback morsels');
  await page.$eval('#ch-close', (el) => el.click());
  await page.waitForFunction(() => !document.querySelector('#channel').classList.contains('open'));

  await page.evaluate(() => {
    const target = Array.from(document.querySelectorAll('#v41 .verse-text .w')).find((el) => /^love$/i.test((el.textContent || '').trim()));
    if (target) target.click();
  });
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });
  const dcLoveCleanState = await page.evaluate(() => ({
    word: document.querySelector('#ch-word')?.textContent.trim(),
    sources: Array.from(document.querySelectorAll('.ch-morsel .ch-src-name')).slice(0, 3).map((el) => el.textContent.trim()),
    verseText: document.querySelector('#v41 .verse-text')?.innerText || '',
    verseHtml: document.querySelector('#v41 .verse-text')?.innerHTML || '',
  }));
  assert(/love/i.test(dcLoveCleanState.word), 'D&C clean re-annotation did not make love clickable');
  assert(dcLoveCleanState.sources[0] === 'Standard Works', 'Doctrine and Covenants love did not rank standard works first after re-annotation');
  assert(!/&lt;span class=|&amp;quot;cw/i.test(dcLoveCleanState.verseHtml), 'Doctrine and Covenants verse HTML still leaks escaped critical-word wrappers');
  await page.$eval('#ch-close', (el) => el.click());
  await page.waitForFunction(() => !document.querySelector('#channel').classList.contains('open'));

  console.log(JSON.stringify({ rootTiles, timesState, starState, sourceState, jdWordState, hocWordState, scriptureState, scriptureToSourceState, rankingState, strongsState, mistState, loveState, johnCleanState, nephiMistState, dcPriesthoodState, dcLoveCleanState }, null, 2));
  await browser.close();
}

run().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
