class Xrayvpn < Formula
  desc "Provision and manage a self-hosted Xray VLESS + REALITY VPN server"
  homepage "https://github.com/lifestreamy/xrayvpn"
  url "{{ReleaseBaseUrl}}/xrayvpn-{{Version}}-macos-arm64-portable"
  sha256 "{{Sha256MacosArm64}}"
  license "AGPL-3.0-or-later"

  depends_on arch: :arm64

  def install
    bin.install "xrayvpn-{{Version}}-macos-arm64-portable" => "xrayvpn"
  end

  test do
    assert_match "xrayvpn", shell_output("#{bin}/xrayvpn --version")
  end
end
