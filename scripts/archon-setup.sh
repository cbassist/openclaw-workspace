#!/usr/bin/env bash
# Configure Archon RAG settings and upload architecture docs
# Usage: ./scripts/archon-setup.sh [--config-only | --upload-only]

set -euo pipefail

ARCHON_API="http://localhost:8181"
ARCH_DIR="exploration/architecture"
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"

# --- Health check ---
echo "Checking Archon API..."
if ! curl -sf "$ARCHON_API/health" > /dev/null 2>&1; then
  echo "ERROR: Archon API not reachable at $ARCHON_API"
  exit 1
fi
echo "Archon API is healthy."

# --- Configure RAG settings ---
configure_settings() {
  echo ""
  echo "=== Configuring RAG Strategy ==="

  local settings=(
    "EMBEDDING_MODEL|text-embedding-3-large|rag_strategy|OpenAI large embeddings for higher semantic precision (3072 dims)"
    "USE_CONTEXTUAL_EMBEDDINGS|true|rag_strategy|Embed chunks with full document context awareness"
    "USE_HYBRID_SEARCH|true|rag_strategy|Combine vector + BM25 keyword search"
    "USE_RERANKING|true|rag_strategy|CrossEncoder reranking for precision"
    "ENABLE_DIAGRAM_FILTERING|true|rag_strategy|Exclude ASCII diagrams from code extraction"
    "ENABLE_CODE_SUMMARIES|true|rag_strategy|Auto-summarize extracted code blocks"
  )

  for entry in "${settings[@]}"; do
    IFS='|' read -r key value category description <<< "$entry"
    echo "  Setting $key = $value"
    curl -sf -X POST "$ARCHON_API/api/credentials" \
      -H "Content-Type: application/json" \
      -d "{\"key\": \"$key\", \"value\": \"$value\", \"is_encrypted\": false, \"category\": \"$category\", \"description\": \"$description\"}" \
      > /dev/null
  done

  echo "RAG settings configured."
}

# --- Upload architecture docs ---
upload_docs() {
  echo ""
  echo "=== Uploading Architecture Docs ==="

  local docs=(
    "01-system-overview.md|system-overview"
    "02-gateway.md|gateway"
    "03-agent-runtime.md|agent-runtime"
    "04-channels-routing.md|channels-routing"
    "05-plugins-skills.md|plugins-skills"
    "06-memory.md|memory"
    "07-memory-adoption.md|memory-adoption"
    "08-appendices.md|appendices"
  )

  for entry in "${docs[@]}"; do
    IFS='|' read -r filename section_tag <<< "$entry"
    local filepath="$WORKSPACE/$ARCH_DIR/$filename"

    if [ ! -f "$filepath" ]; then
      echo "  SKIP: $filename (not found)"
      continue
    fi

    echo "  Uploading $filename..."
    local response
    response=$(curl -sf -X POST "$ARCHON_API/api/documents/upload" \
      -F "file=@$filepath" \
      -F "knowledge_type=technical" \
      -F "tags=[\"architecture\", \"openclaw\", \"$section_tag\"]" \
      -F "extract_code_examples=true")

    local progress_id
    progress_id=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('progressId',''))" 2>/dev/null || echo "")

    if [ -n "$progress_id" ]; then
      echo "    Started (progress: $progress_id)"
      # Poll until complete
      local status="processing"
      while [ "$status" = "processing" ] || [ "$status" = "pending" ]; do
        sleep 2
        local progress
        progress=$(curl -sf "$ARCHON_API/api/crawl-progress/$progress_id" 2>/dev/null || echo '{"status":"unknown"}')
        status=$(echo "$progress" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
        local pct
        pct=$(echo "$progress" | python3 -c "import sys,json; print(json.load(sys.stdin).get('progress',0))" 2>/dev/null || echo "?")
        printf "    Progress: %s (%s%%)\r" "$status" "$pct"
      done
      echo "    Done: $status                    "
    else
      echo "    Response: $response"
    fi
  done

  echo ""
  echo "Upload complete. Verify sources:"
  echo "  curl -s $ARCHON_API/api/knowledge-items | python3 -m json.tool"
}

# --- Main ---
case "${1:-all}" in
  --config-only) configure_settings ;;
  --upload-only) upload_docs ;;
  all) configure_settings; upload_docs ;;
  *)
    echo "Usage: $0 [--config-only | --upload-only]"
    exit 1
    ;;
esac

echo ""
echo "Done. Run /drift-check in Claude Code to verify RAG search quality."
