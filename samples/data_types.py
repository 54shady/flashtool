#!/usr/bin/env python
# coding=utf-8

'''
python 中对文本和二进制做了区分
文本(unicode 编码, 即string的集合)用于显示
二进制(bytes 类型, 即byte的集合)用于数据传输
'''

'''
有如下str1,想要修改其内容
需要先将其转化为bytestring修改再转为string
'''
str1 = 'python'
print str1
try:
    str1[0] = 'P'
except TypeError:  # 'str' object does not support item assignment
    print 'str1[0] = \'P\' ERROR : string object does not support item assignment'

# convert string into bytestring
bstr1 = bytearray(str1)
bstr1[0] = 'P'

# convert bytestring into string
str1 = str(bstr1)
print str1

# substring
str1 = 'python'
str1 = str1[3:5]
print str1
