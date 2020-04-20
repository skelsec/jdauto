
#ens33 -> internet interface
#ens160u2 -> usbarmory interface
#10.0.0.1/32 -> usbarmory IP

sudo iptables -A FORWARD -o ens33 -i ens160u2 -s 10.0.0.1/32 -m conntrack --ctstate NEW -j ACCEPT
sudo iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
sudo iptables -t nat -F POSTROUTING
sudo iptables -t nat -A POSTROUTING -o ens33 -j MASQUERADE

sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"