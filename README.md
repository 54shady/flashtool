# flashtool(A libusb base flash tool)

## Install and Uninstall

### Install from tarball

	python setup.py sdist
	sudo pip install dist/flashtool-1.0.0.tar.gz

	without super user permission:
	pip install --user dist/flashtool-1.0.0.tar.gz

Maybe export local path is necessary(Gentoo)

	export PATH=$PATH:~/.local/bin

Add your user name to the usb group(Gentoo)

	sudo usermod -aG usb your_user_name

### Install from source

	sudo pip install -e .

### Uninstall

	sudo -H pip uninstall flashtool

## INTRO

[Reference : rkflashkit](https://github.com/linuxerwang/rkflashkit)

[USB Bulk Transfer](https://github.com/54shady/kernel_drivers_examples/tree/Firefly_RK3399/debug/usb)

- A high level utils for read or write flash(current support RockChip device)
- Derive from rkflashkit, more structured, more clear coded, make code easier to read
- A good example of python project(ctypes, libusb, etc)

## HOWTO

    Usage: <cmd> [args] [<cmd> [args]...]

    part                              List partition
	chk                               Check read/write operation
    write @<PARTITION> <IMAGE FILE>   Write partition with image file
    cmp @<PARTITION> <IMAGE FILE>     Compare partition with image file
    read @<PARTITION> <IMAGE FILE>    Read partition to image file
    erase @<PARTITION>                Erase partition
    reboot                            Reboot device

    For example, flash device with boot.img and kernel.img, then reboot:

	flashtool [chk] write @boot boot.img @kernel.img kernel.img reboot

	or use smart write, which will flash the image in the sw_img if image exist.

	flashtool [chk] sw [reboot]

## Attached

python应用程序目录结构一般如下

	flashtool
	.
	├── flashtool <--和最外层同名,setup.py和MANIFEST.in中将用到
	|				在rkusb.py中也用的是这个名字
	├── MANIFEST.in
	├── README.md
	└── setup.py

关于setup.py中entry_points字段

	console_scripts表示命令行工具

其中下面表达式内容

	flashtool = flashtool:main
	左边是最终生成可执行文件的名字,右边的flashtool是一级目录的名字(如上面标注)
