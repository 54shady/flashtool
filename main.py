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
import re


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
    PARTITION_PATTERN = re.compile(r'(0x[0-9a-fA-F]+)@(0x[0-9a-fA-F]+)')

    def __init__(self):
        self.bus_id = 0
        self.dev_id = 0
        self.partitions = {}

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
            elif args[0] == "flash":
                args = args[1:]
                while len(args) >= 2 \
                    and (args[0].startswith("@")
                         or args[0].startswith("0x")):
                    self.flash_image(args[0], args[1])
                    args = args[2:]
            elif args[0] == "cmp":
                self.compare_imagefile(args[1], args[2])
                args = args[3:]
            elif args[0] == "reboot":
                self.reboot_device()
                break
            else:
                self.usage()
                raise RuntimeError("Unknown command: %s", args[0])

    def compare_imagefile(self, part_name, image_file):
        offset, size = self.get_partition(part_name)
        with self.get_operation() as op:
            op.cmp_part_with_file(offset, size, image_file)

    def reboot_device(self):
        with self.get_operation() as op:
            op.rk_reboot()

    def flash_image(self, part_name, image_file):
        with self.get_operation() as op:
            if part_name == '@parameter':
                op.flash_rk_parameter(image_file)
            else:
                offset, size = self.get_partition(part_name)
                op.flash_image_file(offset, size, image_file)

    def get_partition(self, part_name):
        if part_name.startswith('0x'):
            # 0x????@0x???? : size@offset
            partitions = self.PARTITION_PATTERN.findall(part_name)
            if len(partitions) != 1:
                raise ValueError('Invalid partition %s' % part_name)
            #print partitions
            return (int(partitions[0][1], 16),
                    int(partitions[0][0], 16))
        else:
            if part_name[0] == '@':
                part_name = part_name[1:]
            if not self.partitions:
                self.load_partitions()
            return self.partitions[part_name]  # (offset, size)

    def get_operation(self):
        with self.get_rkoperation() as op:
            return op

    def load_partitions(self):
        partitions = {}
        op = self.get_operation()
        loaded_partitions = op.rk_load_partitions()
        for size, offset, name in loaded_partitions:
            partitions[name] = (offset, size)
        self.partitions = partitions
        #print self.partitions
        print '=' * 45
        print "Partition table format(name : offset@size)"
        for k in self.partitions:
            print '%s : %d@%d' % (
                k, self.partitions[k][0], self.partitions[k][1])
        print '=' * 45

    def get_rkoperation(self):
        assert self.bus_id and self.dev_id
        return RkOperation(self.bus_id, self.dev_id)

    def __usage(self):
        print __doc__
