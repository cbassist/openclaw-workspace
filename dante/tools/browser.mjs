#!/usr/bin/env node
/**
 * browser.mjs — Shared browser automation utility for all agents.
 *
 * Two backends:
 *   1. CDP attach (port 9222 or configurable) — for co-browsing with Mike
 *   2. Persistent context (~/.playwright-sessions/shared/) — for Telegram Web
 *
 * Usage:
 *   node browser.mjs telegram-read <chatId>          Read latest messages
 *   node browser.mjs telegram-send <chatId> <msg>    Send a message
 *   node browser.mjs telegram-screenshot <chatId>    Screenshot a chat
 *   node browser.mjs screenshot <url> [output]       Screenshot any URL
 *   node browser.mjs dashboard [section]             Screenshot OpenClaw dashboard
 *   node browser.mjs session-check                   Verify Telegram session is live
 *   node browser.mjs cdp-check [port]                Verify CDP browser is running
 */

import { chromium } from 'playwright';
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

const PERSISTENT_DIR = join(process.env.HOME, '.playwright-sessions/shared');
const CDP_PORT = process.env.CDP_PORT || '9222';
const CDP_URL = `http://127.0.0.1:${CDP_PORT}`;
const DASHBOARD_URL = 'http://127.0.0.1:18789/';
const TG_BASE = 'https://web.telegram.org/a/';
const TG_LOAD_WAIT = 12000; // ms to wait for Telegram SPA to hydrate

// --- Helpers ---

async function withPersistentContext(fn) {
  const context = await chromium.launchPersistentContext(PERSISTENT_DIR, {
    headless: true,
    viewport: { width: 1400, height: 900 },
  });
  try {
    return await fn(context);
  } finally {
    await context.close();
  }
}

async function withCDP(fn) {
  const browser = await chromium.connectOverCDP(CDP_URL);
  const context = browser.contexts()[0];
  try {
    return await fn(context, browser);
  } finally {
    // Don't close — just drop the reference. Browser stays alive.
  }
}

async function waitForTelegramReady(page) {
  // Wait for chat list to render instead of fixed sleep
  try {
    await page.locator('.ListItem, .Chat, [class*="ChatList"]').first()
      .waitFor({ state: 'visible', timeout: TG_LOAD_WAIT });
  } catch {
    // Fallback to fixed wait if locator doesn't match
    await page.waitForTimeout(TG_LOAD_WAIT);
  }
}

function getGatewayToken() {
  try {
    const secrets = JSON.parse(
      readFileSync(join(process.env.HOME, '.openclaw/secrets.json'), 'utf-8')
    );
    return secrets?.gateway?.auth?.token || '';
  } catch {
    return '';
  }
}

// --- Commands ---

