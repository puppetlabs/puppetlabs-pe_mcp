# puppetlabs-pe_mcp

This puppet module deploys and validates a **Pupppet Enerprise MCP** (Model Context Protocol) FastMCP server.  This server, fronted by an SSL-terminating nginx reverse proxy, exposes various query tools that interact with an existing PE infrastructure.

Although this module can be installed like any other via `Puppetfile`/`metadata.json`; nevertheless it is primarily--at this stage--a standalone Bolt project:  Clone it, `bolt module install`, create an `inventory.yaml` pointing at your primary and a candidate agent, runt the `pe_mcp::deploy` plan and then you should have a new PE MCP standalone server.  See the  [[#Quickstart]] below for more information.

## Quickstart

### Prerequisites

- [Bolt](https://www.puppet.com/docs/bolt/latest/bolt_installing) >= 3.0 is installed
- A PE ecosystem with at least a primary and 1 agent.  No PE to test against yet?  For more information see [How to intall PE](https://help.puppet.com/pe/current/topics/installing.htm)
- PE admin credentials on the PE primary (`PE_ADMIN_PASSWORD`)

**Note**: Currently the agent must be Ubuntu 24.04 but this will be extended soon to a range of Linux OSs.

### (1) Point Bolt at your PE infrastructure

```bash
git clone https://github.com/puppetlabs/puppetlabs-pe_mcp.git
cd puppetlabs-pe_mcp

# install the puppetlabs-pe_mcp module for the bolt project (view the included bolt-project.yaml for more info)
bolt module install

# create an inventory (view the included inventory.yaml.example for a basic reference example)
vi inventory.yaml         # fill in your primary + target node(s)

# list the help and parameters for the `pe_mcp::deploy`
bolt plan show pe_mcp::deploy
```

`inventory.yaml` is gitignored — never commit real target hostnames/credentials.

### (2) Set the PE admin password

```bash
# used once to mint a short-lived RBAC token; never stored by you
export PE_ADMIN_PASSWORD='...'
```

`PE_ADMIN_PASSWORD` is read from the shell environment only; keep it out of git too (a local gitignored `.env`/`.envrc` works fine for development).

### (3) Deploy

```bash
# change the default token_lifetime for the MCP from 7 days to something larger to suit.
# For example:
bolt plan run pe_mcp::deploy \
  primary=<pe-primary-name> \
  targets=<mcp-node-name> \
  token_lifetime=10y
```

Expect:

```text
Step 1: Checking RBAC token on <mcp-node-name>
...
Step 2: Applying MCP server and nginx profiles
...
Step 3: Verifying MCP server
PASS: MCP server on <mcp-node-name> returned HTTP 200
"MCP deployment complete"
```

**What `pe_mcp::deploy` does**:

* Checks for an existing valid RBAC token on the target node; generates a new one on the PE primary via the REST RBAC API only if needed.
* Creates both the FastMCP and an nginx SSL-terminating reverse proxy.
* Verifies the deployed server responds correctly to an MCP `initialize` handshake over HTTPS.
### (4) Validate

```bash
bolt plan run pe_mcp::validate -i inventory.yaml targets=<mcp-node-name>
```

Expect:

```text
PASS: <mcp-node-name> — smart-mcp active, nginx active, MCP handshake HTTP 200
"Connectivity check passed"
```


**What `pe_mcp::validate` does**.  It does a few lightweight checks confirming:

* the FastMCP service is active, 
* the `nginx` is active, and 
* the server responds correctly to an MCP `initialize` handshake over HTTPS.

## Connect 

Once deployed, the server is reachable at `https://<mcp-node-fqdn>/mcp` (nginx terminates SSL using the target's own PE agent certificate, signed by your PE CA rather than a public one).

For more information on how to connect your AI client (claude, copilot, etc) to this MCP server, see [`puppetlabs/pe_mcp_docker`](https://github.com/puppetlabs/pe_mcp_docker).
