# puppetlabs-pe_mcp

Bolt plans and a Puppet module for deploying and validating the **PE MCP** (Model
Context Protocol) server — a read-only FastMCP server exposing PuppetDB/PE query
tools — onto existing Puppet Enterprise infrastructure, fronted by an SSL-terminating
nginx reverse proxy.

## What this is

A pure Puppet module (installable via `Puppetfile`/`metadata.json` like any other
Puppet module) that also runs standalone as its own Bolt project. Clone it, point it
at your PE infrastructure with an `inventory.yaml`, and run its plans directly —
no separate control repo required.

## Prerequisites

- [Bolt](https://www.puppet.com/docs/bolt/latest/bolt_installing) >= 3.0
- A reachable PE primary (for RBAC token generation) and one or more agent-enrolled
  target nodes (Debian/Ubuntu) to host the MCP server
- Admin credentials on the PE primary (`PE_ADMIN_PASSWORD`)

## Quickstart

```bash
git clone https://github.com/puppetlabs/puppetlabs-pe_mcp.git
cd puppetlabs-pe_mcp

# Resolve module dependencies (puppet_agent, stdlib) into .modules/
bolt module install

# Point at your PE infrastructure
cp inventory.yaml.example inventory.yaml
$EDITOR inventory.yaml   # fill in your primary + target node(s)

# Set the PE admin password used to mint an RBAC token
export PE_ADMIN_PASSWORD='...'

# Deploy the MCP server + nginx proxy to a target node
bolt plan run pe_mcp::deploy -i inventory.yaml \
  primary=<pe-primary-name> targets=<mcp-node-name>

# Validate the deployment with a connectivity check
bolt plan run pe_mcp::validate -i inventory.yaml targets=<mcp-node-name>
```

`inventory.yaml` is gitignored — never commit real target hostnames/credentials.
`PE_ADMIN_PASSWORD` is read from the shell environment only; keep it out of git too
(a local gitignored `.env`/`.envrc` works fine for development).

## What `pe_mcp::deploy` does

1. Checks for an existing valid RBAC token on the target node; generates a new one
   on the PE primary via the REST RBAC API only if needed.
2. Applies `pe_mcp::server` (Python venv, FastMCP, the vendored `pe_mcp` server
   package, and a systemd service) and `pe_mcp::nginx` (SSL-terminating reverse
   proxy using the target's own PE agent certificate) to the target node.
3. Verifies the deployed server responds correctly to an MCP `initialize` handshake
   over HTTPS.

## What `pe_mcp::validate` does

A single, self-contained connectivity check: confirms the `smart-mcp` systemd
service is active, `nginx` is active, and the server responds correctly to an
MCP `initialize` handshake over HTTPS. Nothing is uploaded to the target — it's
just a few `run_command()` calls.

This is intentionally lightweight. The full acceptance-criteria test suite (tool
registry, error envelopes, structured/audit logging, and the rest) is maintained
separately in the private `pe_mcp_control_repo` development repo, not shipped as
part of this module.

## Connecting Claude Code to a deployed server

Once deployed, the server is reachable at `https://<mcp-node-fqdn>/mcp` (nginx
terminates SSL using the target's own PE agent certificate). Add to your Claude
Code MCP configuration:

```json
{
  "mcpServers": {
    "pe-mcp": {
      "url": "https://<mcp-node-fqdn>/mcp"
    }
  }
}
```

The certificate is signed by your PE CA, not a public CA — if your MCP client
validates certificates strictly, trust the PE CA cert
(`/etc/puppetlabs/puppet/ssl/certs/ca.pem` on any PE-enrolled node) or configure
your client to trust it explicitly.

## Using as a module dependency

This module can also be installed as a dependency of another Bolt project or
control repo, the same way as any other Puppet module:

```ruby
# Puppetfile
mod 'puppetlabs/pe_mcp', '0.1.0'
```

```yaml
# bolt-project.yaml
modules:
  - puppetlabs/pe_mcp
```

Then `bolt plan run pe_mcp::deploy ...` / `pe_mcp::validate ...` work identically
from that project.

## Troubleshooting

- **"CA cert path does not exist"** — the server can't find the PE CA cert; check
  `/etc/puppetlabs/puppet/ssl/certs/ca.pem` exists on the target node.
- **"RBAC token is empty"** — the token file at `/opt/smart-mcp/rbac_token` is
  missing or empty; re-run `pe_mcp::deploy` to regenerate it.
- **"Upstream unavailable: PE rejected the RBAC token"** — the token expired or
  lacks read permissions; re-run `pe_mcp::deploy` (it detects an invalid token and
  mints a new one automatically).

## License

Apache-2.0
