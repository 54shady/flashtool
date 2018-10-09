#!/usr/bin/env python
# coding=utf-8

import io
import re
from usb1 import USBContext
import time
from flashtool.misc import rkcrc as RKCRC
import sys
import os


PARTITON_SECTOR_SIZE = 512  # 512 bytes
USB_BULK_READ_SIZE = 512
PART_BLOCKSIZE = 0x800  # must be multiple of 512
PART_OFF_INCR = PART_BLOCKSIZE >> 9
RKFT_BLOCKSIZE = 0x4000  # must be multiple of 512
RKFT_OFF_INCR = RKFT_BLOCKSIZE >> 9
RKFT_DISPLAY = 0x1000

# 0xAA@0xBB(name), -@0xBB(name)
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


def show_process(current, total, message=''):
    '''
    ugly process bar, but this is what I got right now
    '''
    sys.stdout.write('{0} : {1}/{2}\r'.format(message, total - current, total))
    sys.stdout.flush()


def is_rk_device(device):
    return (device.getVendorID() == RK_VENDOR_ID and
            device.getProductID() in RK_PRODUCT_IDS)


def findout_rk_device(device, device_uids, device_list):
    if is_rk_device(device):
        dev_uid = '%d:%d' % (device.getBusNumber(),
                             device.getDeviceAddress())
        device_uids.add(dev_uid)
        device_list.append(
            (device.getBusNumber(),
             device.getDeviceAddress(),
             device.getVendorID(),
             device.getProductID()))


def list_rk_devices():
    device_uids = set([])
    device_list = []

    context = None
    try:
        context = USBContext()
        context.setDebug(3)
        devices = context.getDeviceList()
        for device in devices:
            findout_rk_device(device, device_uids, device_list)
    finally:
        if context:
            del context

    return (device_uids, device_list)


# generate a unique id
def next_cmd_id():
    global global_cmd_id
    global_cmd_id = (global_cmd_id + 1) & 0xFF
    return chr(global_cmd_id)


'''
/* command block wrapper */
struct bulk_cb_wrap {
    __le32  Signature;      /* contains 'USBC' */
    __u32   Tag;            /* unique per command id */
    __le32  DataTransferLength; /* size of data */
    __u8    Flags;          /* direction in bit 0 */
    __u8    Lun;            /* LUN normally 0 */
    __u8    Length;         /* of of the CDB */
    __u8    CDB[16];        /* max command */
};

/* command status wrapper */
struct bulk_cs_wrap {
    __le32  Signature;  /* should = 'USBS' */
    __u32   Tag;        /* same as original command */
    __le32  Residue;    /* amount not transferred */
    __u8    Status;     /* see below */
};
'''
CBW_TAG = 4
CBW_FLAG = 12
CBW_LUN = 13
CBW_LENGTH = 14
CBW_CDB0 = 15
CBW_OFFSET = 17
BULK_CBW = [chr(0)] * 31  # bulk cbw is a list
BULK_CBW[0:4] = 'USBC'  # list can assgin like this, nor str type
global_cmd_id = -1
BULK_CS_WRAP_LEN = 13  # struct bulk_cs_wrap 13 bytes

# rkusb command
# command_name : (comand_id, direction)
rkusb_command = {
    "TEST_UNIT_READY": (0x0,  0x80),
    "READ_FLASH_ID": (0x01, 0x80),
    "TEST_BAD_BLOCK": (0x03, 0x80),
    "READ_SECTOR": (0x04, 0x80),
    "WRITE_SECTOR": (0x05, 0x00),
    "ERASE_NORMAL": (0x06, 0x00),
    "ERASE_FORCE": (0x0B, 0x00),
    "READ_LBA": (0x14, 0x80),
    "WRITE_LBA": (0x15, 0x00),
    "ERASE_SYSTEMDISK": (0x16, 0x00),
    "READ_SDRAM": (0x17, 0x80),
    "WRITE_SDRAM": (0x18, 0x00),
    "EXECUTE_SDRAM": (0x19, 0x00),
    "READ_FLASH_INFO": (0x1A, 0x80),
    "READ_CHIP_INFO": (0x1B, 0x80),
    "SET_RESET_FLAG": (0x1E, 0x00),
    "WRITE_EFUSE": (0x1F, 0x00),
    "READ_EFUSE": (0x20, 0x80),
    "READ_SPI_FLASH": (0x21, 0x80),
    "WRITE_SPI_FLASH": (0x22, 0x00),
    "WRITE_NEW_EFUSE": (0x23, 0x00),
    "READ_NEW_EFUSE": (0x24, 0x80),
    "ERASE_LBA": (0x25, 0x00),
    "READ_CAPABILITY": (0xAA, 0x80),
    "DEVICE_RESET": (0xFF, 0x00),
}

