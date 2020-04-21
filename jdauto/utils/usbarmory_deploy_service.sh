
mkdir /opt/jdauto
mkdir /opt/mpservice


nano /opt/mpservice/mpservice.sh
#!/bin/bash
/usr/local/bin/multiplexor

nano /opt/jdauto/jdautoservice.sh
#!/bin/bash
/usr/local/bin/jdauto sqlite:////opt/jdauto/test.db ws://127.0.0.1:9999


nano /etc/systemd/system/multiplexor.service 
[Unit]
Description=multiplexor service
After=multi-user.target

[Service]
Type=simple
Restart=yes
ExecStart=/opt/mpservice/mpservice.sh

[Install]
WantedBy=multi-user.target


nano /etc/systemd/system/jdauto.service      
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


# initializing database
jackdaw --sql sqlite:////opt/jdauto/test.db dbinit

systemctl enable jdauto
systemctl enable multiplexor

systemctl start jdauto
systemctl start multiplexor


