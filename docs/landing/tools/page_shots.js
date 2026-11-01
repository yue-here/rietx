// Screenshots of the site in both themes, at each width in W (default 1440,900,390).
//
//   PAGE=<built page>   the landing page from a file, the whole page, as before.
//   SITE=<base url>     the site served over http, the landing page and the manual
//                       together (WP-2021): the landing page whole, and the manual's
//                       front page, a Concepts page and a Theory page as a reader first
//                       sees them, since the chrome the two share is what is judged.
//                       Serve `site/` with the manual built into `site/docs/dev/`
//                       (MANUAL=<path> names another tree under the site).
//
// PWC is the path to playwright-core, OUT the directory to write to, and CHROMIUM a
// browser binary where the cached macOS one below is not the one to use.
const { chromium } = require(process.env.PWC);
const EXE = process.env.CHROMIUM || process.env.HOME + '/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const OUT = process.env.OUT;
const WIDTHS = (process.env.W || '1440,900,390').split(',').map(Number);
const MANUAL = process.env.MANUAL || 'docs/dev';
const PAGES = process.env.SITE
  ? [['landing', process.env.SITE + '/', true],
     ['manual', `${process.env.SITE}/${MANUAL}/index.html`, false],
     ['concepts', `${process.env.SITE}/${MANUAL}/concepts/fit.html`, false],
     ['theory', `${process.env.SITE}/${MANUAL}/theory/forward-model.html`, false]]
  : [['page', 'file://' + process.env.PAGE, true]];
(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--disable-gpu', '--no-sandbox'] });
  for (const theme of ['light', 'dark']) {
    for (const W of WIDTHS) {
      const ctx = await browser.newContext({ viewport: { width: W, height: 900 }, deviceScaleFactor: 1, colorScheme: theme });
      const page = await ctx.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(String(e)));
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
      for (const [name, url, whole] of PAGES) {
        await page.goto(url); await page.waitForTimeout(2500);
        // stop the landing page's animation at a telling frame and freeze
        await page.evaluate(() => { const s = document.querySelector('#scrub'); if (s) { s.value = 120; s.dispatchEvent(new Event('input')); } });
        await page.waitForTimeout(600);
        await page.screenshot({ path: `${OUT}/${name}-${theme}-${W}.png`, fullPage: whole });
        const h = await page.evaluate(() => document.documentElement.scrollHeight);
        console.log(name, theme, W, 'height', h, 'errors', errors.length ? errors.splice(0) : 'none');
      }
      await ctx.close();
    }
  }
  await browser.close();
})().catch(e => { console.error('FAILED', e); process.exit(1); });
