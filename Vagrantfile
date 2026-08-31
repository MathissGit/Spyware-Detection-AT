Vagrant.configure("2") do |config|
  config.vm.box = "debian/bookworm64"
  config.vbguest.auto_update = false if Vagrant.has_plugin?("vagrant-vbguest")
  
  config.vm.provider "virtualbox" do |vb|
    vb.name = "sandbox_forensics"
    vb.memory = "4096"
    vb.cpus = 4
    vb.gui = false

    vb.customize ["modifyvm", :id, "--usbxhci", "on"]
    vb.customize ["modifyvm", :id, "--ioapic", "on"]
    vb.customize ["modifyvm", :id, "--clipboard-mode", "bidirectional"]
    vb.customize ["modifyvm", :id, "--draganddrop", "bidirectional"]
    
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
  
  config.vm.provision "shell", inline: <<-SHELL
    echo "[*] Déploiement de la VM en cours..."
    cd /vagrant
    chmod +x sandbox_env.sh
    ./sandbox_env.sh
    echo "[+] Sandbox prête !"
  SHELL
end