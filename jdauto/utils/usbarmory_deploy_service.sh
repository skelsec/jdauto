
mkdir /opt/jdauto
mkdir /opt/mpservice


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

systemctl enable multiplexor
systemctl start multiplexor

systemctl enable jdauto
systemctl start jdauto


