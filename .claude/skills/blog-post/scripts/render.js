// Usage: node render.js path/to/cover.html path/to/output.png
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [src, dst] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1536, height: 1024 }, deviceScaleFactor: 1 });
  await p.goto('file://' + path.resolve(src));
  await p.waitForTimeout(300);
  await p.screenshot({ path: dst });
  await b.close();
  console.log(dst);
})();
