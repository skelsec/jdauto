

mkdir /opt/jdauto
mkdir /opt/mpservice
mkdir -p /opt/shared/jackdaw
mkdir -p /opt/shared/agent
mkdir -p /opt/shared/uploads

apt install samba samba-common-bin smbclient cifs-utils
adduser --system shareuser

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