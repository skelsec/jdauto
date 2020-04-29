
echo "Installing necessary tools"
apt install -y samba samba-common-bin smbclient cifs-utils python3-pip python3.7-dev python3.7-venv git htop lsof tmux iotop

echo "Installing pip packages"
python3.7 -m pip install multiplexor jdauto
python3.7 -m pip uninstall asn1crypto
python3.7 -m pip install 'asn1crypto>=1.3.0'

echo "Creating directory strucutre"
mkdir /opt/jdauto
mkdir /opt/mpservice
mkdir -p /opt/shared/jackdaw
mkdir -p /opt/shared/agent
mkdir -p /opt/shared/uploads


echo "Creating share user"
adduser --system shareuser
chown -R shareuser /opt/shared/uploads/

echo "Setting up service scripts"
cat <<EOF > /opt/mpservice/mpservice.sh
#!/bin/bash
/usr/local/bin/multiplexor
EOF

cat <<EOF > /opt/jdauto/jdautoservice.sh
#!/bin/bash
/usr/local/bin/jdauto /opt/shared/jackdaw -o /opt/shared/jackdaw/progress.txt
EOF

chmod +x /opt/mpservice/mpservice.sh
chmod +x /opt/jdauto/jdautoservice.sh

echo "Creating service entries"
cat <<EOF > /etc/systemd/system/multiplexor.service 
[Unit]
Description=multiplexor service
After=multi-user.target

[Service]
Type=simple
Restart=yes
ExecStart=/opt/mpservice/mpservice.sh

[Install]
WantedBy=multi-user.target
EOF

cat <<EOF > /etc/systemd/system/jdauto.service      
[Unit]
Description=jackdaw auto collection service
After=multi-user.target

[Service]
Type=simple
Restart=true
ExecStart=/opt/jdauto/jdautoservice.sh
StandardOutput=append:/opt/jdauto/stdout.log
StandardError=append:/opt/jdauto/stderr.log

[Install]
WantedBy=multi-user.target
EOF

echo "Adding SMB shares"
cat <<EOF >>  /etc/samba/smb.conf

[jackdaw]
path = /opt/shared/jackdaw
writeable = no
browseable = yes
public = yes
create mask = 0755
directory mask = 0755
force user = root
guest ok = yes

[agent]
path = /opt/shared/agent
writeable = no
browseable = yes
public = yes
create mask = 0755
directory mask = 0755
force user = root
guest ok = yes

[uploads]
path = /opt/shared/uploads
writeable = yes
browseable = yes
public = yes
create mask = 0333
directory mask = 0755
force user = shareuser
EOF

echo "Creating starting services"
systemctl enable multiplexor
systemctl start multiplexor

systemctl enable jdauto
systemctl start jdauto
systemctl restart smbd