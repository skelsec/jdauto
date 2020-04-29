#!/bin/bash

apt install -y isc-dhcp-server

echo "Modifying boot parameter in cmdline"
sed -i 's/rootwait/rootwait modules-load=dwc2,g_ether/g' /boot/cmdline.txt

echo "Modifying boot parameter in config"
cat <<EOF >> /boot/config.txt

dtoverlay=dwc2
EOF

echo "Adding static IP to usb0 interface in DHCPCD"
cat <<EOF >> /etc/dhcpcd.conf

interface usb0
static ip_address=10.0.0.1/24
static routers=10.0.0.2
static domain_name_servers=8.8.8.8 4.4.4.4
EOF

echo "Setting up dhcp server"
cat <<EOF >> /etc/dhcp/dhcpd.conf

subnet 10.0.0.0 netmask 255.255.255.0 {
 range 10.0.0.2 10.0.0.200;
}
EOF

cat <<EOF > /etc/default/isc-dhcp-server
INTERFACESv4="usb0"
EOF
