# External Tools Reference

## BloTato (Social Media Posting)

Multi-platform social media publishing API.

- **Base URL:** `https://backend.blotato.com/v2`
- **Auth header:** `blotato-api-key: $BLOTATO_API_KEY` (NOT Bearer token)
- **Docs:** https://help.blotato.com/api/
- **LLM-optimized docs:** https://help.blotato.com/api/llm
- **Debug dashboard:** https://my.blotato.com/api-dashboard

### Step 0: Get Your Account IDs (MUST DO FIRST)
```bash
curl -s https://backend.blotato.com/v2/users/me/accounts \
  -H "blotato-api-key: $BLOTATO_API_KEY"
```
Save the `id` from each account — you need it as `accountId` for every post.
For Facebook/LinkedIn, also fetch subaccounts to get `pageId`.

### Publish a Post
```bash
curl -X POST https://backend.blotato.com/v2/posts \
  -H "Content-Type: application/json" \
  -H "blotato-api-key: $BLOTATO_API_KEY" \
  -d '{
    "post": {
      "accountId": "<from step 0>",
      "content": {
        "text": "Post content here",
        "mediaUrls": [],
        "platform": "twitter"
      },
      "target": {
        "targetType": "twitter"
      }
    }
  }'
```

### Schedule a Post
Add `"scheduledTime": "2026-03-20T15:30:00Z"` at the top level (outside `post`).
Or use `"useNextFreeSlot": true` to auto-schedule at next available calendar slot.

### Twitter Thread
Add `"additionalPosts": [{"text": "tweet 2", "mediaUrls": []}]` inside `content`.

### Attach Media
Pass publicly accessible URLs in `mediaUrls` — no upload step required. BloTato handles transfer.

### Rate Limits
- Publishing: 30 requests/minute
- Media uploads: 10 requests/minute

### Platform targetTypes
`twitter`, `instagram`, `linkedin`, `facebook`, `tiktok`, `youtube`, `threads`, `bluesky`, `pinterest`

### Notes
- Each platform needs its own POST call with matching `accountId` and `targetType`
- If account not connected, API returns error — log as F1, produce ready-to-publish content instead
- For LinkedIn company pages, you need `pageId` from subaccounts endpoint

## Vercel (Website Deployment)

- **CLI:** `vercel` (globally installed)
- **Auth:** `$VERCEL_TOKEN` environment variable

### Deploy to Production
```bash
cd /path/to/project
vercel --prod --token $VERCEL_TOKEN --yes
```

### Link a Project
```bash
vercel link --token $VERCEL_TOKEN --yes
```

## GitHub (Repository Management)

- **CLI:** `gh` (authenticated as `cbassist`)
- **Org:** All repos go under `cbassist` — this is the active GitHub account
- Vercel is connected to the `cbassist` GitHub org for auto-deploy

### Create Repository
```bash
# Create under cbassist org (default active account)
gh repo create cbassist/1215-labs-site --public --source . --push
```

### Clone an Existing Repo
```bash
gh repo clone cbassist/<repo-name>
```

### Check Auth
```bash
gh auth status
gh api user --jq '.login'  # Should return "cbassist"
```

## Archon (Task Management)

Tasks managed via Archon MCP server.

- Status flow: `todo` → `doing` → `review` → `done`
- As an agent, move tasks to `review` — never mark `done` yourself
- Log progress in task descriptions or as updates
