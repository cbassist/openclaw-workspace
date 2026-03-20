import { chromium } from 'playwright';

const GROUP_NAME = process.env.GROUP_NAME || 'openclaw-dev';
const BOTS_TO_ADD = (process.env.BOTS || 'dante_claude_bot,pimpshizzleBot').split(',');

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

  // Click the compose/pencil FAB
  console.log('Clicking new chat button...');
  const fab = page.locator('.NewChatButton button, button.Button.fab, [aria-label="New Message"]').first();
  await fab.click({ timeout: 5000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'test-results/group-01-menu.png' });

  // The menu is now open — click "New Group" directly from the popup menu
  console.log('Clicking New Group from menu...');
  const newGroupBtn = page.locator('.bubble-menu-item, .MenuItem, .menu-item').filter({ hasText: /new group/i }).first();
  if (await newGroupBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await newGroupBtn.click();
    console.log('  Clicked New Group menu item');
  } else {
    // Try clicking by text content
    await page.locator('text=/New Group/i').first().click({ timeout: 3000 }).catch(async () => {
      console.log('  Text locator failed, trying force click...');
      // Force click the backdrop away first
      await page.mouse.click(640, 450);
      await page.waitForTimeout(500);
      // Try hamburger menu approach
      const hamburger = page.locator('#LeftColumn-main button').first();
      await hamburger.click();
      await page.waitForTimeout(1000);
      await page.locator('text=/New Group/i').first().click();
    });
  }
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'test-results/group-02-addmembers.png' });

  // Now we should be on the "Add Members" screen
  // Search for and add each bot
  for (const bot of BOTS_TO_ADD) {
    console.log(`Searching for @${bot}...`);
    // Find the search input on the add-members screen
    const inputs = page.locator('input[type="text"]');
    const inputCount = await inputs.count();
    console.log(`  Found ${inputCount} text inputs`);

    // Use the last visible input (skip the global search)
    let searchInput;
    for (let i = inputCount - 1; i >= 0; i--) {
      if (await inputs.nth(i).isVisible().catch(() => false)) {
        searchInput = inputs.nth(i);
        break;
      }
    }

    if (!searchInput) {
      console.log(`  No visible search input found`);
      await page.screenshot({ path: `test-results/group-err-${bot}.png` });
      continue;
    }

    await searchInput.click();
    await searchInput.fill(bot);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `test-results/group-search-${bot}.png` });

    // Click the first list item (the search result)
    const firstItem = page.locator('.ListItem').first();
    if (await firstItem.isVisible({ timeout: 3000 }).catch(() => false)) {
      await firstItem.click();
      console.log(`  Added @${bot}`);
    } else {
      console.log(`  No search results for @${bot}`);
    }
    await page.waitForTimeout(500);
    await searchInput.fill('');
    await page.waitForTimeout(500);
  }

  await page.screenshot({ path: 'test-results/group-03-members-added.png' });

  // Click the forward/next FAB
  console.log('Clicking Next...');
  const nextFab = page.locator('.FloatingActionButton button, button.Button.fab').last();
  await nextFab.click({ timeout: 5000 }).catch(async () => {
    // Try any button that looks like "next" or "continue"
    await page.locator('button:has-text("Next")').first().click();
  });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'test-results/group-04-setname.png' });

  // Type the group name
  console.log(`Setting name: ${GROUP_NAME}`);
  const nameInput = page.locator('input[type="text"]').first();
  await nameInput.fill(GROUP_NAME);
  await page.waitForTimeout(500);

  // Click create
  console.log('Creating group...');
  const createFab = page.locator('.FloatingActionButton button, button.Button.fab').last();
  await createFab.click({ timeout: 5000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: 'test-results/group-05-created.png' });

  // Read the header to confirm
  const header = await page.locator('.MiddleHeader').first().textContent().catch(() => '(unknown)');
  console.log(`\nCreated group: ${header}`);

  // Get the group chat URL/ID from the URL bar
  const url = page.url();
  console.log(`URL: ${url}`);

  console.log('\nDone!');
  await browser.close();
}

main().catch(err => { console.error('Fatal:', err.message); process.exit(1); });
