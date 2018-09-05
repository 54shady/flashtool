#!/usr/bin/env python


# coding=utf-8

import io
import re
import protocol
import time
import misc.rkcrc as RKCRC
import sys


USB_BULK_READ_SIZE = 512
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
        context = protocol.USBContext()
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
CBW_CDB1 = 16
CBW_OFFSET = 17
CBW_SIZE = 23
BULK_CBW = [chr(0)] * 31
BULK_CBW[0:4] = 'USBC'
global_cmd_id = -1
BULK_CS_WRAP_LEN = 13  # struct bulk_cs_wrap 13 bytes

# command block wrapper


def bulk_cb_wrap(flag, command, offset, size):
    BULK_CBW[CBW_TAG] = next_cmd_id()
    BULK_CBW[CBW_FLAG] = chr(flag)
    BULK_CBW[CBW_SIZE] = chr(size)
    BULK_CBW[CBW_LUN] = chr((command >> 24) & 0xFF)
    BULK_CBW[CBW_LENGTH] = chr((command >> 16) & 0xFF)
    BULK_CBW[CBW_CDB0] = chr((command >> 8) & 0xFF)
    BULK_CBW[CBW_CDB1] = chr((command) & 0xFF)
    BULK_CBW[CBW_OFFSET] = chr((offset >> 24) & 0xFF)
    BULK_CBW[CBW_OFFSET + 1] = chr((offset >> 16) & 0xFF)
    BULK_CBW[CBW_OFFSET + 2] = chr((offset >> 8) & 0xFF)
    BULK_CBW[CBW_OFFSET + 3] = chr((offset) & 0xFF)
    return BULK_CBW


class RkOperation(object):
    def __init__(self, logger, bus_id, dev_id):
        self.__logger = logger
        # get a usb context, which is a session
        self.__context = protocol.USBContext()
        self.__context.setDebug(3)

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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        del self  # self = None

    def __rk_device_init(self):
        # Init
        self.send_cbw(''.join(bulk_cb_wrap(
            0x80, 0x00060000, 0x00000000, 0x00000000)))
        self.recv_csw()

    def init_device(self):
        if self.__dev_handle.kernelDriverActive(0):
            self.__dev_handle.detachKernelDriver(0)
        self.__dev_handle.claimInterface(0)

        self.__rk_device_init()

        # sleep for 20ms
        time.sleep(0.02)

    def rk_load_partitions(self):
        partitions = []
        self.init_device()

        self.send_cbw(''.join(bulk_cb_wrap(
            0x80, 0x00061a00, 0x00000000, 0x00000000)))
        content = self.send_or_recv_data(data_len=USB_BULK_READ_SIZE)
        self.recv_csw()

        flash_size = (ord(content[0])) | (ord(content[1]) << 8) | (
            ord(content[2]) << 16) | (ord(content[3]) << 24)

        self.send_cbw(''.join(bulk_cb_wrap(
            0x80, 0x000a1400, 0x00000000, PART_OFF_INCR)))
        content = self.send_or_recv_data(data_len=PART_BLOCKSIZE)
        self.recv_csw()

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

    def rk_read_partition(self, offset, size, file_name):
        self.init_device()

        self.__logger.ftlog_dividor()
        self.__logger.ftlog_print("Starting read %s\n" % file_name)

        # open the file for writing
        with open(file_name, 'w') as filename:
            self.rk_usb_read(offset, size, filename)

        # Verify backup.
        self.cmp_part_with_file(offset, size, file_name)

        self.__logger.ftlog_nice("Done")
        self.__logger.ftlog_dividor()

    def dump_str2hex(self, string_value):
        return ' '.join(hex(x) for x in bytearray(string_value))

    def send_cbw(self, cbw):
        '''
        data direction from host to slave
        endpoint is EP_OUT
        '''
        #print self.dump_str2hex(cbw)
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
            show_process(total - size + 32, total, 'Reading')

            self.send_cbw(''.join(bulk_cb_wrap(
                0x80, 0x000a1400, offset, RKFT_OFF_INCR)))
            block = self.send_or_recv_data(data_len=RKFT_BLOCKSIZE)
            self.recv_csw()

            if size < RKFT_BLOCKSIZE and len(block) < size:
                block = block[:size]
            if block:
                filename.write(block)

            offset += RKFT_OFF_INCR
            size -= RKFT_OFF_INCR

    def rk_write_partition(self, offset, size, file_name):
        self.init_device()
        original_offset, original_size = offset, size

        self.__logger.ftlog_dividor()
        self.__logger.ftlog_print("Starting write %s\n" % file_name)
        with open(file_name) as filename:
            self.rk_usb_write(offset, size, filename)

        # Verify backup.
        self.cmp_part_with_file(original_offset, original_size, file_name)
        self.__logger.ftlog_nice("Done")
        self.__logger.ftlog_dividor()

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
            show_process(size - 32, total, 'Checking image')

            # read the image file as block1
            block1 = filename.read(RKFT_BLOCKSIZE)

            # read the image on disk as block2
            self.send_cbw(''.join(bulk_cb_wrap(
                0x80, 0x000a1400, offset, RKFT_OFF_INCR)))
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
        self.init_device()
        total = size
        while size > 0:
            show_process(total - size, total, 'Writing')

            block = filename.read(RKFT_BLOCKSIZE)
            if not block:
                break
            buf = bytearray(RKFT_BLOCKSIZE)
            buf[:len(block)] = block

            self.send_cbw(''.join(bulk_cb_wrap(
                0x80, 0x000a1500, offset, RKFT_OFF_INCR)))
            self.send_or_recv_data(data=str(buf))
            self.recv_csw()

            offset += RKFT_OFF_INCR
            size -= RKFT_OFF_INCR

    def rk_reboot(self):
        self.init_device()
        self.send_cbw(''.join(bulk_cb_wrap(
            0x00, 0x0006ff00, 0x00000000, 0x00)))
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
        self.init_device()

        # write the storage with empty 0xFF
        buf = ''.join([chr(0xFF)] * RKFT_BLOCKSIZE)
        total = size
        while size > 0:
            show_process(size - 32, total, 'Erase')

            self.send_cbw(''.join(bulk_cb_wrap(
                0x80, 0x000a1500, offset, RKFT_OFF_INCR)))
            self.send_or_recv_data(data=buf)
            self.recv_csw()

            offset += RKFT_OFF_INCR
            size -= RKFT_OFF_INCR

        self.__logger.ftlog_nice("\nPartition %s erased\n" % name[1:])
