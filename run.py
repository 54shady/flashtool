#!/usr/bin/env python

# coding=utf-8

import sys
from main import FlashTool

if __name__ == '__main__':
    app = FlashTool()
    sys.exit(app.main(sys.argv[1:]))
