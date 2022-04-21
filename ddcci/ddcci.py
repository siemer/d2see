#!/usr/bin/python3
# coding: utf-8

'''
Copyright 2015 Robert Siemer

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from contextlib import contextmanager
import fcntl
import functools
import glob
import operator
import os
import random
import sys
import time

# 1 i2c messages
# 2 i2c-dev messages
# 3 ddcci messages

# 1 i2c messages

# (controller view point:)
# First comes the start condition. The following data are bytes.
# The first byte is always written: the (slave) device address (7 bits) and
# 1 bit indicates read (1) or write (0).
# The following bytes are read or written according to the rw bit.
# On writes: the slave acknowledges each byte (I think).
# On read: controller can actually also NACK a byte (I think), but otherwise
# controller just stops reading(?)
# End condition is sent from the controller.

# Actually, messages (i.e. read/write blocks) can be chained together to form
# a transaction, by sending repeated start conditions (instead of end).
# But according to wikipedia, many slave devices don’t care about that detail.

# 2 i2c-dev messages

# When using Linux i2c-dev devices, the 7bit address is set by ioctl() on
# the open()ed device. The rw bit is according to read() or write(),
# obviously. There are i2c-dev docs.


# 3 ddc/ci messages

# I’m writing this the third time now and I have to say: the ddc/ci spec
# is such a messy mix of i2c tech with ddc/ci message ideology and
# inconsistent with that as well. It is just easier and faster to explain
# when throwing out the source/destination address bullshit it contains.

# Ok, the slave address is 0x37. So the address-rw-byte is 0x6e/0x6f for
# writing/reading. With linux i2c-dev you do not come in touch with it
# directly. Even though the ddc/ci spec includes it in all regards (and
# really bad so), in the following paragraphs, I’ll leave that byte out
# of consideration when talking about the actual data to be written or read.

# 3.1 checksum

# write: xor all data bytes together and xor again with 0x6e, add this
# checksum at the end

# read: xor all data together including checksum: outcome should be 0x50

# 3.1 message structure

# write: first always 0x51, then amount of following bytes without
# checksum or with 0x80 (i.e. data length minus 3), “vcp” command byte,
# arguments (depend on command), checksum

# read: first always 0x6e, length like in writes, fitting vcp reaction
# byte, ..., checksum

# Spec is a badly written mix of ddc/ci message ideology and i2c on the
# wire tech. The former are messages with sender and destination (like
# packets). The latter contain only 7bits to address the slave for
# reading _and_ writing. No sender address required.

# All ddc/ci messages go like this:

# read goes like this:
# 0x6f (written by master: i2c 0x37 addr + 1 for reading), then 0x6e (read)
# - first byte has two functions
#   - written as i2c addressing
#   - but conceptually also the first byte of the (read!) ddc/ci message
#   - 
#   - is part of the checksum
#   - BUT: 
#   i2c addressing
# - 

# writes start with:
# 0x6e (i2c 0x37 addr + 0 for writing), then 0x51
# - on communications from master to slave, the spec seems to think of
#   using the 


# If ddc/ci wants to keep that sender/destination non-sense, why not use
# the entire message as i2c data?
# Why having two addresses for each entity (least significant bit of a byte
# is flipped to form the other address)? That looks like i2c’s first byte for
# reading/writing.


# Why not calculate the checksum with the first byte as-is or without it?

# And why not be consistent with the use of the two addresses?


# 
# It starts with the fact that slave address 0x37 is written as 0x6e/0x6f.
# That would be the addr-rw-byte on i2c: i.e. 0x37 left shifted by 1 either
# with or without the rw bit (least significant bit) set.
# It then introduces a “host address” 0x50/0x51. But the bus master needs no
# address.
# Finally a ddc/ci message starts with the destination address followed by the
# source address (and then more). Like a packet. Written by the sender.
# But on the i2c wire, the first byte is always written by the master, with
# the address of the slave (and the rw bit). 
# written by the host, and always the addr of the 
# 1. It considers the i2c address/rw byte part of the ddc/ci message.
# 2. It talks about slave address 0x6e/0x6f, which is i2c address 0x37 with
#    rw bit set to write/read. (0x6e >> 1 == 0x37)
# 3. It gives the bus master the address 0x50/0x51 (i2c addr 0x28), but the
#    bus master needs no address!
# 4. The 2nd ddc/ci byte (1st i2c/i2c-dev data byte) is the source address!
#    On ddc/ci writes, you are supposed to write 0x51, i.e. master addr +
#    read(!) mode. WTF
#    On reads, expect a 0x6e (slave + write mode).
# 5. The 1st ddc/ci byte (i.e. i2c addr-rw-byte) is 0x6e on write (which is
#    what i2c should indeed be sending), but it is supposed to be 0x50 on
#    reads. Supposedly written by the slave? That would be the host addr +
#    write(!) mode. WTF

# ddc/ci messages are 


# length byte first bit: should be 0 on vendor specific msgs
# op codes:
# 0x01 VCP request
# 0x02 VCP reply
# 0x03 VCP set
# 0x06 timing reply
# 0x07 timing request
# 0x09 VCP reset  (in spec, but what is it?)
# 0x0c save current settings
# 0xa1 display self-test reply
# 0xb1 display self-test request
# 0xc0-0xc8 is vendor specific???
# 0xe1 identification reply
# 0xe2 table read request
# 0xe3 capabilities reply
# 0xe4 table read reply
# 0xe7 table write
# 0xf1 identification request (to find an internal diplay dependent device)
# 0xf3 capabilities request
# 0xf5 enable application report


# host should
# 1. get ID string
# 2. get capability string
# 3. enable application message report
# ...then ready to go

# Virtual Control Panel (VCP) codes
#
# 0x00-0xdf is MCCS standard
# 0xe0-0xff are manufacturer use
# 0x10 brightness
# 0x12 contrast
# 0x14 select color preset


# Controls
#
# C – Continuous (0-max)
# NC – Non Continuous
# T – Table


examples = {name: bytearray.fromhex(string) for name, string in {
    'enable application report': '6e 51 82 f5 01 49',
    'application test': '6e 51 81 b1 0f',
    'application test reply': '6f 6e 82 a1 00 1d',
    'null message': '6f 6e 80 be',
    # completely nuts, but as in spec
    # excluding first byte (“destination address”), msg is the same
    # source (second byte) is even/odd on writing/reading
    'external: host to touch screen': 'f0 f1 81 b1 31',
    'external: touch screen to host': 'f1 f0 82 a1 00 83',
    'internal: host to touch screen': '6e f1 81 b1 af',
    'internal: touch screen to host': '6f f0 82 a1 00 83',
}.items()}

# dst addr, “src addr”, ((amount of following bytes)-1) & 0x80 if 
#  MCCS std op code to follow, op code, ..., chksum

# (length) from op code, without checksum (wait period afterwards):
# (2) 0x01 get vcp, vcp code (40ms)
# (8) 0x02 get vcp reply, result code: 0x00 no erro or 0x01 unsupported vcp,
#  vcp code, vcp type code: 0x00 set parameter or 0x01 momentary, max value
#  big endian, present value big endian (2 bytes each)
# (4) 0x03 set vcp, vcp code, value big endian (50ms)
# (1) 0x07 get timing report (40ms)
# (7??) no length?? 0x06 get timing report reply, 0x4e “timing messgae op code”,
#  status, horizontal freq big endian, vertical freq big endian
# (1) 0x0c save current settings (200ms)
# (1) 0xb1 application test
# (2) 0xa1 application test reply, status
# (3) 0xf3, offset big endian
# () 0xe3, offset big endian, data [spec: max 32 bytes data] (50ms from reply??)


messages = {
  'request current brightness': '6e 51 82 01 10',
  # at least 40ms later
  'read current brightness': '6f 6e 88 02 00 10',
  'set brightness': '6e 51 84 03 10 00 32', # and wait 50ms
  'save current settings': '6e 51 81 0c', # wait 200ms before next msg
  'request capabilities': '6e 51 83 f3 00 00',
  'read capabilities': '6f 6e a3 e3 00 00 ', # wait 50ms now or in between?
  'request timing report': '6e 51 81 07', # wait 40ms
  'red timing report': '6f 6e 06 4e 00 00 00 00 00', # wait 50ms before next
  'write table': '6e 51 a3 e7 73 00 00 ', # wait 50ms
  'request table': '6e 51 83 e2 73 00 00', # 83 or better 84?
  'read table': '6f 6e a3 e4 00 00 ', # wait 50ms
}

def printbytes(template, *args):
  strings = []
  for arg in args:
    if isinstance(arg, str):
      strings.append(arg)
    else:
      strings.append(' '.join(['{:02x}'.format(byte) for byte in arg]))
  print(template.format(*strings))


class I2cDev(object):
  def __init__(self, file_name, i2c_slave_addr, **kwargs):
    super().__init__(**kwargs)
    self._dev = os.open(file_name, os.O_RDWR)
    fcntl.ioctl(self._dev, 0x0703, i2c_slave_addr)  # CPP macro: I2C_SLAVE

  def read(self, length):
    ba = os.read(self._dev, length)
    if length < 20: printbytes('read: {}', ba)
    return ba

  def write(self, *args, **kwargs):
    printbytes('write: {}', args[0])
    return os.write(self._dev, *args, **kwargs)

class CrappyHardwareError(IOError):
  pass

class Ddcci(I2cDev):
  def __init__(self, **kwargs):
    kwargs['i2c_slave_addr'] = 0x37
    super().__init__(**kwargs)
    self.waiter = Waiter(.2, .2)
    self.set_delay = self.waiter.set_delay
    self.safe_delay = self.waiter.safe_delay
    self.set_delay_permanently = self.waiter.set_delay_permanently

  def write(self, *args):
    ba = bytearray(args)
    ba.insert(0, len(ba) | 0x80)
    ba.insert(0, 0x51)
    ba.append(functools.reduce(operator.xor, ba, 0x6e))
    self.waiter.wait('w')
    return I2cDev.write(self, ba)

  @staticmethod
  def check_read_bytes(ba):
    checks = {
      'source address': ba[0] == 0x6e,
      'checksum': functools.reduce(operator.xor, ba) == 0x50,
      'length': len(ba) >= (ba[1] & ~0x80) + 3
        }
    if False in checks.values():
      raise IOError(checks)

  def read(self, amount):
    self.waiter.wait('r')
    b = I2cDev.read(self, amount + 3)
    if not [i for i in b if i]:
      raise CrappyHardwareError()
    Ddcci.check_read_bytes(b)
    return b[2:-1]

class Waiter(object):
  def __init__(self, *args, **kwargs):
    self.last_which = 'r'
    self.last_when = 0
    self.set_delay_permanently(*args, **kwargs)

  def set_delay_permanently(self, r, w):
    self._calc_delays(dict(r=r, w=w))

  @contextmanager
  def set_delay(self, *args, **kwargs):
    saved_delays = self.delays_raw
    self.set_delay_permanently(*args, **kwargs)
    try:
      yield
    finally:
      self._calc_delays(saved_delays)

  def safe_delay(self):
    return self.set_delay(.2, .2)

  def _calc_delays(self, raw):
    self.delays_raw = raw
    self.delays = dict(wr=raw['r'], ww=raw['w'], rr=0)
    self.delays['rw'] = max(*raw.values())
    print(self.delays)

  def wait(self, which):
    assert which in ('r', 'w')
    succession = self.last_which + which
    wait_time = self.last_when + self.delays[succession] - time.time()
    print(f'{succession}: {wait_time}s')
    if wait_time > 0:
      time.sleep(wait_time)
    self.last_when = time.time()
    self.last_which = which


class Mccs(Ddcci):
  def write(self, vcpopcode, value):
    return Ddcci.write(self, 0x03, vcpopcode, *value.to_bytes(2, 'big'))

  def read(self, vcpopcode):
    for i in range(2):
      Ddcci.write(self, 0x01, vcpopcode)
      try:
        b = Ddcci.read(self, 8)
      except CrappyHardwareError:
        print('Retrying read() operation.')
        b = bytes(8)
        continue
      else:
        break
    checks = {
      'is feature reply': b[0] == 0x02,
      'supported VCP opcode': b[1] == 0,
      'answer matches request': b[2] == vcpopcode,
        }
    if False in checks.values():
      raise IOError(checks)
    return b[3], int.from_bytes(b[4:6], 'big'), int.from_bytes(b[6:8], 'big')

  def flush(self):
    return Ddcci.write(self, 0x0c)

  def capabilities(self):
    Ddcci.write(self, 0xf3, 0, 0)
    # ...

  def timing(self):
    Ddcci.write(self, 0x07)
    return Ddcci.read(self, 6)

class MccsNamed(Mccs):
  @property
  def brightness_both(self):
    m, c = self.read(0x10)[1:]
    return c, m

  @property
  def brightness_max(self):
    return self.read(0x10)[1]

  @property
  def brightness(self):
    return self.read(0x10)[2]

  @brightness.setter
  def brightness(self, value):
    return self.write(0x10, value)

class Edid(I2cDev):
  def __init__(self, **kwargs):
    kwargs['i2c_slave_addr'] = 0x50
    super().__init__(**kwargs)

  def read_edid(self):
    candidate = I2cDev.read(self, 512)  # current position unknown to us
    start = candidate.find(bytes.fromhex('00 FF FF FF FF FF FF 00'))
    if start < 0:
      raise IOError()
    e = candidate[start:start+256]
    manufacturer = int.from_bytes(e[8:10], 'big')
    m = ''
    for i in range(3):
      m = chr(ord('A') - 1 + (manufacturer & 0b11111)) + m
      manufacturer >>= 5
    printbytes('{} P/C S/N {}, week/year {}, EDID ver. {}', m, e[10:16], e[16:18], e[18:20])
    return e


class TimingTest(object):
  def __init__(self, monitor):
    self.monitor = monitor

  def safe_check(self):
    m = self.monitor
    with m.safe_delay():
      orig, mx = m.brightness_both
      v = 1 if orig == 0 else orig - 1
      m.brightness = v
      assert m.brightness == v
      m.brightness = orig
      assert m.brightness == orig
      return orig, mx

  def _test_read(self, repeat, mx, r, w):
    m = self.monitor
    with m.set_delay(r, w):
      for i in range(repeat):
        v = random.randint(0, mx)
        m.brightness = v
        try:
          if m.brightness != v:
            return False
        except OSError:
          return False
    return True

  def _test_write(self, repeat, mx, r, w):
    m = self.monitor
    for i in range(repeat):
      burst = random.randint(3, 8)
      with m.set_delay(r, w):
        for j in range(burst):
          v = random.randint(0, mx)
          m.brightness = v
      with m.safe_delay():
        if m.brightness != v:
          return False
    return True


  def _test(self, what, repeat, r, w):
    orig, mx = self.safe_check()
    m = self.monitor
    start = time.time()
    testfunc = self._test_read if what == 'read' else self._test_write
    result = testfunc(repeat, mx, r, w)
    with m.safe_delay():
      m.brightness = orig
      assert m.brightness == orig
    print(f'{"SUCC" if result else "FAIL"} {what[0]} delay ({r}, {w}) took {time.time() - start} seconds')
    return result

  def test(self):
    r = 1.5 * self.binary_search(0, .2, lambda r: self._test('read', 4, r, .2))
    w = 1.5 * self.binary_search(0, .2, lambda w: self._test('write', 4, r, w))
    r = 1.2 * self.binary_search(0, r, lambda r: self._test('read', 8, r, w))
    w = 1.2 * self.binary_search(0, w, lambda w: self._test('write', 8, r, w))
    assert self._test('write', 5, r, w)
    assert self._test('read', 5, r, w)
    self.monitor.set_delay_permanently(r, w)

  @staticmethod
  def binary_search(a, b, function):
    good = b
    bad = a
    for i in range(5):
      test_point = bad + (good - bad) / 2
      result = function(test_point)
      if result:
        good = test_point
      else:
        bad = test_point
    return good


class Monitor(MccsNamed):
  def __init__(self, **kwargs):
    self.edid = Edid(**kwargs).read_edid()
    super().__init__(**kwargs)

  @classmethod
  def test(self, fname):
    try:
      instance = self(file_name=fname)
    except IOError:
      return None
    else:
      return instance

  @classmethod
  def scan(self):
    return [x for x in map(self.test, glob.glob('/dev/i2c-*')) if x]


if __name__ == '__main__':
  ms = Monitor.scan()
  TimingTest(ms[0]).test()
  m = Mccs(sys.argv[1])
  print('Brightness', m.read(0x10))
