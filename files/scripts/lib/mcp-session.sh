#!/usr/bin/env bash
# Shared MCP session helper for verification scripts.
# Inlined into each script via cat during bolt invocation (bolt transfers
# only the file you hand it, so source-by-path is not possible).
#
# Provides:
#   mcp_session_init  — establish a Streamable HTTP session
#   mcp_call          — call a tool via JSON-RPC tools/call
#   mcp_tools_list    — call tools/list and return the JSON result

MCP_ENDPOINT="${MCP_ENDPOINT:-http://127.0.0.1:8200/mcp}"
MCP_SESSION_ID=""

mcp_session_init() {
  MCP_SESSION_ID=$(curl -s -D /dev/stderr "${MCP_ENDPOINT}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"0.1"}}}' \
    2>&1 1>/dev/null | grep -i 'mcp-session-id' | tr -d '\r' | awk '{print $2}')

  if [ -z "$MCP_SESSION_ID" ]; then
    echo "FAIL: no session ID returned from ${MCP_ENDPOINT}"
    return 1
  fi

  curl -s "${MCP_ENDPOINT}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: $MCP_SESSION_ID" \
    -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' > /dev/null 2>&1
}

mcp_call() {
  local tool_name="$1"
  local arguments="$2"
  local raw
  raw=$(curl -s "${MCP_ENDPOINT}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: $MCP_SESSION_ID" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"${tool_name}\",\"arguments\":${arguments}}}")
  if echo "$raw" | grep -q '^data: '; then
    echo "$raw" | grep '^data: ' | sed 's/^data: //'
  else
    echo "$raw"
  fi
}

mcp_tools_list() {
  local raw
  raw=$(curl -s "${MCP_ENDPOINT}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: $MCP_SESSION_ID" \
    -d '{"jsonrpc":"2.0","id":3,"method":"tools/list","params":{}}')
  if echo "$raw" | grep -q '^data: '; then
    echo "$raw" | grep '^data: ' | sed 's/^data: //'
  else
    echo "$raw"
  fi
}
