require 'spec_helper'

describe 'pe_mcp::server' do
  let(:facts) { { os: { family: 'Debian' }, pe_server_fqdn: 'pe-primary.example.com' } }
  let(:params) { { 'rbac_token' => sensitive('test-token') } }

  it { is_expected.to compile.with_all_deps }
end
