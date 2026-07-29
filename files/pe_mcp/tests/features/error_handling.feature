Feature: Coarse error classification for LLM consumption
  Errors returned to the LLM use exactly one of timeout, auth_failed,
  rate_limited, not_found, or tool_error. No raw upstream error bodies
  are forwarded.

  Scenario Outline: Known PE failure maps to the documented error_type
    Given PE will respond to the next PuppetDB call with <upstream_condition>
    When the MCP client calls <tool>
    Then the response is an error with "error_type": "<expected_type>"
    And the error message contains only curated text

    Examples:
      | upstream_condition            | tool           | expected_type |
      | HTTP 404                      | puppet_node_lookup    | not_found     |
      | HTTP 429                      | puppet_pql_query      | rate_limited  |
      | HTTP 503 after retry          | puppet_recent_reports | tool_error    |
      | connection reset mid-response | puppet_impact_scope   | timeout       |

  Scenario: error_type is always one of the five documented categories
    Given the MCP server is started with mock PE backends
    When multiple tool invocations are made with various failure modes
    Then every error response's "error_type" value is one of "timeout", "auth_failed", "rate_limited", "not_found", "tool_error"