async function telegramRead(chatId) {
  return withPersistentContext(async (context) => {
    const page = await context.newPage();
    await page.goto(`${TG_BASE}#${chatId}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await waitForTelegramReady(page);

    // Scroll to bottom
    const msgArea = page.locator('.MessageList').first();
    await msgArea.evaluate(el => el.scrollTop = el.scrollHeight).catch(() => {});
    await page.waitForTimeout(1000);

    await page.screenshot({ path: '/tmp/tg-read.png' });
    console.log('Screenshot saved to /tmp/tg-read.png');

    // Extract visible message text
    const messages = await page.locator('.Message .text-content, .message-content').allTextContents();
    const last10 = messages.slice(-10);
    if (last10.length) {
      console.log('\nRecent messages:');
      last10.forEach(m => console.log(`  ${m.substring(0, 120)}`));
    }
  });
}

async function telegramSend(chatId, message) {
  return withPersistentContext(async (context) => {
    const page = await context.newPage();
    await page.goto(`${TG_BASE}#${chatId}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await waitForTelegramReady(page);

    const msgInput = page.locator('[contenteditable="true"]').last();
    await msgInput.click();
    await page.waitForTimeout(300);
    await msgInput.fill(message);
    await page.waitForTimeout(300);
    await page.keyboard.press('Enter');
    await page.waitForTimeout(2000);

    await page.screenshot({ path: '/tmp/tg-sent.png' });
    console.log('Message sent. Screenshot: /tmp/tg-sent.png');
  });
}

async function telegramScreenshot(chatId) {
  return withPersistentContext(async (context) => {
    const page = await context.newPage();
    await page.goto(`${TG_BASE}#${chatId}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await waitForTelegramReady(page);

    const msgArea = page.locator('.MessageList').first();
    await msgArea.evaluate(el => el.scrollTop = el.scrollHeight).catch(() => {});
    await page.waitForTimeout(1000);

    const output = `/tmp/tg-${chatId.replace('-', 'n')}.png`;
    await page.screenshot({ path: output });
    console.log(`Screenshot saved to ${output}`);
  });
}

async function screenshot(url, output) {
  const out = output || '/tmp/browser-screenshot.png';

  // Try CDP first, fall back to persistent context
  try {
    await withCDP(async (context) => {
      const page = await context.newPage();
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await page.waitForTimeout(2000);
      await page.screenshot({ path: out });
      await page.close();
    });
  } catch {
    await withPersistentContext(async (context) => {
      const page = await context.newPage();
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
      await page.waitForTimeout(2000);
      await page.screenshot({ path: out });
    });
  }
  console.log(`Screenshot saved to ${out}`);
}

async function dashboard(section) {
  const token = getGatewayToken();

  // Try CDP first for co-browsing, fall back to persistent context
  const doWork = async (context) => {
    const page = await context.newPage();
    await page.goto(DASHBOARD_URL, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForTimeout(2000);

    // Auto-fill token if login screen
    const tokenInput = page.locator('input[placeholder*="OPENCLAW_GATEWAY_TOKEN"]');
    if (await tokenInput.isVisible().catch(() => false)) {
      await tokenInput.fill(token);
      await page.locator('button:has-text("Connect")').click();
      await page.waitForTimeout(3000);
    }

    // Navigate to section if specified
    if (section) {
      await page.locator(`text=${section}`).first().click().catch(() => {
        console.log(`Section "${section}" not found`);
      });
      await page.waitForTimeout(2000);
    }

    await page.screenshot({ path: '/tmp/dashboard.png', fullPage: true });
    console.log('Dashboard screenshot: /tmp/dashboard.png');
  };

  try {
    await withCDP(async (context) => doWork(context));
  } catch {
    await withPersistentContext(async (context) => doWork(context));
  }
}

async function sessionCheck() {
  try {
    await withPersistentContext(async (context) => {
      const page = await context.newPage();
      await page.goto(TG_BASE, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(8000);

      const bodyText = await page.locator('body').textContent().catch(() => '');
      const needsLogin = bodyText.includes('QR') || bodyText.includes('Log in') || bodyText.length < 200;

      if (needsLogin) {
        console.log('SESSION: EXPIRED — Telegram Web needs re-login (QR scan)');
        console.log('Fix: launch visible browser, scan QR, close browser');
        process.exit(1);
      } else {
        console.log('SESSION: ACTIVE — Telegram Web is logged in');
        process.exit(0);
      }
    });
  } catch (err) {
    console.log(`SESSION: ERROR — ${err.message}`);
    process.exit(1);
  }
}

async function cdpCheck(port) {
  const p = port || CDP_PORT;
  try {
    const resp = await fetch(`http://127.0.0.1:${p}/json/version`);
    const data = await resp.json();
    console.log(`CDP: ALIVE on port ${p}`);
    console.log(`  Browser: ${data.Browser}`);
    console.log(`  WebSocket: ${data.webSocketDebuggerUrl}`);

    const pages = await (await fetch(`http://127.0.0.1:${p}/json`)).json();
    console.log(`  Open tabs: ${pages.filter(p => p.type === 'page').length}`);
    process.exit(0);
  } catch {
    console.log(`CDP: NOT RUNNING on port ${p}`);
    process.exit(1);
  }
}

// --- CLI ---

const [,, command, ...args] = process.argv;

switch (command) {
  case 'telegram-read':
    await telegramRead(args[0] || '-5210450493');
    break;
  case 'telegram-send':
    await telegramSend(args[0] || '-5210450493', args.slice(1).join(' '));
    break;
  case 'telegram-screenshot':
    await telegramScreenshot(args[0] || '-5210450493');
    break;
  case 'screenshot':
    await screenshot(args[0], args[1]);
    break;
  case 'dashboard':
    await dashboard(args[0]);
    break;
  case 'session-check':
    await sessionCheck();
    break;
  case 'cdp-check':
    await cdpCheck(args[0]);
    break;
  default:
    console.log(`Usage: node browser.mjs <command> [args]

Commands:
  telegram-read [chatId]           Read latest messages (default: ACP group)
  telegram-send [chatId] <msg>     Send a message
  telegram-screenshot [chatId]     Screenshot a chat
  screenshot <url> [output]        Screenshot any URL
  dashboard [section]              Screenshot OpenClaw dashboard
  session-check                    Verify Telegram session is live
  cdp-check [port]                 Verify CDP browser is running

Chat IDs:
  -5210450493  Agent Coordination Protocol group

Environment:
  CDP_PORT     Chrome remote debugging port (default: 9222)
`);
}
