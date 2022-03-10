#!/usr/bin/python3
from ast import AsyncFunctionDef
import collections
import os
import select
import sys
import termios
import time

def d(*args, **kwargs):
    return print(*args, **kwargs, file=sys.stderr)

def ubbp(buffer):  # unbufferend binary print()
    sys.stdout.buffer.write(buffer)
    sys.stdout.buffer.flush()

class MouseSettings(object):
    def __init__(self, new_mode):  # store settings
        self.saved = {}
        modes = (9, 1000, 1001, 1003, 1004)
        for mode in modes:
            state = int(MouseSettings.read_setting(mode))
            if state in (0, 3, 4):  # not recognized, permanently on and off
                continue
            elif state not in (1, 2):
                raise RuntimeError(f'DECRQM request returned {state} for {mode}.')
            else:
                self.saved[mode] = True if state == 1 else False
        ubbp(b'\x1b[?%dh' % new_mode)

    def restore(self):
        for mode in self.saved:
            ubbp(b'\x1b[?%d%c' % (mode, b'h' if self.saved[mode] else b'l'))

    @staticmethod
    def read_setting(setting):
        ubbp(b'\x1b[?%d$p' % setting)  # ESC ? 1000 $ p
        # ESC ? 1000 ; 1 $ y
        return EscapeReader('read settings', True).start(b'[?%d;' % setting).result(1).end(b'$y')

class MouseScreen(object):
    def __enter__(self):
        self.oldterm = termios.tcgetattr(0)
        newterm = termios.tcgetattr(0)
        newterm[3] &= ~termios.ICANON # & ~termios.ECHO
        termios.tcsetattr(0, termios.TCSANOW, newterm)
        os.set_blocking(0, False)
        self.mouse_setting = MouseSettings(9)
        return self


    def __exit__(self, type, value, traceback):
        self.mouse_setting.restore()
        termios.tcsetattr(0, termios.TCSAFLUSH, self.oldterm)
        d('Exit through contextmanager.')


def read_wheel_click(blocking):
    while True:
        r = EscapeReader('wheel click', blocking).start(b'[M').result(3).end()
        if r is None:
            return None
        elif r is False or r[0] not in (96, 97):
            continue
        else:
            return -1 if r[0] == 97 else 1

def read_wheel(blocking):
    result = 0
    while True:
        r = read_wheel_click(False)
        if r is False:
            continue
        elif r is None:
            break
        else:
            result += r
    if result:
        return result
    while blocking:
        r = read_wheel_click(True)
        if r is False:
            continue
        else:
            return r


def stays_failed(function):
    def test_first(self, *args, **kwargs):
        if not self.error and not self.would_block:
            function(self, *args, **kwargs)
        return self
    return test_first

class EscapeReader(object):
    def __init__(self, id, blocking=False):  # skip to escape
        self.id = id
        self.would_block = False
        self.error = False
        while True:
            ch = sys.stdin.buffer.read(1)
            if ch == b'\x1b':
                break
            elif ch == None:
                if blocking:
                    self.d('went blocking')
                    select.select([0], [], [])
                else:
                    self.would_block = True
                    break

    def d(self, msg):
        d(f'{self.id}: {msg}')

    @stays_failed
    def start(self, string):
        for int_match in string:
            ch_match = bytes((int_match,))
            ch_in = sys.stdin.buffer.read(1)
            if ch_in == ch_match:
                continue
            else:
                self.d(f'Did not receive expected bytes: {ch_in} != {ch_match}.')
                self.error = True
                break

    @stays_failed
    def result(self, amount):
        self.result = sys.stdin.buffer.read(amount)
        if self.result == None or len(self.result) != amount:
            self.d('Could not read all result bytes.')
            self.error = True

    def end(self, string=b''):
        self.start(string)
        if self.would_block:
            return None
        elif self.error:
            return False
        else:
            return self.result

class Brightness(object):
    def __init__(self, brightness=0):
        self.brightness = brightness

    def dim(self, change):
        d('dim:', change)
        time.sleep(2)
        self.brightness += change
        return self.brightness


with MouseScreen() as scr:
    d('hi')
    b = Brightness()
    while True:
        b.dim(read_wheel(True))
