# Changelog

All notable changes to `puppetlabs-pe_mcp` are documented here.

## [1.0.1] - 2026-07-29

- **Breaking:** all 10 default MCP tools renamed with a `puppet_` prefix
  (e.g. `node_lookup` -> `puppet_node_lookup`) to follow the PAG
  Architecture Guide's tool-naming convention. Any existing MCP client
  configuration or automation calling tools by their old bare names must
  be updated.
- Added Dependabot config (pip + github-actions).

## [1.0.0] - 2026-07-29

- First tagged release. Fixed `puppet_agent` dependency pin (was
  resolving down to a broken `0.1.0` placeholder Forge release) and added
  the `inifile`/`apt`/`powershell`/`pwshlib` pins the module actually
  needs.
- Added `server.json` for MCP discovery-registry publishing.
