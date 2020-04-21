


sudo fallocate -l 10G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# to make it permanent:
# sudo nano /etc/fstab
# add this line at the bottom: /swapfile swap swap defaults 0 0