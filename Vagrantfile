Vagrant.configure("2") do |config|
  config.vm.box = "debian/bookworm64"
  config.vbguest.auto_update = false if Vagrant.has_plugin?("vagrant-vbguest")

  # --- Proxy du reseau hote (VPN / entreprise) : reporte dans la VM -------
  http_proxy  = ENV["http_proxy"]  || ENV["HTTP_PROXY"]  || ""
  https_proxy = ENV["https_proxy"] || ENV["HTTPS_PROXY"] || http_proxy
  no_proxy    = [ENV["no_proxy"], ENV["NO_PROXY"]].compact.reject(&:empty?).join(",")
  no_proxy    = ([no_proxy, "127.0.0.1", "localhost"]).reject(&:empty?).join(",")

  config.vm.provider "virtualbox" do |vb|
    vb.name = "sandbox_forensics"
    vb.memory = "4096"
    vb.cpus = 4
    vb.gui = false

    vb.customize ["modifyvm", :id, "--usbxhci", "on"]
    vb.customize ["modifyvm", :id, "--ioapic", "on"]
    vb.customize ["modifyvm", :id, "--clipboard-mode", "bidirectional"]
    vb.customize ["modifyvm", :id, "--draganddrop", "bidirectional"]
    # Resolution DNS via le resolveur de l'hote (fix "Temporary failure resolving")
    vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
    vb.customize ["modifyvm", :id, "--natdnsproxy1", "on"]

    vb.customize ["usbfilter", "add", "0", "--target", :id, "--name", "Apple", "--vendorid", "05ac"]
    vb.customize ["usbfilter", "add", "1", "--target", :id, "--name", "Google_Generic", "--vendorid", "18d1"]
    vb.customize ["usbfilter", "add", "2", "--target", :id, "--name", "Samsung", "--vendorid", "04e8"]
    vb.customize ["usbfilter", "add", "3", "--target", :id, "--name", "Xiaomi", "--vendorid", "2717"]
    vb.customize ["usbfilter", "add", "4", "--target", :id, "--name", "Huawei_Honor", "--vendorid", "12d1"]
    vb.customize ["usbfilter", "add", "5", "--target", :id, "--name", "Oppo_Vivo", "--vendorid", "22d9"]
    vb.customize ["usbfilter", "add", "6", "--target", :id, "--name", "OnePlus", "--vendorid", "2a70"]
    vb.customize ["usbfilter", "add", "7", "--target", :id, "--name", "Motorola", "--vendorid", "22b8"]
    vb.customize ["usbfilter", "add", "8", "--target", :id, "--name", "Sony", "--vendorid", "0fce"]
    vb.customize ["usbfilter", "add", "9", "--target", :id, "--name", "LG", "--vendorid", "1004"]
    vb.customize ["usbfilter", "add", "10", "--target", :id, "--name", "HTC", "--vendorid", "0bb4"]
    vb.customize ["usbfilter", "add", "11", "--target", :id, "--name", "Asus", "--vendorid", "0b05"]
    vb.customize ["usbfilter", "add", "12", "--target", :id, "--name", "ZTE", "--vendorid", "19d2"]
    vb.customize ["usbfilter", "add", "13", "--target", :id, "--name", "Lenovo", "--vendorid", "17ef"]
    vb.customize ["usbfilter", "add", "14", "--target", :id, "--name", "Nokia", "--vendorid", "2e04"]
  end

  config.vm.synced_folder ".", "/vagrant"

  # --- Etape 1 : reseau (DNS + proxy) AVANT toute installation apt ----------
  config.vm.provision "network", type: "shell", env: {
    "HTTP_PROXY"  => http_proxy,
    "HTTPS_PROXY" => https_proxy,
    "NO_PROXY"    => no_proxy,
  }, inline: <<-SHELL
    set -e
    echo "[*] Configuration reseau de la VM..."
    rm -f /etc/resolv.conf
    printf '%s\n' 'nameserver 10.0.2.3' 'nameserver 8.8.8.8' 'nameserver 1.1.1.1' > /etc/resolv.conf
    if [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ]; then
      echo "[*] Proxy detecte sur l'hote : configuration d'apt..."
      cat > /etc/apt/apt.conf.d/01proxy <<EOF
Acquire::http::Proxy "${HTTP_PROXY}";
Acquire::https::Proxy "${HTTPS_PROXY}";
EOF
    fi
  SHELL

  # --- Etape 2 : deploiement --------------------------------------------------
  config.vm.provision "shell", env: {
    "HTTP_PROXY"  => http_proxy,
    "HTTPS_PROXY" => https_proxy,
    "NO_PROXY"    => no_proxy,
  }, inline: <<-SHELL
    echo "[*] Deploiement de la VM en cours..."
    cd /vagrant
    chmod +x scripts/launch.sh
    ./scripts/launch.sh cli
    echo "[+] Sandbox prete !"
  SHELL
end