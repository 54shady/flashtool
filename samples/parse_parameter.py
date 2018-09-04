#!/usr/bin/env python
# coding=utf-8

import re

# partition format as below
# size@offset(name)
# -@offset(name)
PARTITION_PATTERN = re.compile(r'(-|0x[0-9a-fA-F]+)@(0x[0-9a-fA-F]+)\((.*?)\)')

# assume flash total size in byte
FLASH_SIZE = 30777344

# parameter file name
PARAMETER_FILE_NAME = "parameter"


def main():
    partitions = []
    with open(PARAMETER_FILE_NAME) as filename:
        for line in filename.read().split('\n'):
            if line.startswith('CMDLINE:'):
                for size, offset, name in re.findall(PARTITION_PATTERN, line):
                    offset = int(offset, 16)
                    if size == '-':
                        size = FLASH_SIZE - offset
                    else:
                        size = int(size, 16)

                    #print '%s : size(%d), offset(%d)' % (name, size, offset)
                    partitions.append((name, size, offset))

    print partitions


if __name__ == '__main__':
    main()
