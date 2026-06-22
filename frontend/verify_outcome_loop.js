const puppeteer = require('puppeteer-core');

(async () => {
  console.log('Launching Edge browser...');
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1200 });

  // Trace network requests
  page.on('request', req => {
    const url = req.url();
    if (url.includes('localhost:8000') || url.includes('localhost:3000')) {
      console.log(`[NETWORK] ${req.method()} -> ${url}`);
    }
  });

  console.log('Navigating to http://localhost:3000...');
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle2' });

  console.log('Waiting for active incident dossier and outcome form to render...');
  await page.waitForSelector('input[placeholder="e.g. 120"]', { timeout: 10000 });

  // Scroll to bottom of right sidebar
  console.log('Scrolling right sidebar to bottom...');
  await page.evaluate(() => {
    const sidebars = Array.from(document.querySelectorAll('.overflow-y-auto'));
    const rightSidebar = sidebars[sidebars.length - 1];
    if (rightSidebar) rightSidebar.scrollTop = 1500;
  });
  await new Promise(resolve => setTimeout(resolve, 500));

  // Capture before screenshot
  console.log('Capturing initial dashboard state...');
  await page.screenshot({ path: 'C:\\Users\\rites\\aegis\\screenshot_before_outcome.png' });

  // Fill in the form fields
  console.log('Filling out the Outcome Log Form...');
  await page.type('input[placeholder="e.g. 120"]', '250'); // Actual duration: 250 mins
  await page.type('input[placeholder="e.g. 8"]', '16'); // Officers deployed: 16
  await page.select('select', 'Critical'); // Disruption class: Critical
  await page.type('input[placeholder="e.g. Inspector R. Gowda"]', 'Inspector J. Rogers'); // Operator ID
  await page.type('textarea', 'Logged end-to-end outcome loop test.'); // Notes

  console.log('Submitting Outcome Form...');
  await page.click('button[type="submit"]');

  console.log('Waiting for success state to display (2.5s success duration)...');
  await new Promise(resolve => setTimeout(resolve, 3500));

  // Scroll right sidebar to bottom again since elements may have resized
  console.log('Scrolling right sidebar to bottom...');
  await page.evaluate(() => {
    const sidebars = Array.from(document.querySelectorAll('.overflow-y-auto'));
    const rightSidebar = sidebars[sidebars.length - 1];
    if (rightSidebar) rightSidebar.scrollTop = 1500;
  });
  await new Promise(resolve => setTimeout(resolve, 500));

  console.log('Capturing post-outcome dashboard state (showing updated recalibration viz)...');
  await page.screenshot({ path: 'C:\\Users\\rites\\aegis\\screenshot_after_outcome.png' });

  console.log('Extracting dashboard status metrics...');
  const metrics = await page.evaluate(() => {
    const textElements = Array.from(document.querySelectorAll('div, span'));
    
    // Find counter values based on text contents
    const outcomesHeader = textElements.find(el => el.textContent && el.textContent.includes('Outcomes Calibrated'));
    const biasHeader = textElements.find(el => el.textContent && el.textContent.includes('Active Bias Shift'));

    const outcomesCount = outcomesHeader ? outcomesHeader.nextElementSibling?.textContent?.trim() : 'N/A';
    const activeBias = biasHeader ? biasHeader.nextElementSibling?.textContent?.trim() : 'N/A';
    
    const predHeader = textElements.find(el => el.textContent && el.textContent.includes('PREDICTED DURATION'));
    const predVal = predHeader ? predHeader.nextElementSibling?.textContent?.trim() : 'N/A';

    return { outcomesCount, activeBias, predVal };
  });

  console.log('=== METRICS VERIFICATION ===');
  console.log('Outcomes Calibrated Count:', metrics.outcomesCount);
  console.log('Active Bias Shift Value:  ', metrics.activeBias);
  console.log('New Shifted Prediction:   ', metrics.predVal);
  console.log('============================');

  await browser.close();
  console.log('Verification completed successfully!');
})().catch(err => {
  console.error('Test failed with error:', err);
  process.exit(1);
});
