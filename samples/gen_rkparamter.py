#!/usr/bin/env python
# coding=utf-8

'''
Generate a binary <data> parameter.bin file with <ASCII> text parameter.txt

Usage :
    generate partition.bin :
    python gen_rkparamter.py -p

    unpack the partition.bin :
    python gen_rkparamter.py -u
'''

'''
Using hexdump and file to see the differences

$ hexdump -C parameter.txt | head
00000000  46 49 52 4d 57 41 52 45  5f 56 45 52 3a 36 2e 30  |FIRMWARE_VER:6.0|
00000010  2e 30 0a 4d 41 43 48 49  4e 45 5f 4d 4f 44 45 4c  |.0.MACHINE_MODEL|
00000020  3a 72 6b 33 32 38 38 0a  4d 41 43 48 49 4e 45 5f  |:rk3288.MACHINE_|
00000030  49 44 3a 30 30 37 0a 4d  41 4e 55 46 41 43 54 55  |ID:007.MANUFACTU|
00000040  52 45 52 3a 52 4b 33 32  38 38 0a 4d 41 47 49 43  |RER:RK3288.MAGIC|
00000050  3a 20 30 78 35 30 34 31  35 32 34 42 0a 41 54 41  |: 0x5041524B.ATA|
00000060  47 3a 20 30 78 36 30 30  30 30 38 30 30 0a 4d 41  |G: 0x60000800.MA|
00000070  43 48 49 4e 45 3a 20 33  32 38 38 0a 43 48 45 43  |CHINE: 3288.CHEC|
00000080  4b 5f 4d 41 53 4b 3a 20  30 78 38 30 0a 50 57 52  |K_MASK: 0x80.PWR|
00000090  5f 48 4c 44 3a 20 30 2c  30 2c 41 2c 30 2c 31 0a  |_HLD: 0,0,A,0,1.|

$ hexdump -C partition.bin | head
00000000  50 41 52 4d eb 02 00 00  46 49 52 4d 57 41 52 45  |PARM....FIRMWARE|
00000010  5f 56 45 52 3a 36 2e 30  2e 30 0a 4d 41 43 48 49  |_VER:6.0.0.MACHI|
00000020  4e 45 5f 4d 4f 44 45 4c  3a 72 6b 33 32 38 38 0a  |NE_MODEL:rk3288.|
00000030  4d 41 43 48 49 4e 45 5f  49 44 3a 30 30 37 0a 4d  |MACHINE_ID:007.M|
00000040  41 4e 55 46 41 43 54 55  52 45 52 3a 52 4b 33 32  |ANUFACTURER:RK32|
00000050  38 38 0a 4d 41 47 49 43  3a 20 30 78 35 30 34 31  |88.MAGIC: 0x5041|
00000060  35 32 34 42 0a 41 54 41  47 3a 20 30 78 36 30 30  |524B.ATAG: 0x600|
00000070  30 30 38 30 30 0a 4d 41  43 48 49 4e 45 3a 20 33  |00800.MACHINE: 3|
00000080  32 38 38 0a 43 48 45 43  4b 5f 4d 41 53 4b 3a 20  |288.CHECK_MASK: |
00000090  30 78 38 30 0a 50 57 52  5f 48 4c 44 3a 20 30 2c  |0x80.PWR_HLD: 0,|

$ file parameter.txt
parameter.txt: ASCII text, with very long lines

$ file partition.bin
partition.bin: Par archive data
'''

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(os.path.curdir)))
import misc.rkcrc as RKCRC


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print __doc__
        sys.exit(-1)

    if sys.argv[1] == '-p':
        print 'Packing parameter...'
        # open parameter.txt for read
        with open("parameter.txt") as parameter:
            context = parameter.read()

        # pack tag, ... crc
        buf = RKCRC.make_parameter_image(context)

        # wirte to bin file
        with open("partition.bin", 'w') as binfile:
            binfile.write(buf)
        print 'Done.'
    elif sys.argv[1] == '-u':
        print 'Unpacking...'
        # open file with binary mode
        with open("partition.bin", 'rb') as partition:
            data = partition.read()
            buf = RKCRC.verify_parameter_image(data)

        # open newparameter.txt for backup context
        with open("newparameter.txt", "w") as parameter:
            parameter.write(buf)
        print 'Done'
    else:
        print __doc__
