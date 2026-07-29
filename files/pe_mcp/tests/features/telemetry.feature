Feature: OTel spans for MCP tool calls
  Telemetry spans use OTel semantic conventions and carry tool metadata
  without leaking tool arguments or result payloads.

  Scenario: A tool call emits a span with tool name attribute
    Given the MCP server is running with an OTel span recorder attached
    When the MCP client calls puppet_node_lookup
    Then exactly one tool span is recorded
    And the span has attribute "tool.name": "puppet_node_lookup"
    And the span has a non-zero duration

  Scenario: Error sets span status to ERROR
    Given the MCP server is running with an OTel span recorder attached
    And PE will respond to the next PuppetDB call with HTTP 429
    When the MCP client calls puppet_pql_query with query "nodes {}"
    Then the recorded span has status "ERROR"
    And the span has attribute "error.type": "rate_limited"
