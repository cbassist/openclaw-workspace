import { chromium } from 'playwright';

async function main() {
  const browser = await chromium.launchPersistentContext(
    process.env.HOME + '/.playwright/telegram-session',
    {
      headless: false,
      permissions: ['clipboard-read', 'clipboard-write', 'notifications'],
      args: ['--disable-infobars', '--no-first-run'],
      viewport: { width: 1280, height: 900 },
    }
  );

  const page = browser.pages()[0] || await browser.newPage();
  console.log('Opening Telegram Web...');
  await page.goto('https://web.telegram.org/a/');
  await page.waitForTimeout(5000);

  // Search for BotFather
  console.log('Searching for BotFather...');
  await page.keyboard.type('BotFather', { delay: 30 });
  await page.waitForTimeout(2000);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);

  const results = page.locator('.ListItem');
  const count = await results.count();
  for (let i = 0; i < Math.min(count, 5); i++) {
    const t = await results.nth(i).textContent().catch(() => '');
    if (t.includes('BotFather')) {
      await results.nth(i).click();
      break;
    }
  }
  await page.waitForTimeout(2000);

  // Send /mybots
  const msgInput = page.locator('.composer-input, [contenteditable="true"]').last();
  await msgInput.click();
  await page.keyboard.type('/mybots', { delay: 50 });
  await page.waitForTimeout(300);
  await page.keyboard.press('Enter');
  console.log('Sent /mybots');
  await page.waitForTimeout(3000);

  await page.screenshot({ path: 'test-results/botfather-mybots.png' });

  // Look for inline keyboard buttons
  const buttons = page.locator('.inline-button-text, button.Button');
  const btnCount = await buttons.count();
  console.log(`Found ${btnCount} buttons`);

  // Click the @dante_claude_bot button
  for (let i = 0; i < btnCount; i++) {
    const text = await buttons.nth(i).textContent().catch(() => '');
    console.log(`  Button ${i}: ${text}`);
    if (text.includes('dante_claude_bot')) {
      await buttons.nth(i).click();
      console.log('  -> Clicked dante_claude_bot');
      break;
    }
  }
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'test-results/botfather-dante-selected.png' });

  // Click "Bot Settings"
  const buttons2 = page.locator('.inline-button-text, button.Button');
  const btn2Count = await buttons2.count();
  for (let i = 0; i < btn2Count; i++) {
    const text = await buttons2.nth(i).textContent().catch(() => '');
    if (text.includes('Bot Settings')) {
      await buttons2.nth(i).click();
      console.log('  -> Clicked Bot Settings');
      break;
    }
  }
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'test-results/botfather-settings.png' });

  // Click "Group Privacy"
  const buttons3 = page.locator('.inline-button-text, button.Button');
  const btn3Count = await buttons3.count();
  for (let i = 0; i < btn3Count; i++) {
    const text = await buttons3.nth(i).textContent().catch(() => '');
    console.log(`  Setting ${i}: ${text}`);
    if (text.includes('Group Privacy')) {
      await buttons3.nth(i).click();
      console.log('  -> Clicked Group Privacy');
      break;
    }
  }
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'test-results/botfather-privacy.png' });

  // Read the current state
  const msgs = page.locator('.message, .Message');
  const msgCount = await msgs.count();
  for (let i = Math.max(0, msgCount - 3); i < msgCount; i++) {
    const txt = await msgs.nth(i).textContent().catch(() => '');
    console.log(`msg: ${txt?.substring(0, 300)}`);
  }

  await page.screenshot({ path: 'test-results/botfather-final.png' });
  console.log('\nDone. Check test-results/botfather-*.png for screenshots.');
  await browser.close();
}

main().catch(err => { console.error('Fatal:', err.message); process.exit(1); });