DIRECTION_OUT = 0x00
DIRECTION_IN = 0x80

'''
rkusb CDB(from rkdeveloptool)

BYTE	ucOperCode; ==> CDB[0]
BYTE	ucReserved; ==> CDB[1]
DWORD	dwAddress;  ==> CDB[2:5]
BYTE	ucReserved2; ==> CDB[6]
USHORT	usLength; ==> CDB[7:8]
BYTE	ucReserved3; CDB[9]
'''


def bulk_cb_wrap(cmd_name, offset=0, size=0):
    '''
    rkusb command block wrapper
    cmd_name : rkusb command name in string
    return a list
    '''
    # findout command direction
    flag = rkusb_command[cmd_name][1]
    # findout command id
    cmd_id = rkusb_command[cmd_name][0]

    BULK_CBW[CBW_TAG] = next_cmd_id()
    BULK_CBW[CBW_FLAG] = chr(flag)
    BULK_CBW[CBW_LUN] = chr(0)

    # len of cdb data
    BULK_CBW[CBW_LENGTH] = chr(0x8)

    # 6 bytes cdb
    BULK_CBW[CBW_CDB0] = chr(cmd_id)  # rkusb cmd
    BULK_CBW[CBW_CDB0 + 1] = chr(0)  # reserved
    BULK_CBW[CBW_OFFSET] = chr((offset >> 24) & 0xFF)
    BULK_CBW[CBW_OFFSET + 1] = chr((offset >> 16) & 0xFF)
    BULK_CBW[CBW_OFFSET + 2] = chr((offset >> 8) & 0xFF)
    BULK_CBW[CBW_OFFSET + 3] = chr((offset) & 0xFF)

    # the 8th byte of cdb
    BULK_CBW[CBW_CDB0 + 8] = chr(size)

    # BULK_CBW is a list type data
    # because the send_cbw need a string value
    # so need to covert the list to string
    # ''.join() make the list into a new sting
    return ''.join(BULK_CBW)


