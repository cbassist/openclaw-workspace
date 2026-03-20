# API Quickstart

## Get Started with Blotato API

The Blotato API allows you to:

* publish and schedule posts directly to social media platforms
* supports text, image, videos, reels, slideshows, carousels, threads, and stories
* create images, videos, slideshows, and carousels programmatically via templates

It is limited to paying subscribers in order to reduce spam and service abuse, keeping Blotato's integration in good standing with the social platforms.

***

## 1. Get Your API Key

:exclamation:**IMPORTANT: this will end your free trial immediately and start your paid subscription.**

Go to [Settings](https://my.blotato.com/settings) > API > click "Generate API Key".

***

## 2. Connect Social Accounts

Go to [Settings](https://my.blotato.com/settings) and connect your social accounts. If you get stuck, more information here:

{% embed url="<https://help.blotato.com/settings/social-accounts>" %}

***

## 3. Install the Official Blotato Node

### n8n

1. Go to your n8n Admin Panel > Settings
2. Enable Verified Community Nodes
3. Open any workflow
4. Click the "+" icon in the top right corner
5. Search for "Blotato"
6. Click Install

For self-hosted n8n, see: [Self-Hosted n8n Users](https://help.blotato.com/api/n8n/n8n-blotato-node#self-hosted-n8n-users)

### Make

1. Open any scenario in Make
2. Click the "+" icon to add a module
3. Search for "Blotato"
4. Select the Blotato module

***

## 4. Setup Your First Automation!

**New to building automations?** Start here:

* [Build Your First AI Automation](https://help.blotato.com/api/templates/11-build-your-first-ai-automation) - Learn how to extract content from any source and publish to social media

Choose your preferred integration path:

* [MCP Server](https://help.blotato.com/api/mcp) - control Blotato from Claude Desktop, Claude Code, or Cursor with natural language
* [n8n - post everywhere](https://help.blotato.com/api/templates/1-post-everywhere)
* [Make - post everywhere](https://help.blotato.com/api/templates/1-post-everywhere)
* [REST API - OpenAPI reference](https://help.blotato.com/api/openapi-reference) and [Examples Below](#raw-rest-api-calls-examples)

Blotato has official Make.com and n8n nodes. Zapier coming soon!

Check out more workflow automation templates here:

{% embed url="<https://help.blotato.com/api/templates>" %}

***

## 5. Troubleshoot Errors

Use the API Dashboard and click on each request to see full payload, response, and error message:

**API Dashboard (for debugging):** <https://my.blotato.com/api-dashboard>

***

## Raw REST API Calls - Examples

### Authentication

To authenticate API requests, include your Blotato API key in the request headers.

**Authentication Header**

```
blotato-api-key: YOUR_API_KEY
```

Requests without a valid API key will be rejected and 401 error will be returned.

### Step 0: Get Your Account IDs

Before publishing, fetch your connected accounts to get the `accountId`:

```
GET https://backend.blotato.com/v2/users/me/accounts HTTP/1.1
blotato-api-key: YOUR_API_KEY
```

Use the `id` from the response as your `accountId`. For Facebook and LinkedIn, also fetch subaccounts to get `pageId`. See [Accounts reference](https://help.blotato.com/api/accounts) for details.

### Post to a Platform Immediately

```
POST https://backend.blotato.com/v2/posts HTTP/1.1
Content-Type: application/json
blotato-api-key: YOUR_API_KEY

{
  "post": {
    "accountId": "98432",
    "content": {
      "text": "Hello, world!",
      "mediaUrls": [],
      "platform": "twitter"
    },
    "target": {
      "targetType": "twitter"
    }
  }
}
```

### Post at a Scheduled Time

```
POST https://backend.blotato.com/v2/posts HTTP/1.1
Content-Type: application/json
blotato-api-key: YOUR_API_KEY

{
  "post": {
    "accountId": "98432",
    "content": {
      "text": "Scheduled post example",
      "mediaUrls": [],
      "platform": "facebook"
    },
    "target": {
      "targetType": "facebook",
      "pageId": "987654321"
    }
  },
  "scheduledTime": "2025-03-10T15:30:00Z"
}
```

To schedule at the user's next available calendar slot instead of a specific time, replace `scheduledTime` with `useNextFreeSlot: true`. Both are top-level fields, not inside `post`. See [Publish Post](https://help.blotato.com/api/publish-post) for all scheduling options.

### Post a Twitter Thread with Multiple Posts

```
POST https://backend.blotato.com/v2/posts HTTP/1.1
Content-Type: application/json
blotato-api-key: YOUR_API_KEY

{
  "post": {
    "accountId": "98432",
    "content": {
      "text": "This is the first tweet in the thread.",
      "mediaUrls": [],
      "platform": "twitter",
      "additionalPosts": [
        {
          "text": "Here's the second tweet, adding more info.",
          "mediaUrls": []
        },
        {
          "text": "And here's the third tweet to conclude!",
          "mediaUrls": []
        }
      ]
    },
    "target": {
      "targetType": "twitter"
    }
  }
}
```

### Attach Media to Post (images and videos)

Pass any publicly accessible image/video URL into the `mediaUrls` parameter. No upload step required. Blotato handles the media transfer.

```
POST https://backend.blotato.com/v2/posts HTTP/1.1
Content-Type: application/json
blotato-api-key: YOUR_API_KEY

{
  "post": {
    "accountId": "98432",
    "content": {
      "text": "Check out this image!",
      "mediaUrls": [
        "https://example.com/image.jpg"
      ],
      "platform": "instagram"
    },
    "target": {
      "targetType": "instagram"
    }
  }
}
```

The optional Upload Media endpoint is still available if you need to host media on Blotato's servers. See [Upload Media](https://help.blotato.com/api/publish-post/upload-media-v2-media).

***

## For AI Agents

If you are an AI agent or LLM integration, start with the plain-text API reference:

[API Reference for LLMs](https://help.blotato.com/api/llm)

This contains the full API specification in a format optimized for LLMs, including all endpoints, parameters, status values, and a complete workflow pseudocode.

For async workflow patterns and code examples, see [Protocol and Recipes](https://help.blotato.com/api/workflows).

For the full endpoint reference, see [API Reference](https://github.com/Blotato-Inc/help.blotato.com/blob/main/api/api-reference/README.md).
