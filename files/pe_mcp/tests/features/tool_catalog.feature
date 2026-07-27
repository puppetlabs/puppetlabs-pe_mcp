Feature: Tool catalog advertised to the MCP client
  The default catalog ships ten read-only tools: node_lookup,
  pql_query, recent_reports, resource_events, impact_scope,
  environment_status, node_facts, nodes_by_class, comply_results,
  and infrastructure_map. Every tool has a description and declares
  its input schema.

  Scenario: Server advertises every default tool on MCP initialize
    Given the MCP server is started with mock PE backends
    When an MCP client sends "tools/list"
    Then the response contains exactly 10 tool definitions
    And the tool names are:
      | node_lookup        |
      | pql_query          |
      | recent_reports     |
      | resource_events    |
      | impact_scope       |
      | environment_status |
      | node_facts         |
      | nodes_by_class     |
      | comply_results     |
      | infrastructure_map |

  Scenario: Every tool schema describes its purpose and inputs
    Given the MCP server is started with mock PE backends
    When an MCP client sends "tools/list"
    Then every tool has a non-empty "description" field
    And every tool declares its input schema
