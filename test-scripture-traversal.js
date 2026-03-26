const puppeteer = require('puppeteer');

const LIBRARY_URL = 'http://127.0.0.1:4173/library/index.html';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function loadScripture(page, chapterId, verse) {
  await page.evaluate(({ chapterId, verse }) => {
    jumpTo(chapterId, verse);
  }, { chapterId, verse });
  await page.waitForSelector(`#ch-${chapterId} .verse#v${verse}`, { timeout: 20000 });
  await page.waitForFunction(
    ({ chapterId, verse }) => {
      const verseEl = document.querySelector(`#ch-${chapterId} .verse#v${verse}`);
      return !!(verseEl && verseEl.classList.contains('verse-focus'));
    },
    { timeout: 10000 },
    { chapterId, verse }
  );
}

async function currentTarget(page) {
  return page.evaluate(() => {
    if (document.querySelector('.source-doc')) {
      const title = document.querySelector('.source-doc .source-title')?.textContent.trim() || '';
      const focus = document.querySelector('.source-para-focus')?.textContent.trim() || '';
      return {
        type: 'source',
        id: `source:${title}`,
        title,
        focus: focus.slice(0, 220),
      };
    }
    const verse = document.querySelector('.verse.verse-focus');
    const chapter = window.currentChapter || '';
    const meta = (window.chapterMeta && chapter && window.chapterMeta[chapter]) || null;
    const verseNum = verse ? Number((verse.id || '').replace('v', '')) : null;
    const display = meta && verseNum ? `${meta.book} ${meta.label}:${verseNum}` : chapter;
    return {
      type: 'scripture',
      id: `scripture:${chapter}:${verseNum || 0}`,
      chapter,
      verse: verseNum,
      display,
    };
  });
}

async function candidateWords(page) {
  return page.evaluate(() => {
    let nodes = [];
    const verse = document.querySelector('.verse.verse-focus');
    if (verse) {
      nodes = [...verse.querySelectorAll('.w')];
    } else {
      const focus = document.querySelector('.source-para-focus');
      if (focus) nodes = [...focus.querySelectorAll('.w')];
      if (!nodes.length) {
        const para = document.querySelector('.source-doc .source-para');
        if (para) nodes = [...para.querySelectorAll('.w')];
      }
    }
    const seen = new Set();
    return nodes.map((el) => ({
      stem: el.dataset.st,
      text: (el.textContent || '').trim(),
    })).filter((item) => {
      const key = `${item.stem}|${item.text}`;
      if (!item.stem || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  });
}

async function clickWord(page, stem) {
  await page.evaluate((stem) => {
    let nodes = [];
    const verse = document.querySelector('.verse.verse-focus');
    if (verse) {
      nodes = [...verse.querySelectorAll('.w')];
    } else {
      const focus = document.querySelector('.source-para-focus');
      if (focus) nodes = [...focus.querySelectorAll('.w')];
      if (!nodes.length) {
        const para = document.querySelector('.source-doc .source-para');
        if (para) nodes = [...para.querySelectorAll('.w')];
      }
    }
    const target = nodes.find((el) => el.dataset.st === stem);
    if (target) target.click();
  }, stem);
  await page.waitForFunction(() => document.querySelector('#channel').classList.contains('open'), { timeout: 15000 });
  await sleep(250);
}

async function channelCandidates(page) {
  return page.evaluate(() => {
    const matches = Array.isArray(window.channelMorsels) ? window.channelMorsels : [];
    return matches.map((m, idx) => {
      const scripture = window.resolveScriptureRef ? window.resolveScriptureRef(`${m.lb || ''} ${m.x || ''}`) : null;
      const source = window.resolveSourceTarget ? window.resolveSourceTarget(m) : null;
      return {
        idx,
        source: m.s || '',
        label: m.lb || '',
        excerpt: String(m.x || '').slice(0, 220),
        scripture,
        sourceTarget: source,
      };
    }).filter((m) => m.scripture || m.sourceTarget);
  });
}

async function clickMorsel(page, idx) {
  await page.$eval(`.ch-morsel[data-idx="${idx}"]`, (el) => el.click());
  await sleep(700);
}

async function run() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox'],
    protocolTimeout: 120000,
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 1 });
  await page.goto(LIBRARY_URL, { waitUntil: 'networkidle0', timeout: 60000 });
  await page.waitForSelector('#splash.gone', { timeout: 60000 });

  const start = { chapterId: 'john_3', verse: 1, display: 'John 3:1' };
  await loadScripture(page, start.chapterId, start.verse);

  const visited = new Set();
  const chain = [];
  let current = await currentTarget(page);
  visited.add(current.id);

  for (let hop = 0; hop < 5; hop += 1) {
    const words = await candidateWords(page);
    let nextHop = null;

    for (const word of words) {
      await clickWord(page, word.stem);
      const candidates = await channelCandidates(page);
      const pick = candidates.find((candidate) => {
        if (candidate.scripture) {
          return !visited.has(`scripture:${candidate.scripture.chapterId}:${candidate.scripture.verse}`);
        }
        if (candidate.sourceTarget) {
          return !visited.has(`source:${candidate.sourceTarget.docId}`);
        }
        return false;
      });
      if (!pick) {
        await page.$eval('#ch-close', (el) => el.click());
        continue;
      }

      await clickMorsel(page, pick.idx);
      const target = await currentTarget(page);
      if (target.type === 'source' && pick.sourceTarget) {
        target.id = `source:${pick.sourceTarget.docId}`;
      }
      nextHop = {
        from: current.type === 'scripture' ? current.display : current.title,
        viaWord: word.text,
        viaStem: word.stem,
        viaSource: pick.source,
        label: pick.label,
        to: target.type === 'scripture' ? target.display : target.title,
        type: target.type,
      };
      current = target;
      visited.add(target.id);
      break;
    }

    if (!nextHop) {
      chain.push({ from: current.type === 'scripture' ? current.display : current.title, deadEnd: true });
      break;
    }
    chain.push(nextHop);
  }

  const hopCount = chain.filter((step) => !step.deadEnd).length;
  const sourceHopCount = chain.filter((step) => step.type === 'source').length;
  const scriptureHopCount = chain.filter((step) => step.type === 'scripture').length;

  const report = {
    start: start.display,
    metrics: {
      hopCount,
      sourceHopCount,
      scriptureHopCount,
      deadEnd: chain.some((step) => step.deadEnd),
      visitedCount: visited.size,
    },
    chain,
  };

  console.log(JSON.stringify(report, null, 2));
  assert(hopCount >= 3, 'Traversal smoke test produced too few hops');
  assert(sourceHopCount >= 1, 'Traversal smoke test never entered a source document');

  await browser.close();
}

run().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
