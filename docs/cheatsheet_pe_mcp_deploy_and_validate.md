# pe_mcp deploy and validate

Copy-paste commands for deploying and validating the PE MCP server with this module's Bolt plans.

## Quick Reference

| Task | Command / Pattern |
| --- | --- |
| Install project modules | `bolt module install` |
| Deploy MCP server to a target | `bolt plan run pe_mcp::deploy -i inventory.yaml primary=<primary> targets=<mcp-node>` |
| Validate a deployment | `bolt plan run pe_mcp::validate -i inventory.yaml targets=<mcp-node>` |
| Show deploy plan's full parameter list | `bolt plan show pe_mcp::deploy` |

## Quick Start
### Initialize bolt and install the module

```bash
# initialize a clean bolt project (2 files generated: bolt-project.yaml and inventory.yaml)
mkdir pe_mcp && cd pe_mcp
bolt project init pe_mcp

# add this module to the bolt project
cat <<- 'EOF' > bolt-project.yaml
---
name: pe_mcp
modules:
  - git: https://github.com/puppetlabs/puppetlabs-pe_mcp.git
    ref: main
EOF

# install the module locally to .modules (use `--force` if you're re-installing modules)
bolt module install
```

Finally, configure your bolt `inventory.yaml` to connect to both your primary and "clean" MCP server.  For a sample inventory, see the [[#Sample inventory]] below.
### Deploy

Before running anything bolt, make sure **(1)** to set `PE_ADMIN_PASSWORD` equal to the primary's admin password **BEFORE** running `pe_mcp::deploy`.

```bash
# VERY IMPORTANT: set the PE_ADMIN_PASSWORD so that bolt can generate a token for the MCP server
export PE_ADMIN_PASSWORD='...'   # minted into a short-lived RBAC token, never stored by you

# deploy the MCP server to the <mcp-node-name> giving it a token with 1y ttl
bolt plan run pe_mcp::deploy -i inventory.yaml primary=<pe-primary-name> targets=<mcp-node-name> token_lifetime=1y

# verified 2026-08-05 on raw-millennium: "RBAC token generated successfully" ->
# "PASS: MCP server on raw-millennium returned HTTP 200" (2 min 36 sec end to end)
```

This plan generates a token for the new MCP server, configures nginx, and verifies the MCP server is healthy.

> 📖 **Deeper dive:** [[explanation_server_side_vs_client_side_rbac_tokens_in_the_pe_mcp_stack]]

### Validate

Validate that the new MCP server is healthy.

```bash
bolt plan run pe_mcp::validate -i inventory.yaml targets=<mcp-node-name>
# Confirms smart-mcp active, nginx active, MCP initialize handshake == HTTP 200.
# verified 2026-08-05 on raw-millennium before deploy: exit code 7, http code 000
# verified 2026-08-05 on raw-millennium after deploy:  "PASS: ... handshake HTTP 200"
```

## Appendix

### Sample inventory

```yaml
---
targets:
- name: bathyran-double
  uri: bathyran-double.delivery.puppetlabs.net
  vars:
    type: ubuntu-2404-x86_64
    ttl: 2026-08-08 23:04
- name: raw-millennium
  uri: raw-millennium.delivery.puppetlabs.net
  vars:
    type: ubuntu-2404-x86_64
    ttl: 2026-08-08 23:04
groups:
- name: linux
  config:
    transport: ssh
    ssh:
      native-ssh: true
      copy-command:
      - scp
      - "-r"
      - "-O"
      load-config: true
      login-shell: bash
      tty: false
      host-key-check: false
      run-as: root
      user: root
  facts:
    role: linux
  targets:
  - bathyran-double
  - raw-millennium
  groups:
  - name: primary
    targets:
      - bathyran-double
  - name: pe_mcp
    targets:
      - raw-millennium
```

