// investigation_script.js
const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
    ],
  });
  const page = await browser.newPage();

  // Array to store console messages
  const consoleLogs = [];

  // Listen for all console events and push them to the array
  page.on('console', msg => {
    consoleLogs.push({
      type: msg.type(),
      text: msg.text(),
      location: msg.location(),
    });
  });

  try {
    console.log('Navigating to the page...');
    // Use a longer timeout to be safe, wait until the network is idle
    await page.goto('http://127.0.0.1:42649/', { waitUntil: 'networkidle', timeout: 20000 });
    console.log('Navigation complete. Waiting a bit more for any async operations...');
    await page.waitForTimeout(2000); // Wait 2 seconds for any late-loading elements or errors

    await page.screenshot({ path: 'logs/frontend_screenshot.png', fullPage: true });
    console.log('Screenshot saved to logs/frontend_screenshot.png');

  } catch (error) {
    console.error('An error occurred during navigation or screenshot:', error);
    // Even if navigation fails, try to take a screenshot of the error page
    await page.screenshot({ path: 'logs/frontend_error_screenshot.png', fullPage: true });
    console.log('Error screenshot saved to logs/frontend_error_screenshot.png');
  } finally {
    await browser.close();

    // Write the collected console logs to a file
    fs.writeFileSync('logs/console_logs.json', JSON.stringify(consoleLogs, null, 2));
    console.log('Console logs saved to logs/console_logs.json');
    console.log('Investigation script finished.');
  }
})();
