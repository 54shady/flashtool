#!/usr/bin/env python

# coding=utf-8

import sys
from main import CliMain

if __name__ == '__main__':
    app = CliMain()
    sys.exit(app.main(sys.argv[1:]))
