import { chromium } from 'playwright';

const DANTE_KITT_BOT = 'dante_claude_bot';
const COMMANDS_TO_TEST = [];

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

  // Navigate to Telegram Web
  console.log('Opening Telegram Web...');
  await page.goto('https://web.telegram.org/a/');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);

  // Screenshot to see current state
  await page.screenshot({ path: 'test-results/01-telegram-loaded.png' });
  console.log('Screenshot: test-results/01-telegram-loaded.png');

  // Use the global search to find @dante_claude_bot
  console.log('Searching for Dante KITT bot...');

  // Click the search icon / input in the left sidebar
  const searchTrigger = page.locator('[aria-label="Search"], .LeftMainHeader button, #LeftColumn-main .search-input, input[type="text"]').first();
  await searchTrigger.click();
  await page.waitForTimeout(500);

  // Type the bot username
  await page.keyboard.type('@dante_claude_bot', { delay: 30 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'test-results/02-search.png' });

  // Look at all visible list items and find one with "Dante" (not "BotFather", not the group)
  // We want the bot, which should show as "Dante" with a bot badge
  const results = page.locator('.ListItem');
  const count = await results.count();
  console.log(`Found ${count} search results`);

  // Dismiss any overlay menus
  await page.keyboard.press('Escape');
  await page.waitForTimeout(500);

  // Configurable: which chat to open
  const TARGET_CHAT = process.env.TG_TARGET || 'pimp-shizzle';

  let clicked = false;
  for (let i = 0; i < Math.min(count, 10); i++) {
    const text = await results.nth(i).textContent().catch(() => '');
    console.log(`  Result ${i}: ${text?.substring(0, 80)}`);
    if (text && text.toLowerCase().includes(TARGET_CHAT.toLowerCase())) {
      console.log(`  -> Clicking result ${i}`);
      await results.nth(i).click();
      clicked = true;
      break;
    }
  }

  if (!clicked) {
    console.log(`Could not find ${TARGET_CHAT} in search, trying first result...`);
    const fallback = page.locator('.ListItem').filter({ hasText: new RegExp(TARGET_CHAT, 'i') }).first();
    await fallback.click().catch(() => console.log('No match found at all'));
  }

  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'test-results/02-navigated-to-bot.png' });

  // Check what chat we're in
  const headerText = await page.locator('.MiddleHeader, .ChatInfo, .chat-info').first().textContent().catch(() => '');
  console.log(`Chat header: ${headerText?.substring(0, 100)}`);

  await page.screenshot({ path: 'test-results/03-bot-chat.png' });
  console.log('Screenshot: test-results/03-bot-chat.png');

  // Find the message input and send a custom message
  const msgInput = page.locator('.composer-input, [contenteditable="true"]').last();
  const customMsg = process.env.TG_MESSAGE || 'test';

  if (customMsg) {
    console.log(`\nSending message: ${customMsg}`);
    try {
      await msgInput.click();
      await msgInput.fill('');
      await page.keyboard.type(customMsg, { delay: 30 });
      await page.waitForTimeout(500);
      await page.keyboard.press('Enter');
      console.log('  Sent!');
      await page.waitForTimeout(5000);
      await page.screenshot({ path: 'test-results/04-message-sent.png' });

      // Grab last few messages
      const messages = page.locator('.message, .Message');
      const msgCount = await messages.count();
      for (let i = Math.max(0, msgCount - 3); i < msgCount; i++) {
        const txt = await messages.nth(i).textContent().catch(() => '');
        console.log(`  msg[${i}]: ${txt?.substring(0, 200)}`);
      }
    } catch (err) {
      console.error(`  Error: ${err.message}`);
      await page.screenshot({ path: 'test-results/error-send.png' });
    }
  }

  console.log('\nDone. Closing browser...');
  await page.screenshot({ path: 'test-results/final-state.png' });
  await browser.close();
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
