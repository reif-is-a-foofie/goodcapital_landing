const puppeteer = require('puppeteer-core');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function run() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1440, height: 1400 },
  });
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:4173/library/index.html', { waitUntil: 'networkidle0' });

  await page.waitForSelector('#content #metric-docs');
  await page.waitForFunction(() => {
    const el = document.getElementById('metric-docs');
    return el && el.textContent && el.textContent.trim() !== '...';
  });

  const payload = await page.evaluate(() => ({
    docs: document.getElementById('metric-docs')?.textContent?.trim(),
    paragraphs: document.getElementById('metric-paragraphs')?.textContent?.trim(),
    links: document.getElementById('metric-links')?.textContent?.trim(),
    agentBars: document.querySelectorAll('#agent-bars .bar-row').length,
    recent: document.querySelectorAll('#recent-completions .recent-item').length,
  }));

  assert(payload.docs && payload.docs !== '...', 'title page docs metric did not render');
  assert(payload.paragraphs && payload.paragraphs !== '...', 'title page paragraph metric did not render');
  assert(payload.links && payload.links !== '...', 'title page semantic links metric did not render');
  assert(payload.agentBars >= 1, 'title page agent activity chart missing');
  assert(payload.recent >= 1, 'title page recent completions list missing');

  console.log(JSON.stringify(payload, null, 2));
  await browser.close();
}

run().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
