What you’re trying to build — **multiple OpenClaw agents represented by Telegram bots collaborating in a group chat** — runs directly into several **Telegram Bot API design constraints**. Most people hit exactly the behavior you described (works in DM but bots “see nothing” in groups).

Below is the **actual set of rules Telegram enforces**, plus the **practical fixes**.

---

# 1. The biggest hidden rule: bots cannot receive messages from other bots

This is the #1 thing that breaks multi-agent Telegram setups.

**Telegram Bot API rule:**

> Bots with privacy disabled or admin status receive all group messages **except messages sent by other bots**. ([Telegram Core][1])

Meaning:

| Sender        | Bot receives message?             |
| ------------- | --------------------------------- |
| Human → bot   | ✅ Yes                             |
| Human → group | ✅ Yes (if privacy disabled/admin) |
| Bot → group   | ❌ **No other bots will see it**   |

This is deliberate to prevent bot loops and spam.

**Implication for your architecture**

Your agent-bots cannot talk to each other through Telegram alone.

Even with:

* privacy mode OFF
* bot as group admin
* full permissions

**Bots will still never see messages sent by other bots.**

This is why your “agent group chat” appears silent.

---

# 2. Privacy mode behavior (important but not your main issue)

Telegram protects group chats by default.

When **privacy mode is ON**:

* bot receives only:

  * `/commands`
  * messages mentioning `@botname`

When **privacy mode is OFF**:

* bot receives **all human messages** in the group. ([Papercraft][2])

Fix:

```
@BotFather
/setprivacy
Disable
```

But this alone **does not solve bot-to-bot messaging**.

---

# 3. Telegram requires re-adding the bot after privacy changes

If you changed privacy mode already, Telegram does **not apply it retroactively**.

You must:

1. `/setprivacy` → Disable
2. Remove bot from group
3. Re-add bot
4. Send a message in the group

Otherwise the bot still behaves like privacy mode is enabled. ([OpenClaw][3])

---

# 4. Bots must be admins to reliably see group traffic

Another common gotcha.

If you want your bot to observe everything:

**Make bot admin in the group.**

Admin bots automatically receive group messages regardless of privacy settings. ([Stack Overflow][4])

Permissions needed:

* Read messages
* Send messages
* Optional: delete / manage

---

# 5. OpenClaw-specific gotcha: allowlists

OpenClaw adds its own security layer.

If you see logs like:

```
skipping group message
sender not allowed
group not allowlisted
```

then check config.

Example config:

```yaml
telegram:
  token: xxx
  allowedUsers:
    - 123456789
  groupPolicy: allowlist
  groupAllowFrom:
    - -1001234567890
```

If `groupPolicy: allowlist` is enabled and the group ID isn't added, the bot will ignore the group.

---

# 6. Architecture reality: Telegram cannot be the agent bus

Because bots cannot see other bots, **Telegram cannot function as an agent-to-agent communication layer**.

This explains exactly what you observed.

Your agents can only see:

```
Human → Telegram → bot
```

But never:

```
Bot → Telegram → other bot
```

---

# 7. Correct architecture for multi-agent Telegram systems

What you actually want is:

```
            Telegram UI
                │
        (human messages)
                │
           Gateway agent
                │
        ┌───────┴────────┐
        │                │
     Agent A          Agent B
        │                │
        └─────Shared Memory─────┘
              (Supabase/MCP)
```

Agents communicate through:

* database
* message queue
* internal API

NOT Telegram.

Telegram becomes **just the human interface layer**.

---

# 8. Recommended architecture for your setup

Based on what you said you already have:

You already run:

* Claude Code agent
* OpenClaw agent
* Supabase MCP memory

Perfect.

Use Telegram only as **user input**.

Agent communication happens via:

```
Supabase
Redis
NATS
RabbitMQ
```

Example flow:

```
User → Telegram → Agent A
Agent A writes task to DB
Agent B picks task from DB
Agent B responds
Agent A posts result to Telegram
```

From the user's perspective it still looks like a group conversation.

---

# 9. If you really want “multiple personalities” in Telegram

You can simulate multi-agents with **one bot token**.

Example:

```
/ask planner
/ask researcher
/ask coder
```

Internally route to agents.

But Telegram only sees **one bot identity**.

---

# 10. Checklist to debug your current setup

Run through this in order:

1️⃣ `/setprivacy → Disable`
2️⃣ Remove bot from group
3️⃣ Re-add bot
4️⃣ Make bot **group admin**
5️⃣ Confirm group ID in OpenClaw config
6️⃣ Check OpenClaw logs for "skipping group message"
7️⃣ Remember: **bots cannot see other bots**

---

# If you'd like

I can also show you the **best architecture for a Telegram-controlled multi-agent system** (the pattern used by many autonomous agent labs), including:

* Telegram → gateway agent
* agent bus
* memory layers
* escalation to frontier models
* multi-agent debate in the background

It’s actually a **very elegant system once you stop trying to use Telegram as the agent network.**

[1]: https://core.telegram.org/bots/faq?utm_source=chatgpt.com "Bots FAQ"
[2]: https://papercraft.tmat.me/book/chats/groups?utm_source=chatgpt.com "Developing Telegram Bots for Groups - Papercraft"
[3]: https://docs.openclaw.ai/channels/telegram?utm_source=chatgpt.com "Telegram - OpenClaw"
[4]: https://stackoverflow.com/questions/69371489/setprivacy-is-not-working-with-my-telegram-bot?utm_source=chatgpt.com "/setprivacy is not working with my Telegram bot"
