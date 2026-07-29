Feature: Tool catalog advertised to the MCP client
  The default catalog ships ten read-only tools: puppet_node_lookup,
  puppet_pql_query, puppet_recent_reports, puppet_resource_events, puppet_impact_scope,
  puppet_environment_status, puppet_node_facts, puppet_nodes_by_class, puppet_comply_results,
  and puppet_infrastructure_map. Every tool has a description and declares
  its input schema.

  Scenario: Server advertises every default tool on MCP initialize
    Given the MCP server is started with mock PE backends
    When an MCP client sends "tools/list"
    Then the response contains exactly 10 tool definitions
    And the tool names are:
      | puppet_node_lookup        |
      | puppet_pql_query          |
      | puppet_recent_reports     |
      | puppet_resource_events    |
      | puppet_impact_scope       |
      | puppet_environment_status |
      | puppet_node_facts         |
      | puppet_nodes_by_class     |
      | puppet_comply_results     |
      | puppet_infrastructure_map |

  Scenario: Every tool schema describes its purpose and inputs
    Given the MCP server is started with mock PE backends
    When an MCP client sends "tools/list"
    Then every tool has a non-empty "description" field
    And every tool declares its input schema
