#!/usr/bin/env python
# coding=utf-8

"""
Usage: <cmd> [args] [<cmd> [args]...]

part                              List partition
write @<PARTITION> <IMAGE FILE>   Write partition with image file
cmp @<PARTITION> <IMAGE FILE>     Compare partition with image file
read @<PARTITION> <IMAGE FILE>    Read partition to image file
erase @<PARTITION>                Erase partition
reboot                            Reboot device

For example, flash device with boot.img and kernel.img, then reboot:

python run.py write @boot boot.img @kernel.img kernel.img reboot
"""

from datetime import datetime
import time
from vendor.rkusb import list_rk_devices, RkOperation
import re
import sys

# a little bit like enum in C language
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)


def get_color(fg=None, bg=None, bright=False, bold=False, dim=False, reset=False):
    # manually derived from http://en.wikipedia.org/wiki/ANSI_escape_code#Codes
    codes = []
    if reset:
        codes.append("0")
    else:
        if not fg is None:
            codes.append("3%d" % (fg))
        if not bg is None:
            if not bright:
                codes.append("4%d" % (bg))
            else:
                codes.append("10%d" % (bg))
        if bold:
            codes.append("1")
        elif dim:
            codes.append("2")
        else:
            codes.append("22")
    return "\033[%sm" % (";".join(codes))


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


class FlashToolLogger(object):
    def __init__(self, use_color=False):
        self.WARN_COLOR = self.SUCC_COLOR = self.RESET_COLOR = ""
        if use_color:
            self.WARN_COLOR = get_color(fg=RED)
            self.SUCC_COLOR = get_color(fg=GREEN)
            self.RESET_COLOR = get_color(reset=True)

    def ftlog_print(self, message):
        sys.stdout.write(message)

    def ftlog_dividor(self):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.ftlog_print('\n%s============= %s ============%s\n\n' % (
            self.WARN_COLOR, current_time, self.RESET_COLOR))

    def ftlog_nice(self, message):
        self.ftlog_print('%s%s%s\n' %
                         (self.SUCC_COLOR, message, self.RESET_COLOR))

    def ftlog_error(self, message):
        self.ftlog_print('%sERROR:%s %s' %
                         (self.WARN_COLOR, message, self.RESET_COLOR))


class FlashTool(object):
    '''
    command line mode
    '''
    PARTITION_PATTERN = re.compile(r'(0x[0-9a-fA-F]+)@(0x[0-9a-fA-F]+)')

    def __init__(self):
        self.logger = FlashToolLogger(use_color=True)
        self.bus_id = 0
        self.dev_id = 0
        self.partitions = {}

    def main(self, args):
        if args[0] in ("help", "-h", "--help"):
            self.usage()
            return 0

        dev = wait_for_one_device()
        self.bus_id = dev[1][0]
        self.dev_id = dev[1][1]
        self.parse_and_execute(args)

    def parse_and_execute(self, args):
        while args:
            if args[0] == "part":
                self.load_partitions()
                # support multiple command in one line
                args = args[1:]
            elif args[0] == "write":
                args = args[1:]
                while len(args) >= 2 \
                    and (args[0].startswith("@")
                         or args[0].startswith("0x")):
                    self.flash_image(args[0], args[1])
                    # support multiple command in one line
                    args = args[2:]
            elif args[0] == "cmp":
                self.compare_imagefile(args[1], args[2])
                # support multiple command in one line
                args = args[3:]
            elif args[0] == "read":
                self.backup_partition(args[1], args[2])
                # support multiple command in one line
                args = args[3:]
            elif args[0] == "erase":
                self.erase_partition(args[1])
                args = args[2:]
            elif args[0] == "reboot":
                self.reboot_device()
                break
            else:
                self.usage()
                break

    def erase_partition(self, part_name):
        offset, size = self.get_partition(part_name)
        with self.get_operation() as op:
            op.rk_erase_partition(offset, size)

    def backup_partition(self, part_name, image_file):
        with self.get_operation() as op:
            if part_name == '@parameter':
                op.rk_backup_parameter(image_file)
            else:
                offset, size = self.get_partition(part_name)
                op.rk_backup_partition(offset, size, image_file)

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
                op.write_partition(offset, size, image_file)

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
            try:
                return self.partitions[part_name]  # (offset, size)
            except KeyError:
                print 'ERROR : %s is not in partition table' % part_name
                sys.exit(-1)

    def get_operation(self):
        with self.get_rkoperation() as op:
            return op

    def print_partitions(self):
        self.logger.ftlog_dividor()
        print "Partition table format(name : offset@size)"
        for k in self.partitions:
            print '%s : %d@%d' % (
                k, self.partitions[k][0], self.partitions[k][1])
        self.logger.ftlog_dividor()

    def load_partitions(self):
        partitions = {}
        op = self.get_operation()
        loaded_partitions = op.rk_load_partitions()
        for size, offset, name in loaded_partitions:
            partitions[name] = (offset, size)
        self.partitions = partitions
        #print self.partitions
        self.print_partitions()

    def get_rkoperation(self):
        assert self.bus_id and self.dev_id
        return RkOperation(self.logger, self.bus_id, self.dev_id)

    def usage(self):
        print __doc__
