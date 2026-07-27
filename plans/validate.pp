# @summary Validate PE MCP deployment against acceptance criteria
#
# Runs the verification script suite on a deployed MCP node and
# returns a structured pass/fail report per acceptance criterion.
#
# Uploads scripts to /tmp/pe_mcp_verify/ on the target, runs each
# check, and collects exit codes into per-AC verdicts.
#
# AC mapping:
#   AC-01  Standalone server  — service status + MCP handshake
#   AC-02  Tool catalog       — tool registry + 5 tool calls
#   AC-03  FastMCP framework  — MCP handshake serverInfo
#   AC-04  Error envelopes    — error handling + envelope contract
#   AC-05  Config validation  — entrypoint exits 2 on bad config
#   AC-06  Structured logging — JSON-lines log file contract
#   AC-07  OTel observability — source code inspection (local only)
#   AC-08  Semgrep rules      — semgrep scan (local only)
#   AC-09  Audit logging      — audit event contract in log file
#   AC-10  BDD specs          — pytest-bdd (local only)
#   Proxy  nginx termination  — nginx status + HTTPS handshake
#
# @param targets MCP node(s) to validate.
plan pe_mcp::validate (
  TargetSpec $targets,
) {
  $deploy_targets = get_targets($targets)
  $verify_dir = '/tmp/pe_mcp_verify'

  # ------------------------------------------------------------------
  # Stage scripts on target
  # ------------------------------------------------------------------
  out::message('Uploading verification scripts to target...')

  run_command("mkdir -p ${verify_dir}", $deploy_targets)

  upload_file('pe_mcp/scripts/lib', "${verify_dir}/lib", $deploy_targets)
  upload_file('pe_mcp/scripts/01-verify-mcp-server', "${verify_dir}/01-verify-mcp-server", $deploy_targets)
  upload_file('pe_mcp/scripts/02-verify-proxy', "${verify_dir}/02-verify-proxy", $deploy_targets)
  upload_file('pe_mcp/scripts/07-verify-audit-logging', "${verify_dir}/07-verify-audit-logging", $deploy_targets)

  # Make scripts executable
  run_command("chmod -R +x ${verify_dir}", $deploy_targets)

  # ------------------------------------------------------------------
  # Helpers for running checks
  # ------------------------------------------------------------------
  $lib_path = "${verify_dir}/lib/mcp-session.sh"

  # ------------------------------------------------------------------
  # Phase 1: MCP Server (on node, localhost:8200)
  # ------------------------------------------------------------------
  out::message('')
  out::message('======= Phase 1: MCP Server =======')

  # AC-01: Standalone MCP server — service active, port 8200 listening
  $r_svc = run_command("bash ${verify_dir}/01-verify-mcp-server/01-check-service-status.sh",
    $deploy_targets, '_catch_errors' => true)
  $v_svc = $r_svc.ok ? { true => 'PASS', false => 'FAIL' }
  out::message("  ${v_svc}  AC-01: service-status")

  # AC-01 + AC-03: MCP handshake — proves server responds and FastMCP serverInfo
  $r_shake = run_command("bash ${verify_dir}/01-verify-mcp-server/02-mcp-initialize-handshake.sh",
    $deploy_targets, '_catch_errors' => true)
  $v_shake = $r_shake.ok ? { true => 'PASS', false => 'FAIL' }
  out::message("  ${v_shake}  AC-01/03: mcp-handshake")

  # AC-02: Tool registry — all 5 default tools registered
  $r_reg = run_command("cat ${lib_path} ${verify_dir}/01-verify-mcp-server/03-verify-tool-registry.sh | bash",
    $deploy_targets, '_catch_errors' => true)
  $v_reg = $r_reg.ok ? { true => 'PASS', false => 'FAIL' }
  out::message("  ${v_reg}  AC-02: tool-registry")

  # AC-02: Individual tool calls
  $tool_checks = [
    { 'name' => 'node-lookup',     'script' => '04-call-node-lookup.sh' },
    { 'name' => 'pql-query',       'script' => '05-call-pql-query.sh' },
    { 'name' => 'recent-reports',  'script' => '06-call-recent-reports.sh' },
    { 'name' => 'impact-scope',    'script' => '07-call-impact-scope.sh' },
    { 'name' => 'resource-events', 'script' => '08-call-resource-events.sh' },
  ]

  $tool_verdicts = $tool_checks.map |$tc| {
    $r = run_command(
      "cat ${lib_path} ${verify_dir}/01-verify-mcp-server/${tc['script']} | bash",
      $deploy_targets, '_catch_errors' => true)
    $v = $r.ok ? { true => 'PASS', false => 'FAIL' }
    out::message("  ${v}  AC-02: ${tc['name']}")
    $v
  }
  $tool_fail_count = $tool_verdicts.filter |$v| { $v == 'FAIL' }.length

  # AC-04: Error handling and envelopes
  $r_err = run_command(
    "cat ${lib_path} ${verify_dir}/01-verify-mcp-server/09-verify-error-handling.sh | bash",
    $deploy_targets, '_catch_errors' => true)
  $v_err = $r_err.ok ? { true => 'PASS', false => 'FAIL' }
  out::message("  ${v_err}  AC-04: error-handling")

  $r_env = run_command(
    "cat ${lib_path} ${verify_dir}/01-verify-mcp-server/12-check-error-envelopes.sh | bash",
    $deploy_targets, '_catch_errors' => true)
  $v_env = $r_env.ok ? { true => 'PASS', false => 'FAIL' }
  out::message("  ${v_env}  AC-04: error-envelopes")

  # AC-05: Config validation — entrypoint rejects bad config
  $r_cfg = run_command("bash ${verify_dir}/01-verify-mcp-server/11-check-config-validation.sh",
    $deploy_targets, '_catch_errors' => true)
  $v_cfg = $r_cfg.ok ? { true => 'PASS', false => 'FAIL' }
  out::message("  ${v_cfg}  AC-05: config-validation")

  # AC-06: Structured logging — JSON-lines in log file
  $r_log = run_command("bash ${verify_dir}/01-verify-mcp-server/10-check-structured-logging.sh",
    $deploy_targets, '_catch_errors' => true)
  $v_log = $r_log.ok ? { true => 'PASS', false => 'FAIL' }
  out::message("  ${v_log}  AC-06: structured-logging")

  # ------------------------------------------------------------------
  # Phase 2: Proxy Layer (nginx SSL termination)
  # ------------------------------------------------------------------
  out::message('')
  out::message('======= Phase 2: Proxy Layer =======')

  $r_ngx = run_command("bash ${verify_dir}/02-verify-proxy/01-check-proxy-status.sh",
    $deploy_targets, '_catch_errors' => true)
  $v_ngx = $r_ngx.ok ? { true => 'PASS', false => 'FAIL' }
  out::message("  ${v_ngx}  Proxy: nginx-status")

  $r_https = run_command("bash ${verify_dir}/02-verify-proxy/02-mcp-via-https.sh",
    $deploy_targets, '_catch_errors' => true)
  $v_https = $r_https.ok ? { true => 'PASS', false => 'FAIL' }
  out::message("  ${v_https}  Proxy: mcp-via-https")

  # ------------------------------------------------------------------
  # Phase 3: Audit Logging (AC-09)
  # ------------------------------------------------------------------
  out::message('')
  out::message('======= Phase 3: Audit Logging =======')

  $r_audit = run_command("bash ${verify_dir}/07-verify-audit-logging/01-check-audit-events.sh",
    $deploy_targets, '_catch_errors' => true)
  $v_audit = $r_audit.ok ? { true => 'PASS', false => 'FAIL' }
  out::message("  ${v_audit}  AC-09: audit-events")

  # ------------------------------------------------------------------
  # Cleanup
  # ------------------------------------------------------------------
  run_command("rm -rf ${verify_dir}", $deploy_targets, '_catch_errors' => true)

  # ------------------------------------------------------------------
  # Build structured report
  # ------------------------------------------------------------------
  $ac01 = ($v_svc == 'PASS' and $v_shake == 'PASS') ? { true => 'PASS', false => 'FAIL' }
  $ac02 = ($v_reg == 'PASS' and $tool_fail_count == 0) ? { true => 'PASS', false => 'FAIL' }
  $ac03 = $v_shake
  $ac04 = ($v_err == 'PASS' and $v_env == 'PASS') ? { true => 'PASS', false => 'FAIL' }
  $ac05 = $v_cfg
  $ac06 = $v_log
  $ac09 = $v_audit
  $proxy = ($v_ngx == 'PASS' and $v_https == 'PASS') ? { true => 'PASS', false => 'FAIL' }

  $report = [
    { 'ac' => 'AC-01', 'label' => 'Standalone MCP server',     'verdict' => $ac01 },
    { 'ac' => 'AC-02', 'label' => 'Tool catalog (5 defaults)',  'verdict' => $ac02 },
    { 'ac' => 'AC-03', 'label' => 'FastMCP framework',          'verdict' => $ac03 },
    { 'ac' => 'AC-04', 'label' => 'Error envelopes',            'verdict' => $ac04 },
    { 'ac' => 'AC-05', 'label' => 'Config validation',          'verdict' => $ac05 },
    { 'ac' => 'AC-06', 'label' => 'Structured logging',         'verdict' => $ac06 },
    { 'ac' => 'AC-07', 'label' => 'OTel observability',         'verdict' => 'SKIP: run locally with scripts/06-verify-otel/01-check-otel-config.sh' },
    { 'ac' => 'AC-08', 'label' => 'Semgrep rules',              'verdict' => 'SKIP: run locally with semgrep scan --config semgrep/' },
    { 'ac' => 'AC-09', 'label' => 'Audit logging',              'verdict' => $ac09 },
    { 'ac' => 'AC-10', 'label' => 'BDD feature specs',          'verdict' => 'SKIP: run locally with pytest tests/features/' },
    { 'ac' => 'Proxy', 'label' => 'nginx SSL termination',      'verdict' => $proxy },
  ]

  $pass_count = $report.filter |$r| { $r['verdict'] == 'PASS' }.length
  $fail_count = $report.filter |$r| { $r['verdict'] == 'FAIL' }.length
  $skip_count = $report.filter |$r| { $r['verdict'] =~ /SKIP/ }.length

  out::message('')
  out::message('==================== VALIDATION REPORT ====================')
  $report.each |$r| {
    $pad_width = 7 - length($r['ac'])
    $pad = sprintf("%${pad_width}s", '')
    out::message("  [${r['verdict']}]${pad} ${r['ac']}: ${r['label']}")
  }
  out::message('===========================================================')
  out::message("${pass_count} passed, ${fail_count} failed, ${skip_count} skipped")

  if $fail_count > 0 {
    fail_plan("Validation failed: ${fail_count} acceptance criteria did not pass")
  }

  return($report)
}
