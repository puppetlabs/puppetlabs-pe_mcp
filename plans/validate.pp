# @summary Verify a deployed PE MCP server is up and responding
#
# A single connectivity check: confirms the smart-mcp service is running,
# nginx is running, and the server responds correctly to an MCP
# initialize handshake over HTTPS. Self-contained — no scripts are
# uploaded to the target.
#
# This is intentionally lightweight. The full acceptance-criteria test
# suite (tool registry, error envelopes, structured/audit logging, etc.)
# is maintained separately in the private pe_mcp_control_repo development
# repo, not shipped as part of this module.
#
# @param targets MCP node(s) to validate.
plan pe_mcp::validate (
  TargetSpec $targets,
) {
  $deploy_targets = get_targets($targets)

  out::message('Checking smart-mcp service status...')
  $svc_result = run_command('systemctl is-active smart-mcp', $deploy_targets, '_catch_errors' => true)

  out::message('Checking nginx service status...')
  $nginx_result = run_command('systemctl is-active nginx', $deploy_targets, '_catch_errors' => true)

  out::message('Verifying MCP handshake over HTTPS...')
  $handshake_result = run_command(
    'curl -sk https://localhost/mcp -X POST \
      -H "Content-Type: application/json" \
      -H "Accept: application/json, text/event-stream" \
      --cacert /etc/puppetlabs/puppet/ssl/certs/ca.pem \
      -d \'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"validate","version":"0.1"}}}\' \
      -o /dev/null -w "%{http_code}"',
    $deploy_targets,
  )

  $failures = $deploy_targets.map |$target| {
    $svc_ok = $svc_result.find($target.name).ok
    $nginx_ok = $nginx_result.find($target.name).ok
    $http_code = $handshake_result.find($target.name).value['stdout'].strip
    $handshake_ok = $http_code == '200'

    if $svc_ok and $nginx_ok and $handshake_ok {
      out::message("PASS: ${target.name} — smart-mcp active, nginx active, MCP handshake HTTP ${http_code}")
      undef
    } else {
      out::message("FAIL: ${target.name} — smart-mcp active=${svc_ok}, nginx active=${nginx_ok}, handshake HTTP ${http_code}")
      $target.name
    }
  }.filter |$f| { $f =~ NotUndef }

  if !$failures.empty {
    fail_plan("Connectivity check failed on: ${failures.join(', ')}")
  }

  return('Connectivity check passed')
}
