#!/usr/bin/env python

# coding=utf-8

import sys
from main import FlashTool

def main():
    app = FlashTool()
    sys.exit(app.main(sys.argv[1:]))

if __name__ == '__main__':
    main
