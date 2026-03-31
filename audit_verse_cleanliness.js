const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, 'library', 'chapters');
const OUT_JSON = path.join(__dirname, 'verse-cleanliness-report.json');
const OUT_TXT = path.join(__dirname, 'verse-cleanliness-report.txt');

function lineNumber(text, index) {
  return text.slice(0, index).split('\n').length;
}

function excerpt(text, index, radius = 120) {
  const start = Math.max(0, index - radius);
  const end = Math.min(text.length, index + radius);
  return text.slice(start, end).replace(/\s+/g, ' ').trim();
}

function collectFiles(dir) {
  return fs.readdirSync(dir)
    .filter((name) => name.endsWith('.html'))
    .sort()
    .map((name) => path.join(dir, name));
}

function scanFile(filePath) {
  const text = fs.readFileSync(filePath, 'utf8');
  const issues = [];

  const escapedPatterns = [
    /&lt;span class="cw"/g,
    /&lt;span class=&quot;cw&quot;/g,
    /&lt;div class="cw"/g,
    /&lt;span class='cw'/g,
  ];

  escapedPatterns.forEach((pattern) => {
    let match;
    while ((match = pattern.exec(text))) {
      issues.push({
        type: 'escaped-wrapper',
        line: lineNumber(text, match.index),
        excerpt: excerpt(text, match.index),
      });
    }
  });

  const verseRe = /<div class="verse" id="v(\d+)">([\s\S]*?)(?=<div class="verse" id="v\d+">|<\/body>)/g;
  let verseMatch;
  while ((verseMatch = verseRe.exec(text))) {
    const verseId = parseInt(verseMatch[1], 10);
    const chunk = verseMatch[2];
    const numMatch = chunk.match(/<span class="verse-num">(\d+)<\/span>/);
    if (numMatch) {
      const num = parseInt(numMatch[1], 10);
      if (num !== verseId) {
        issues.push({
          type: 'verse-number-mismatch',
          line: lineNumber(text, verseMatch.index),
          excerpt: `verse id v${verseId} but verse-num ${num}`,
        });
      }
    } else {
      issues.push({
        type: 'missing-verse-number',
        line: lineNumber(text, verseMatch.index),
        excerpt: `verse id v${verseId} missing verse-num span`,
      });
    }

    const textNodeMatch = chunk.match(/<span class="verse-text">([\s\S]*?)<\/span>/);
    if (textNodeMatch) {
      const verseText = textNodeMatch[1];
      const escapedInside = verseText.includes('&lt;span class=');
      if (escapedInside) {
        const idx = text.indexOf(textNodeMatch[0], verseMatch.index);
        issues.push({
          type: 'escaped-wrapper-in-verse-text',
          line: lineNumber(text, idx >= 0 ? idx : verseMatch.index),
          excerpt: excerpt(text, idx >= 0 ? idx : verseMatch.index),
        });
      }
    }
  }

  return issues;
}

function main() {
  const files = collectFiles(ROOT);
  const report = [];

  files.forEach((filePath) => {
    const issues = scanFile(filePath);
    if (!issues.length) return;
    report.push({
      file: path.relative(__dirname, filePath),
      issueCount: issues.length,
      issues: issues.slice(0, 12),
      total: issues.length,
    });
  });

  const summary = {
    filesScanned: files.length,
    filesWithIssues: report.length,
    totalIssues: report.reduce((sum, row) => sum + row.total, 0),
    report,
  };

  fs.writeFileSync(OUT_JSON, JSON.stringify(summary, null, 2) + '\n');
  const lines = [
    `filesScanned: ${summary.filesScanned}`,
    `filesWithIssues: ${summary.filesWithIssues}`,
    `totalIssues: ${summary.totalIssues}`,
    '',
  ];
  report.slice(0, 80).forEach((row) => {
    lines.push(`${row.file} (${row.total})`);
    row.issues.slice(0, 4).forEach((issue) => {
      lines.push(`  ${issue.type} L${issue.line}: ${issue.excerpt}`);
    });
    lines.push('');
  });
  fs.writeFileSync(OUT_TXT, lines.join('\n'));

  console.log(JSON.stringify({
    filesScanned: summary.filesScanned,
    filesWithIssues: summary.filesWithIssues,
    totalIssues: summary.totalIssues,
  }, null, 2));
}

main();
