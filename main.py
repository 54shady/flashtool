#!/usr/bin/env python
# coding=utf-8

"""
Usage: <cmd> [args] [<cmd> [args]...]

part                              List partition
flash @<PARTITION> <IMAGE FILE>   Flash partition with image file
cmp @<PARTITION> <IMAGE FILE>     Compare partition with image file
backup @<PARTITION> <IMAGE FILE>  Backup partition to image file
erase  @<PARTITION>               Erase partition
reboot                            Reboot device

For example, flash device with boot.img and kernel.img, then reboot:

sudo rkflashkit flash @boot boot.img @kernel.img kernel.img reboot
"""

import time
from vendor.rkusb import list_rk_devices, RkOperation


def get_devices():
    devices = []
    device_uids, device_list = list_rk_devices()
    for bus_id, dev_id, vendor_id, prod_id in device_list:
        dev_name = '0x%04x:0x%04x' % (vendor_id, prod_id)
        devices.append((dev_name, (bus_id, dev_id, vendor_id, prod_id)))
    return devices


def wait_for_one_device():
    while True:
        devices = get_devices()
        if not devices:
            print "No device found, retry..."
            time.sleep(1)
        else:
            print "Found devices"
            for device in devices:
                print device[0]
            if len(devices) > 1:
                print "More than one device found"
            break
    return devices[0]


class CliMain(object):
    '''
    command line mode
    '''

    def __init__(self):
        self.bus_id = 0
        self.dev_id = 0

    def main(self, args):
        if args[0] in ("help", "-h", "--help"):
            self.__usage()
            return 0

        dev = wait_for_one_device()
        self.bus_id = dev[1][0]
        self.dev_id = dev[1][1]
        self.parse_and_execute(args)

    def parse_and_execute(self, args):
        while args:
            if args[0] == "part":
                self.load_partitions()
                args = args[1:]
            else:
                self.usage()
                raise RuntimeError("Unknown command: %s", args[0])

    def get_operation(self):
        with self.get_rkoperation() as op:
            return op

    def load_partitions(self):
        partitions = {}
        op = self.get_operation()
        loaded_partitions = op.rk_load_partitions()
        for size, offset, name in loaded_partitions:
            partitions[name] = (offset, size)
        self.__partitions = partitions
        print self.__partitions

    def get_rkoperation(self):
        assert self.bus_id and self.dev_id
        return RkOperation(self.bus_id, self.dev_id)

    def __usage(self):
        print __doc__
