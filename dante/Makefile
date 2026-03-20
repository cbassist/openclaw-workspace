# Donna — local development commands
# Requires: uv, node/npm, ffmpeg

.PHONY: install bot gateway miniapp tunnel all help

help: ## Show this help
	@grep -E '^[a-z][a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	uv sync
	cd miniapp && npm install

bot: ## Start the Telegram bot (Phase 1 + 2)
	uv run python bot.py

gateway: ## Start the FastAPI voice gateway (Phase 2, port 8765)
	uv run uvicorn gateway.server:app --host 0.0.0.0 --port 8765 --reload

miniapp: ## Start the React Mini App dev server (Phase 2, port 5173)
	cd miniapp && npm run dev

tunnel: ## Start Cloudflare tunnel to Mini App (Phase 2, HTTPS required)
	@echo "Starting Cloudflare tunnel to localhost:5173..."
	@echo "Copy the URL and set MINIAPP_URL in .env"
	cloudflared tunnel --url http://localhost:5173

# --- Combined ---

phase1: install bot ## Phase 1: install deps + start bot (voice notes only)

all: ## Start all Phase 2 services (run in separate terminals)
	@echo "Run these in separate terminals:"
	@echo "  make bot       # Telegram bot"
	@echo "  make gateway   # FastAPI gateway (port 8765)"
	@echo "  make miniapp   # React Mini App (port 5173)"
	@echo "  make tunnel    # Cloudflare HTTPS tunnel"
	@echo ""
	@echo "Ports:"
	@echo "  Bot:     polling (no port)"
	@echo "  Gateway: http://localhost:8765"
	@echo "  MiniApp: http://localhost:5173"
	@echo "  Tunnel:  https://<random>.trycloudflare.com -> 5173"
