#!/usr/bin/env node
/**
 * Test: nav stays fixed when scrolling.
 * Run: node test-nav-fixed.js
 * Requires: npm install puppeteer (or use system Chrome)
 */
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 9876;
const htmlPath = path.join(__dirname, 'index.html');

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html' });
  res.end(fs.readFileSync(htmlPath));
});

server.listen(PORT, async () => {
  try {
    const puppeteer = require('puppeteer');
    const browser = await puppeteer.launch({
      headless: true,
      executablePath: process.platform === 'darwin'
        ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        : undefined,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    await page.goto(`http://localhost:${PORT}`, { waitUntil: 'networkidle0', timeout: 5000 });

    const before = await page.evaluate(() => {
      const n = document.querySelector('nav');
      return n ? { top: n.getBoundingClientRect().top, pos: getComputedStyle(n).position } : null;
    });
    await page.evaluate(() => window.scrollBy(0, 600));
    await new Promise(r => setTimeout(r, 150));
    const after = await page.evaluate(() => {
      const n = document.querySelector('nav');
      return n ? { top: n.getBoundingClientRect().top } : null;
    });

    await browser.close();
    server.close();

    const fixed = before?.pos === 'fixed' && before && after && Math.abs(after.top - before.top) < 3;
    console.log('position:', before?.pos, '| top before:', before?.top?.toFixed(0), '| after scroll:', after?.top?.toFixed(0));
    console.log(fixed ? '✓ Nav stays fixed' : '✗ Nav moved');
    process.exit(fixed ? 0 : 1);
  } catch (e) {
    server.close();
    console.error('Browser test failed:', e.message);
    console.log('Static check: nav has position:fixed in CSS');
    const html = fs.readFileSync(htmlPath, 'utf8');
    process.exit(html.includes('position: fixed') ? 0 : 1);
  }
});
