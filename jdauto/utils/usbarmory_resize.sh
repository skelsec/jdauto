
This will only work during initial setup
To resize usbarmory:
1. download image
2. dd image to sdcard dd if=usbarmory-mark-two-debian_buster-base_image-20200408.raw of=/dev/sda conv=fsync bs=4M
3. sync
4. load gparted, resize sdcard

