# flashtool(A libusb base flash tool)

## Package Required

For branch nowrapper need install package libusb1

	sudo pip install libusb1

For branch standalone

	libusb wrapped already inside

## INTRO

[Reference : rkflashkit](https://github.com/linuxerwang/rkflashkit)

[USB Bulk Transfer](https://github.com/54shady/kernel_drivers_examples/tree/Firefly_RK3399/debug/usb)

- A high level utils for read or write flash(current support RockChip device)
- Derive from rkflashkit, more structured, more clear coded, make code easier to read
- A good example of python project(ctypes, libusb, etc)

## HOWTO

    Usage: <cmd> [args] [<cmd> [args]...]

    part                              List partition
    write @<PARTITION> <IMAGE FILE>   Write partition with image file
    cmp @<PARTITION> <IMAGE FILE>     Compare partition with image file
    read @<PARTITION> <IMAGE FILE>    Read partition to image file
    erase @<PARTITION>                Erase partition
    reboot                            Reboot device

    For example, flash device with boot.img and kernel.img, then reboot:

	python run.py write @boot boot.img @kernel.img kernel.img reboot
