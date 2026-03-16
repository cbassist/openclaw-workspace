#!/usr/bin/env bash
# Configure Archon RAG settings and manage architecture doc sources
# Usage: ./scripts/archon-setup.sh [--config-only | --upload-only | --refresh <file> | --list | --delete <source_id>]

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

# --- List current sources ---
list_sources() {
  echo ""
  echo "=== Current Archon RAG Sources ==="
  curl -sf "$ARCHON_API/api/knowledge-items" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('items', data.get('sources', []))
print(f'{'Source ID':<50} {'Title':<35} {'Words':>6}')
print('-' * 95)
for item in items:
    sid = item.get('source_id', item.get('id', ''))
    title = item.get('title', item.get('name', ''))
    words = item.get('total_words', '?')
    print(f'{sid:<50} {title:<35} {words:>6}')
print(f'\nTotal: {len(items)} sources')
"
}

# --- Delete a source ---
delete_source() {
  local source_id="$1"
  echo "Deleting source: $source_id"
  local response
  response=$(curl -sf -X DELETE "$ARCHON_API/api/knowledge-items/$source_id")
  echo "  $response"
}

# --- Refresh a single doc (delete old + re-upload) ---
refresh_doc() {
  local filename="$1"
  local filepath="$WORKSPACE/$ARCH_DIR/$filename"

  if [ ! -f "$filepath" ]; then
    echo "ERROR: $filepath not found"
    exit 1
  fi

  # Derive source_id from filename pattern: file_<name-without-ext>_md_<hash>
  local base
  base=$(basename "$filename" .md)
  echo "Refreshing $filename..."

  # Find existing source ID
  local old_source_id
  old_source_id=$(curl -sf "$ARCHON_API/api/knowledge-items" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('items', data.get('sources', []))
for item in items:
    sid = item.get('source_id', item.get('id', ''))
    if '${base}' in sid:
        print(sid)
        break
" 2>/dev/null || echo "")

  if [ -n "$old_source_id" ]; then
    echo "  Deleting old source: $old_source_id"
    curl -sf -X DELETE "$ARCHON_API/api/knowledge-items/$old_source_id" > /dev/null
  else
    echo "  No existing source found (new upload)"
  fi

  # Derive section tag from filename
  local section_tag
  section_tag=$(echo "$base" | sed 's/^[0-9]*-//')

  echo "  Uploading new version..."
  local response
  response=$(curl -sf -X POST "$ARCHON_API/api/documents/upload" \
    -F "file=@$filepath" \
    -F "knowledge_type=technical" \
    -F "tags=[\"architecture\", \"openclaw\", \"$section_tag\"]" \
    -F "extract_code_examples=true")

  local progress_id
  progress_id=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('progressId',''))" 2>/dev/null || echo "")

  if [ -n "$progress_id" ]; then
    local status="processing"
    while [ "$status" = "processing" ] || [ "$status" = "pending" ]; do
      sleep 2
      local progress
      progress=$(curl -sf "$ARCHON_API/api/crawl-progress/$progress_id" 2>/dev/null || echo '{"status":"unknown"}')
      status=$(echo "$progress" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
    done
    echo "  Done: $status"
  else
    echo "  Response: $response"
  fi

  # Print new source ID
  echo "  New source ID:"
  curl -sf "$ARCHON_API/api/knowledge-items" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('items', data.get('sources', []))
for item in items:
    sid = item.get('source_id', item.get('id', ''))
    if '${base}' in sid:
        print(f'    {sid}')
        break
" 2>/dev/null
  echo "  Remember to update exploration/archon-rag-strategy.md if the source ID changed."
}

# --- Main ---
case "${1:-all}" in
  --config-only) configure_settings ;;
  --upload-only) upload_docs ;;
  --list) list_sources ;;
  --delete) delete_source "${2:?Usage: $0 --delete <source_id>}" ;;
  --refresh) refresh_doc "${2:?Usage: $0 --refresh <filename.md>}" ;;
  all) configure_settings; upload_docs ;;
  *)
    echo "Usage: $0 [--config-only | --upload-only | --refresh <file.md> | --list | --delete <source_id>]"
    exit 1
    ;;
esac

echo ""
echo "Done. Run /drift-check in Claude Code to verify RAG search quality."
