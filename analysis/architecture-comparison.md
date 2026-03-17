# Architecture comparison

## Gateway control plane
- **Documented intent:** `exploration/openclaw-architecture.md` Part II claims a WebSocket gateway with 95+ RPC methods, lane-based scheduling, and default `ws://127.0.0.1:18789`.
- **Actual evidence:** `install/dist/gateway-cli-CuZs0RlJ.js:16800` exports `coreGatewayHandlers`, `install/dist/gateway-cli-CuZs0RlJ.js:7519` implements `applyGatewayLaneConcurrency`, and the onboarding runtime still hard-codes `ws://127.0.0.1:18789` (`install/dist/onboard-remote-f25-fsZp.js:8`).

## Agent runtime & channels
- **Documented intent:** Parts III–IV describe the Pi Embedded Runner and 22+ channel adapters (Telegram, Discord, WhatsApp, Slack, etc.).
- **Actual evidence:** `install/package.json` depends on `@mariozechner/pi-coding-agent`, `install/dist/pi-tools.before-tool-call.runtime-*.js` bundles Pi runtimes, and each channel listed appears under `install/extensions` (`telegram`, `discord`, `whatsapp`, `slack`, `mattermost`, `signal`, `matrix`, `feishu`, etc.).

## Plugin SDK and skills
- **Documented intent:** Part V/VI plus Appendix B note 37 plugin extensions and 50+ bundled skills.
- **Actual evidence:** `install/extensions` currently contains 43 directories (acpx, bluebubbles, copilot-proxy, diagnostics-otel, memory-core, memory-lancedb, etc.), and `install/skills` contains 53 skill folders, reflecting at least the same coverage as the doc. The SDK sources under `install/dist/plugin-sdk` still expose the schemas referenced in the write-up.

## Memory system and config
- **Documented intent:** Part VII/VIII outline file-based `memory/YYYY-MM-DD.md` logs, hybrid BM25+vector search (SQLite + sqlite-vec + QMD), JSON5 configs, and Zod validation.
- **Actual evidence:** `install/dist/bundled/session-memory/handler.js` creates workspace `memory/` directories, `install/dist/reply-Bm8VrLQh.js` scans `memoryDir` and loads `sqlite-vec`, `install/dist/qmd-manager-*.js` implements BM25 keyword normalization, JSON5 parsing is used in `install/dist/reply-Bm8VrLQh.js` and numerous config helpers, and Zod schemas appear throughout the generated dist files (`install/dist/gateway-cli-CuZs0RlJ.js:99`, `install/dist/model-selection-46xMp11W.js` regions).

## Onboarding/configuration flows
- **Documented intent:** Onboarding wizard + CLI with JSON5 config hot reload, secrets via profiles, and port defaults.
- **Actual evidence:** `install/dist/config-cli-DrrG4KLm.js`, `install/dist/doctor-config-flow-DM9Q7QuP.js`, and `install/dist/onboard-remote-*.js` support those flows, and they keep referencing default port `18789` and config schema modules (`install/dist/plugin-sdk/config/…`).

## Summary
- The packaged `install/` tree implements the gateway control plane, Pi runtime, channel adapters, plugin/skill catalog, memory/log stack, and JSON5+Zod configuration exactly as described in the `exploration` notes. The shipped numbers even slightly exceed the documented counts (43 vs. 37 extensions, 53 vs. 50 skills). No additional source changes were made.
