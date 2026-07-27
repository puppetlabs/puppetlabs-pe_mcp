# @summary Nginx reverse proxy for the PE MCP server
#
# Installs nginx and configures SSL termination using PE agent
# certificates, proxying HTTPS :443 /mcp to the local smart MCP
# server on :8200.
#
# @param mcp_port
#   Port the backend MCP server listens on.
#
# @example
#   include pe_mcp::nginx
class pe_mcp::nginx (
  Integer $mcp_port = 8200,
) {
  $certname = $facts['clientcert']
  $ssl_cert = "/etc/puppetlabs/puppet/ssl/certs/${certname}.pem"
  $ssl_key  = "/etc/puppetlabs/puppet/ssl/private_keys/${certname}.pem"
  $ssl_ca   = '/etc/puppetlabs/puppet/ssl/certs/ca.pem'

  package { 'nginx':
    ensure => installed,
  }

  file { '/etc/nginx/sites-available/smart-mcp':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => epp('pe_mcp/nginx-smart-mcp.conf.epp', {
        'ssl_cert' => $ssl_cert,
        'ssl_key'  => $ssl_key,
        'ssl_ca'   => $ssl_ca,
        'mcp_port' => $mcp_port,
    }),
    require => Package['nginx'],
    notify  => Service['nginx'],
  }

  file { '/etc/nginx/sites-enabled/smart-mcp':
    ensure  => link,
    target  => '/etc/nginx/sites-available/smart-mcp',
    require => File['/etc/nginx/sites-available/smart-mcp'],
    notify  => Service['nginx'],
  }

  file { '/etc/nginx/sites-enabled/default':
    ensure  => absent,
    require => Package['nginx'],
    notify  => Service['nginx'],
  }

  service { 'nginx':
    ensure  => running,
    enable  => true,
    require => Package['nginx'],
  }
}
