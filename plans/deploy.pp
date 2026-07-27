# @summary Deploy PE MCP smart server to an agent node
#
# Orchestrates: generate RBAC token on primary, apply server +
# nginx profiles on the target node, verify MCP handshake.
#
# Requires PE_ADMIN_PASSWORD environment variable to be set.
#
# @param targets Agent node(s) to deploy the MCP server on.
# @param primary PE primary server (for RBAC token generation).
# @param token_lifetime RBAC token lifetime.
plan pe_mcp::deploy (
  TargetSpec $targets,
  TargetSpec $primary,
  String    $token_lifetime  = '7d',
) {
  $env_password = system::env('PE_ADMIN_PASSWORD')
  unless $env_password {
    fail_plan('PE_ADMIN_PASSWORD environment variable must be set')
  }
  $admin_password = Sensitive($env_password)

  $primary_target = get_targets($primary)[0]
  $pe_fqdn = $primary_target.host
  $deploy_targets = get_targets($targets)

  # Step 1: Check existing RBAC token, generate only if needed
  out::message("Step 1: Checking RBAC token on ${deploy_targets[0].name}")
  $check_result = run_task('pe_mcp::check_rbac_token', $deploy_targets[0],
    pe_primary => $pe_fqdn,
  )
  $token_status = $check_result.first.value['status']

  if $token_status == 'valid' {
    out::message('Existing RBAC token is still valid — skipping generation')
    $rbac_token = Sensitive($check_result.first.value['token'])
  } else {
    out::message("Token status: ${token_status} — generating new RBAC token on ${pe_fqdn}")
    $token_result = run_task('pe_mcp::generate_rbac_token', $primary_target,
      admin_password => $admin_password.unwrap,
      lifetime       => $token_lifetime,
    )
    $rbac_token = Sensitive($token_result.first.value['token'])
    out::message('RBAC token generated successfully')
  }

  # Step 2: Apply MCP server and nginx profiles
  out::message('Step 2: Applying MCP server and nginx profiles')
  apply_prep($deploy_targets)

  apply($deploy_targets) {
    class { 'pe_mcp::server':
      pe_fqdn    => $pe_fqdn,
      rbac_token => $rbac_token,
    }
    include pe_mcp::nginx
  }

  # Step 3: Verify MCP server is responding
  out::message('Step 3: Verifying MCP server')
  $verify_result = run_command(
    'curl -sk https://localhost/mcp -X POST \
      -H "Content-Type: application/json" \
      -H "Accept: application/json, text/event-stream" \
      --cacert /etc/puppetlabs/puppet/ssl/certs/ca.pem \
      -d \'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"0.1"}}}\' \
      -o /dev/null -w "%{http_code}"',
    $deploy_targets,
  )

  $deploy_targets.each |$target| {
    $http_code = $verify_result.find($target.name).value['stdout'].strip
    if $http_code == '200' {
      out::message("PASS: MCP server on ${target.name} returned HTTP 200")
    } else {
      fail_plan("FAIL: MCP server on ${target.name} returned HTTP ${http_code}")
    }
  }

  return('MCP deployment complete')
}
