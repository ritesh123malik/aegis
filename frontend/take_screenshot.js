const puppeteer = require('puppeteer-core');
const path = require('path');

(async () => {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000 });
  
  console.log('Setting up request interception...');
  page.on('request', req => {
    const url = req.url();
    if (url.includes('localhost:8000') || url.includes('localhost:3000')) {
      console.log(`[NETWORK] ${req.method()} -> ${url}`);
    }
  });

  page.on('console', msg => {
    console.log(`[CONSOLE] ${msg.type().toUpperCase()}: ${msg.text()}`);
  });

  console.log('Navigating to http://localhost:3000...');
  await page.goto('http://localhost:3000', { 
    waitUntil: 'networkidle2',
    timeout: 30000 
  });
  
  console.log('Waiting 5 seconds for Leaflet map tiles and UI to settle...');
  await new Promise(resolve => setTimeout(resolve, 5000));
  
  const screenshotPath = 'C:\\Users\\rites\\aegis\\screenshot.png';
  console.log(`Taking screenshot and saving to ${screenshotPath}...`);
  await page.screenshot({ path: screenshotPath });
  console.log('Screenshot saved successfully!');
  
  await browser.close();
  console.log('Browser closed.');
})().catch(err => {
  console.error('Fatal error during execution:', err);
  process.exit(1);
});
