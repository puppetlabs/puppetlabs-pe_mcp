Feature: Audit trail attribution for tool invocations
  Every tool invocation emits an audit event with caller identity,
  tool name, outcome, trace_id, and timestamp.

  Scenario: Successful tool call emits audit event with outcome "success"
    Given the MCP server is started with audit logging enabled
    When the MCP client calls node_lookup
    Then an audit event is emitted with tool "node_lookup" and outcome "success"
    And the audit event contains a non-empty trace_id
    And the audit event actor is not "unknown"

  Scenario: Failed tool call emits audit event with outcome "error"
    Given the MCP server is started with audit logging enabled
    And PE will respond to the next PuppetDB call with HTTP 404
    When the MCP client calls node_lookup
    Then an audit event is emitted with tool "node_lookup" and outcome "error"

  Scenario: Per-request caller identity is propagated from HTTP header
    Given the MCP server is started with audit logging enabled
    And the request includes header "X-PE-MCP-Caller-Id" with value "alice@example.com"
    When the MCP client calls node_lookup
    Then an audit event is emitted with tool "node_lookup" and outcome "success"
    And the audit event actor is "alice@example.com"
