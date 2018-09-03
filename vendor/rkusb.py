#!/usr/bin/env python

# coding=utf-8

import re
import protocol
import time

PART_BLOCKSIZE = 0x800  # must be multiple of 512
PART_OFF_INCR = PART_BLOCKSIZE >> 9
RKFT_BLOCKSIZE = 0x4000  # must be multiple of 512
RKFT_OFF_INCR = RKFT_BLOCKSIZE >> 9
RKFT_DISPLAY = 0x1000
PARTITION_PATTERN = re.compile(r'(-|0x[0-9a-fA-F]+)@(0x[0-9a-fA-F]+)\((.*?)\)')

RK_VENDOR_ID = 0x2207
RK_PRODUCT_IDS = set([
    0x290a,  # RK2906
    0x292a,  # RK2928
    0x292c,  # RK3026/RK3028
    0x281a,
    0x300a,  # RK3066
    0x0010,  # RK3168 ???
    0x300b,  # RK3168 ???
    0x310b,  # RK3188
    0x310c,  # RK3128
    0x320a,  # RK3288
    0x320b,  # RK3229
    0x330c,  # RK3399
])

# (read endpoint, write endpoint)
RK_DEVICE_ENDPOINTS = {
    0x290a: (0x01, 0x02),  # RK2906
    0x292a: (0x01, 0x02),  # RK2928
    0x292c: (0x01, 0x02),  # RK3026/RK3028
    0x281a: (0x01, 0x02),
    0x300a: (0x01, 0x02),  # RK3066
    0x0010: (0x01, 0x02),  # RK3168 ???
    0x300b: (0x01, 0x02),  # RK3168 ???
    0x310b: (0x01, 0x02),  # RK3188
    0x310c: (0x01, 0x02),  # RK3128
    0x320a: (0x01, 0x02),  # RK3288
    0x320b: (0x01, 0x02),  # RK3229
    0x330c: (0x81, 0x01),  # RK3399
}


def is_rk_device(device):
    return (device.getVendorID() == RK_VENDOR_ID and
            device.getProductID() in RK_PRODUCT_IDS)


def list_devices():
    device_uids = set([])
    device_list = []

    context = None
    try:
        context = protocol.USBContext()
        context.setDebug(3)
        devices = context.getDeviceList()
        for device in devices:
            if is_rk_device(device):
                dev_uid = '%d:%d' % (device.getBusNumber(),
                                     device.getDeviceAddress())
                device_uids.add(dev_uid)
                device_list.append(
                    (device.getBusNumber(),
                     device.getDeviceAddress(),
                     device.getVendorID(),
                     device.getProductID()))
    finally:
        if context:
            del context

    return (device_uids, device_list)


def next_cmd_id():
    global global_cmd_id
    global_cmd_id = (global_cmd_id + 1) & 0xFF
    return chr(global_cmd_id)


RKFT_CID = 4
RKFT_FLAG = 12
RKFT_COMMAND = 13
RKFT_OFFSET = 17
RKFT_SIZE = 23
USB_CMD = [chr(0)] * 31
USB_CMD[0:4] = 'USBC'
global_cmd_id = -1


def prepare_cmd(flag, command, offset, size):
    USB_CMD[RKFT_CID] = next_cmd_id()
    USB_CMD[RKFT_FLAG] = chr(flag)
    USB_CMD[RKFT_SIZE] = chr(size)
    USB_CMD[RKFT_COMMAND] = chr((command >> 24) & 0xFF)
    USB_CMD[RKFT_COMMAND + 1] = chr((command >> 16) & 0xFF)
    USB_CMD[RKFT_COMMAND + 2] = chr((command >> 8) & 0xFF)
    USB_CMD[RKFT_COMMAND + 3] = chr((command) & 0xFF)
    USB_CMD[RKFT_OFFSET] = chr((offset >> 24) & 0xFF)
    USB_CMD[RKFT_OFFSET + 1] = chr((offset >> 16) & 0xFF)
    USB_CMD[RKFT_OFFSET + 2] = chr((offset >> 8) & 0xFF)
    USB_CMD[RKFT_OFFSET + 3] = chr((offset) & 0xFF)
    return USB_CMD


class RkOperation(object):
    def __init__(self, bus_id, dev_id):
        # get a usb context, which is a session
        self.__context = protocol.USBContext()
        self.__context.setDebug(3)

        # get the devices
        devices = self.__context.getDeviceList()

        # find out the rkdevice
        for device in devices:
            if (is_rk_device(device)
                and device.getBusNumber() == bus_id and
                    device.getDeviceAddress() == dev_id):
                # get device's info
                product_id = device.getProductID()
                # endpoint for read
                self.EP_IN = RK_DEVICE_ENDPOINTS[product_id][0]
                # endpoint for write
                self.EP_OUT = RK_DEVICE_ENDPOINTS[product_id][1]
                # open device, get a device handle
                self.__dev_handle = device.open()

        if not self.__dev_handle:
            raise Exception('Failed to open device.')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        del self  # self = None

    def rk_device_init(self):
        # Init
        self.__dev_handle.bulkWrite(self.EP_OUT,
                                    ''.join(prepare_cmd(0x80, 0x00060000, 0x00000000, 0x00000000)))
        self.__dev_handle.bulkRead(self.EP_IN, 13)

    def __init_device(self):
        if self.__dev_handle.kernelDriverActive(0):
            self.__dev_handle.detachKernelDriver(0)
        self.__dev_handle.claimInterface(0)

        self.rk_device_init()

        # sleep for 20ms
        time.sleep(0.02)

    def rk_load_partitions(self):
        partitions = []
        self.__init_device()

        self.__dev_handle.bulkWrite(self.EP_OUT,
                                    ''.join(prepare_cmd(0x80, 0x00061a00, 0x00000000, 0x00000000)))

        content = self.__dev_handle.bulkRead(self.EP_IN, 512)
        self.__dev_handle.bulkRead(self.EP_IN, 13)
        flash_size = (ord(content[0])) | (ord(content[1]) << 8) | (
            ord(content[2]) << 16) | (ord(content[3]) << 24)

        self.__dev_handle.bulkWrite(self.EP_OUT,
                                    ''.join(prepare_cmd(0x80, 0x000a1400, 0x00000000, PART_OFF_INCR)))

        content = self.__dev_handle.bulkRead(self.EP_IN, PART_BLOCKSIZE)
        self.__dev_handle.bulkRead(self.EP_IN, 13)

        for line in content.split('\n'):
            if line.startswith('CMDLINE:'):
                # return a list of tuple (size, unused, offset, part_name)
                for size, offset, name in re.findall(PARTITION_PATTERN, line):
                    offset = int(offset, 16)
                    if size == '-':
                        size = flash_size - offset
                    else:
                        size = int(size, 16)
                    partitions.append((size, offset, name))
                break

        return partitions
