# flashtool(A libusb base flash tool)

## Branches

Branch setup is a standard python application package

Branch standalone(libusb wrapped already inside)

Branch nowrapper need install package libusb1

	sudo pip install libusb1

See details in each branch README.md

## Intro

[Reference : rkflashkit](https://github.com/linuxerwang/rkflashkit)

[USB Bulk Transfer](https://github.com/54shady/kernel_drivers_examples/tree/Firefly_RK3399/debug/usb)

- A high level utils for read or write flash(current support RockChip device)
- Derive from rkflashkit, more structured, more clear coded, make code easier to read
- A good example of python project(ctypes, libusb, etc)
