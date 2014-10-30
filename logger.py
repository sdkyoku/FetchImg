#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Contributor:
#       SDK             <sdk19881107@yahoo.co.jp>
#       Sarasa          <chiey.qs@gmail.com>
# Specially thanks:
#       GoAgent Team

__version__ = '0.1.01'

import sys
import os
import time


class MyLogger(type(sys)):
    CRITICAL = 50
    FATAL = CRITICAL
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10
    NOTSET = 0
    LEVEL = 20

    def __init__(self, *args, **kw):
        self.level = self.__class__.INFO
        self.__set_error_color = lambda: None
        self.__set_warning_color = lambda: None
        self.__set_debug_color = lambda: None
        self.__reset_color = lambda: None
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            if os.name == 'nt':
                import ctypes
                set_console_text_attr = ctypes.windll.kernel32.SetConsoleTextAttribute
                get_std_handle = ctypes.windll.kernel32.GetStdHandle
                self.__set_error_color = lambda: set_console_text_attr(get_std_handle(-11), 0x04)
                self.__set_warning_color = lambda: set_console_text_attr(get_std_handle(-11), 0x06)
                self.__set_debug_color = lambda: set_console_text_attr(get_std_handle(-11), 0x002)
                self.__reset_color = lambda: set_console_text_attr(get_std_handle(-11), 0x07)
            elif os.name == 'posix':
                self.__set_error_color = lambda: sys.stderr.write('\033[31m')
                self.__set_warning_color = lambda: sys.stderr.write('\033[33m')
                self.__set_debug_color = lambda: sys.stderr.write('\033[32m')
                self.__reset_color = lambda: sys.stderr.write('\033[0m')

    @classmethod
    def get_logger(cls, *args, **kw):
        return cls(*args, **kw)

    def basic_config(self, *args, **kw):
        self.level = int(kw.get('level', self.__class__.INFO))
        if self.level > self.__class__.DEBUG:
            self.debug = self.dummy

    def log(self, level, fmt, *args, **kw):
        sys.stderr.write('%s - [%s] %s\n' % (level, time.ctime()[4:-5], fmt % args))

    def dummy(self, *args, **kw):
        pass

    def debug(self, fmt, *args, **kw):
        if self.LEVEL == 20:
            return
        self.__set_debug_color()
        self.log('DEBUG', fmt, *args, **kw)
        self.__reset_color()

    def info(self, fmt, *args, **kw):
        self.log('INFO', fmt, *args, **kw)

    def warning(self, fmt, *args, **kw):
        self.__set_warning_color()
        self.log('WARNING', fmt, *args, **kw)
        self.__reset_color()

    def error(self, fmt, *args, **kw):
        self.__set_error_color()
        self.log('ERROR', fmt, *args, **kw)
        self.__reset_color()

    def set_logger_level(self, level):
        self.LEVEL = int(level)


mylogger = sys.modules['mylogger'] = MyLogger('mylogger') # eof
