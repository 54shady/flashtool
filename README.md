# flashtool(A libusb base flash tool)

HOWTO

    Usage: <cmd> [args] [<cmd> [args]...]

    part                              List partition
    write @<PARTITION> <IMAGE FILE>   Write partition with image file
    cmp @<PARTITION> <IMAGE FILE>     Compare partition with image file
    read @<PARTITION> <IMAGE FILE>    Read partition to image file
    erase @<PARTITION>                Erase partition
    reboot                            Reboot device

    For example, flash device with boot.img and kernel.img, then reboot:

    python run.py write @boot boot.img @kernel.img kernel.img reboot
