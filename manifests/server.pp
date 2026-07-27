# @summary Install and manage the PE MCP smart server
#
# Sets up a Python venv with FastMCP, deploys the pe_mcp package,
# drops an RBAC token, and manages the systemd service.
#
# @param pe_fqdn
#   FQDN of the PE primary server for PuppetDB queries.
# @param rbac_token
#   PE RBAC token for authenticating API calls.
# @param listen_port
#   Port the MCP server listens on (localhost only).
# @param install_dir
#   Base directory for the MCP server installation.
# @param otlp_endpoint
#   Optional OTLP HTTP endpoint for OpenTelemetry trace export.
#   When undef, telemetry initialises in no-op mode.
#
# @example
#   class { 'pe_mcp::server':
#     pe_fqdn    => 'pe-primary.example.com',
#     rbac_token => Sensitive('my-rbac-token'),
#   }
class pe_mcp::server (
  String           $pe_fqdn    = $facts['pe_server_fqdn'],
  Sensitive[String] $rbac_token = Sensitive('UNSET'),
  Integer           $listen_port = 8200,
  Stdlib::Absolutepath $install_dir = '/opt/smart-mcp',
  Optional[String]     $otlp_endpoint = undef,
) {
  $venv_dir    = "${install_dir}/venv"
  $package_dir = "${install_dir}/pe_mcp"
  $token_file  = "${install_dir}/rbac_token"
  $unit_name   = 'smart-mcp'

  if $facts['os']['family'] == 'Debian' {
    package { 'python3-venv':
      ensure => installed,
      before => Exec['create-smart-mcp-venv'],
    }
  }

  file { $install_dir:
    ensure => directory,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }

  exec { 'create-smart-mcp-venv':
    command => "/usr/bin/python3 -m venv ${venv_dir}",
    creates => "${venv_dir}/bin/python3",
    require => File[$install_dir],
  }

  exec { 'install-fastmcp':
    command => "${venv_dir}/bin/pip install fastmcp structlog pydantic-settings httpx opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http",
    unless  => "${venv_dir}/bin/python3 -c 'import fastmcp; import structlog; import pydantic_settings; import httpx; import opentelemetry'",
    require => Exec['create-smart-mcp-venv'],
  }

  file { $package_dir:
    ensure  => directory,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    recurse => true,
    purge   => true,
    source  => 'puppet:///modules/pe_mcp/pe_mcp',
    require => File[$install_dir],
    notify  => Service[$unit_name],
  }

  file { $token_file:
    ensure    => file,
    owner     => 'root',
    group     => 'root',
    mode      => '0600',
    content   => $rbac_token.unwrap,
    show_diff => false,
    require   => File[$install_dir],
    notify    => Service[$unit_name],
  }

  file { "/etc/systemd/system/${unit_name}.service":
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => epp('pe_mcp/smart-mcp.service.epp', {
        'venv_dir'      => $venv_dir,
        'install_dir'   => $install_dir,
        'pe_fqdn'       => $pe_fqdn,
        'otlp_endpoint' => $otlp_endpoint,
    }),
    notify  => [Exec['systemd-reload-smart-mcp'], Service[$unit_name]],
  }

  exec { 'systemd-reload-smart-mcp':
    command     => '/usr/bin/systemctl daemon-reload',
    refreshonly => true,
  }

  service { $unit_name:
    ensure  => running,
    enable  => true,
    require => [
      Exec['install-fastmcp'],
      File[$package_dir],
      File[$token_file],
      File["/etc/systemd/system/${unit_name}.service"],
      Exec['systemd-reload-smart-mcp'],
    ],
  }
}