class RkOperation(object):
    def __init__(self, logger, bus_id, dev_id, chk_rw):
        self.__logger = logger
        # get a usb context, which is a session
        self.__context = USBContext()
        self.__context.setDebug(3)

        # check read/write operation
        self.__chk_rw = chk_rw

        # for image flash check, default True
        self.integrity = True

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

        # do some init for the device
        self.init_device()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        del self  # self = None

    def __rk_device_init(self):
        # Init
        self.send_cbw(bulk_cb_wrap("TEST_UNIT_READY"))
        self.recv_csw()

    def init_device(self):
        if self.__dev_handle.kernelDriverActive(0):
            self.__dev_handle.detachKernelDriver(0)
        self.__dev_handle.claimInterface(0)

        self.__rk_device_init()

        # sleep for 20ms
        time.sleep(0.02)

    def rk_load_partitions(self):
        '''
        define a list partition as list type
        return the partition in dict type
        '''
        partitions = []

        # read flash info
        self.send_cbw(bulk_cb_wrap("READ_FLASH_INFO"))
        content = self.send_or_recv_data(data_len=USB_BULK_READ_SIZE)
        self.recv_csw()

        flash_size = (ord(chr(content[0]))) | (ord(chr(content[1])) << 8) | (
            ord(chr(content[2])) << 16) | (ord(chr(content[3])) << 24)

        # read lba
        self.send_cbw(bulk_cb_wrap("READ_LBA", size=PART_OFF_INCR))
        content = self.send_or_recv_data(data_len=PART_BLOCKSIZE)
        self.recv_csw()

        # convert bytearray context into str
        ctx = str(content)
        for line in ctx.split('\n'):
            if line.startswith('CMDLINE:'):
                # return a list of tuple (size, unused, offset, part_name)
                for size, offset, name in re.findall(PARTITION_PATTERN, line):
                    offset = int(offset, 16)
                    if size == '-':
                        size = flash_size - offset
                    else:
                        size = int(size, 16)
                    # make a nesting list, so we can covert it into dict
                    # list[('key', (value1, value2)), ...]
                    partitions.append((name, (offset, size)))
                break

        return dict(partitions)

    def rk_read_partition(self, offset, size, file_name):
        self.__logger.ftlog_dividor()
        self.__logger.ftlog_print("Starting read %s(%d bytes)\n" % (file_name,
                                                                    size))

        # open the file for writing
        with open(file_name, 'w') as filename:
            self.rk_usb_read(offset, size, filename)

        if self.__chk_rw:
            # Verify backup.
            self.cmp_part_with_file(offset, size, file_name)

        self.__logger.ftlog_nice("Done")

    def dump_str2hex(self, string_value):
        return ' '.join(hex(x) for x in bytearray(string_value))

    def send_cbw(self, cbw):
        '''
        data direction from host to slave
        endpoint is EP_OUT

        In rkloader(u-boot)
        function do_rockusb_cmd
        usbcmd.cmnd = usbcmd.cbw.CDB[0]
        the CDB[0] will decide the command in rkusb protocol

        cbw need a string type
        '''
        #print '\nCDB[0] : ' + self.dump_str2hex(cbw[15]) + '\n'
        #print '\n' + self.dump_str2hex(cbw[12:16]) + '\n'
        self.__dev_handle.bulkWrite(self.EP_OUT, cbw)

    def send_or_recv_data(self, data_len=0, data=None):
        '''
        if there is data, means send
        # no data, means recv
        '''
        if data:
            self.__dev_handle.bulkWrite(self.EP_OUT, data)
        else:
            return self.__dev_handle.bulkRead(self.EP_IN, data_len)

    def recv_csw(self, csw=None):
        self.__dev_handle.bulkRead(self.EP_IN, BULK_CS_WRAP_LEN)

    def rk_usb_read(self, offset, size, filename):
        total = size
        while size > 0:
            show_process(size - RKFT_OFF_INCR, total, 'Reading')

            self.send_cbw(bulk_cb_wrap("READ_LBA", offset, RKFT_OFF_INCR))
            block = self.send_or_recv_data(data_len=RKFT_BLOCKSIZE)
            self.recv_csw()

            if size < RKFT_BLOCKSIZE and len(block) < size:
                block = block[:size]
            if block:
                filename.write(block)

            offset += RKFT_OFF_INCR
            size -= RKFT_OFF_INCR

    def rk_write_partition(self, offset, size, file_name):
        image_size_bytes = os.lstat(file_name).st_size
        if image_size_bytes % PARTITON_SECTOR_SIZE == 0:
            one_more_sector = 0
        else:
            one_more_sector = 1
        image_size_sectors = image_size_bytes / PARTITON_SECTOR_SIZE + one_more_sector

        original_offset = offset

        self.__logger.ftlog_dividor()
        self.__logger.ftlog_print("Starting write %s(%d bytes)\n" % (file_name,
                                                                     image_size_sectors))
        with open(file_name) as filename:
            if image_size_sectors <= size:
                # just write the image file size to partiton
                self.rk_usb_write(offset, image_size_sectors, filename)
            else:
                print 'partition size is too small'
                sys.exit(-1)

        if self.__chk_rw:
            # Verify backup
            # just compare the image file's size is enough
            self.cmp_part_with_file(
                original_offset, image_size_sectors, file_name)

        self.__logger.ftlog_nice("Done")

    def cmp_part_with_file(self, offset, size, file_name):
        '''
        Compare the image file with local copy
        file_name : local file name
        '''
        with open(file_name) as filename:
            ret = self.__cmp_part_with_file(offset, size, filename)
            if not ret:
                self.__logger.ftlog_error("\nIntegrity check Error\n")
            else:
                self.__logger.ftlog_nice("\nIntegrity check Successfully\n")

    def __cmp_part_with_file(self, offset, size, filename):
        total = size
        while size > 0:
            show_process(size - RKFT_OFF_INCR, total, 'Checking image')

            # read the image file as block1
            block1 = filename.read(RKFT_BLOCKSIZE)

            # read the image on disk as block2
            self.send_cbw(bulk_cb_wrap("READ_LBA", offset, RKFT_OFF_INCR))
            block2 = self.send_or_recv_data(data_len=RKFT_BLOCKSIZE)
            self.recv_csw()

            # check length first
            if len(block1) == len(block2):
                if block1 != block2:
                    # self.__logger.ftlog_print("Flash at 0x%08X is differnt from file!\n" % offset)
                    self.integrity = False
            # we got some same data
            else:
                # endof the block1
                if len(block1) == 0:
                    break

                # compare the same length of data
                block2 = block2[:len(block1)]
                if block1 != block2:
                    # self.__logger.ftlog_print("Flash at 0x%08X is differnt from file!\n" % offset)
                    self.integrity = False

            offset += RKFT_OFF_INCR
            size -= RKFT_OFF_INCR

        return self.integrity

    def rk_usb_write(self, offset, size, filename):
        total = size
        while size > 0:
            show_process(size - RKFT_OFF_INCR, total, 'Writing')

            block = filename.read(RKFT_BLOCKSIZE)
            if not block:
                break

            # FIXME : wired situation when write large file
            # store the image into byte format
            # if not to do so, hanging will happen
            byte_buf = bytearray(RKFT_BLOCKSIZE)
            byte_buf[:len(block)] = block

            self.send_cbw(bulk_cb_wrap("WRITE_LBA", offset, RKFT_OFF_INCR))

            # FIXME : convert the byte format into string
            self.send_or_recv_data(data=str(byte_buf))
            self.recv_csw()

            offset += RKFT_OFF_INCR
            size -= RKFT_OFF_INCR

    def rk_reboot(self):
        self.send_cbw(bulk_cb_wrap("DEVICE_RESET"))
        self.recv_csw()
        self.__logger.ftlog_print("Rebooting device\n")

    def rk_write_parameter(self, parameter_file):
        with open(parameter_file) as filename:
            data = filename.read()
            buf = RKCRC.make_parameter_image(data)
        assert len(buf) <= PART_BLOCKSIZE
        with io.BytesIO(buf) as filename:
            self.__logger.ftlog_print(
                "Writing parameter file %s\n\n" % parameter_file)
            self.rk_usb_write(0x00000000, PART_BLOCKSIZE, filename)

    def rk_read_parameter(self, parameter_file):
        self.__logger.ftlog_print(
            "Backuping parameter to file %s\n" % parameter_file)

        with io.BytesIO() as filename:
            self.rk_usb_read(0x00000000, PART_BLOCKSIZE, filename)
            data = filename.getvalue()
        data = RKCRC.verify_parameter_image(data)
        if data:
            with open(parameter_file, 'wb') as filename:
                filename.write(data)
        else:
            self.__logger.ftlog_error("Invalid parameter file!\n")

    def rk_erase_partition(self, name, offset, size):
        # write the storage with empty 0xFF
        buf = ''.join([chr(0xFF)] * RKFT_BLOCKSIZE)
        total = size
        while size > 0:
            show_process(size - RKFT_OFF_INCR, total, 'Erase')

            self.send_cbw(bulk_cb_wrap("WRITE_LBA", offset, RKFT_OFF_INCR))
            self.send_or_recv_data(data=buf)
            self.recv_csw()

            offset += RKFT_OFF_INCR
            size -= RKFT_OFF_INCR

        self.__logger.ftlog_nice("\nPartition %s erased\n" % name[1:])
