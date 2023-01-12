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
import enum
import fcntl
import functools
import glob
import itertools
import operator
import os
import random
import time
import traceback

import trio
from ddcci import xdg

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
#   - is part of the checksum
#   - ...

# writes start with:
# 0x6e (i2c 0x37 addr + 0 for writing), then 0x51
# - ...

# If ddc/ci wants to keep that sender/destination non-sense, why not use
# the entire message as i2c data?
# Why having two addresses for each entity (least significant bit of a byte
# is flipped to form the other address)? That looks like i2c’s first byte for
# reading/writing.

# Why not calculate the checksum with the first byte as-is or without it?

# And why not be consistent with the use of the two addresses?

# It starts with the fact that slave address 0x37 is written as 0x6e/0x6f.
# That would be the addr-rw-byte on i2c: i.e. 0x37 left shifted by 1 either
# with or without the rw bit (least significant bit) set.
# It then introduces a “host address” 0x50/0x51. But the bus master needs no
# address.
# Finally a ddc/ci message starts with the destination address followed by the
# source address (and then more). Like a packet. Written by the sender.
# But on the i2c wire, the first byte is always written by the master, with
# the address of the slave (and the rw bit).

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


class I2cDev:
  def __init__(self, file_name, i2c_slave_addr):
    self._dev = os.open(file_name, os.O_RDWR)
    fcntl.ioctl(self._dev, 0x0703, i2c_slave_addr)  # CPP macro: I2C_SLAVE

  def read(self, length):
    ba = os.read(self._dev, length)
    if length < 20: printbytes('read: {}', ba)
    return ba

  def write(self, buffer):
    printbytes('write: {}', buffer)
    return os.write(self._dev, buffer)

class EdidDevice:
  def __init__(self, file_name):
    dev = I2cDev(file_name=file_name, i2c_slave_addr=0x50)
    candidate = dev.read(512)  # current position unknown to us
    start = candidate.find(bytes.fromhex('00 FF FF FF FF FF FF 00'))
    if start < 0:
      raise IOError()
    edid = candidate[start:start+256]
    manu_code = int.from_bytes(edid[8:10], 'big')
    manufacturer = ''
    for i in range(3):
      manufacturer = chr(ord('A') - 1 + (manu_code & 0b11111)) + manufacturer
      manu_code >>= 5
    self.edid256 = edid  # always 256 bytes long even for 128 byte EDIDs
    self.edid_id = manufacturer + edid[10:18].hex()  # PC/SN, manufacturing date
    self.file_name = file_name

  @classmethod
  def match_edids(cls, monitor):
      for edev in cls.devices:
        if edev.edid256.startswith(monitor.edid):
          cls.device.remove(edev)
          monitor.init_with_ediddev(edev)


class CrappyHardwareError(IOError):
  pass

class WouldBlockTime(Exception):
  def __init__(self, wait_time):
    super().__init__()
    self.wait_time = wait_time

def async_version_of(method):
  async def async_method(*args, **kwargs):
    while True:
      try:
        res = method(*args, **kwargs)
      except WouldBlockTime as e:
        await trio.sleep(e.wait_time)
        continue
      else:
        return res
  return async_method

class Ddcci:
  def __init__(self, *, file_name, open_config):
    self.waiter = Waiter(open_config)
    self._i2c = I2cDev(i2c_slave_addr=0x37, file_name=file_name)
    self.set_delay = self.waiter.set_delay
    self.safe_delay = self.waiter.safe_delay

  @staticmethod
  def ddc2i2c(buffer):
    ba = bytearray(buffer)
    ba.insert(0, len(ba) | 0x80)
    ba.insert(0, 0x51)
    ba.append(functools.reduce(operator.xor, ba, 0x6e))
    return ba

  def write_nowait(self, buffer):
    self.waiter.prepare('w')
    res = self._i2c.write(Ddcci.ddc2i2c(buffer))
    return res

  write = async_version_of(write_nowait)

  @staticmethod
  def check_read_bytes(ba):
    chk_calc = functools.reduce(operator.xor, ba)
    checks = {
      'source address': ba[0] == 0x6e,
      f'checksum {chk_calc}': chk_calc == 0x50,
      'length': len(ba) >= (ba[1] & ~0x80) + 3
        }
    if False in checks.values():
      raise IOError(checks)

  def read_nowait(self, amount, /, *, compensate=False):
    self.waiter.prepare('r')
    length = amount + 3
    b = self._i2c.read(length)
    leading_zeros = len(list(itertools.takewhile(lambda x: x == 0, b)))
    if leading_zeros == length:
      raise CrappyHardwareError()
    elif leading_zeros and compensate:
      print(f'Compensating {leading_zeros} zeros.')
      b2 = self._i2c.read(leading_zeros + 5)
      b = b[leading_zeros:] + b2[:leading_zeros]
    Ddcci.check_read_bytes(b)
    b = b[2:-1]
    return b

  read = async_version_of(read_nowait)

class Waiter:
  def __init__(self, open_config):
    self.open_config = open_config
    self.last_which = 'r'
    self.last_when = 0
    default_delay = False
    with open_config() as file:
      rw_delays = []
      for _ in range(2):
        try:
          f = float(file.readline())
        except ValueError:
          f = .2
          default_delay = True
        rw_delays.append(f)
    self._set_delay_permanently(*rw_delays)
    self._default_delay = default_delay

  def has_default_delay(self):
    return self._default_delay

  def _write_config(self):
    with self.open_config(mode='w') as file:
      for float_val in self.delays_raw.values():
        file.write(f'{float_val}\n')

  def remove_default_delays(self, rw_delays):
      self._set_delay_permanently(*rw_delays)
      self._write_config()
      self._default_delay = False

  def _set_delay_permanently(self, r, w):
    self._set_internal(dict(r=r, w=w))

  @contextmanager
  def set_delay(self, *args, **kwargs):
    saved_delays = self.delays_raw
    self._set_delay_permanently(*args, **kwargs)
    try:
      yield
    finally:
      self._set_internal(saved_delays)

  def safe_delay(self):
    return self.set_delay(.2, .2)

  def _set_internal(self, raw):
    self.delays_raw = raw
    self.delays = dict(wr=raw['r'], ww=raw['w'], rr=0)
    self.delays['rw'] = max(*raw.values())
    print(self.delays)

  def prepare(self, which):
    '''Either raise WouldBlockTime with corresponding timeout or update this Waiter
    to reflect execution of the corresponding operation. I.e. the prepared op should
    be called immediately.'''
    assert which in ('r', 'w')
    succession = self.last_which + which
    wait_time = self.last_when + self.delays[succession] - time.time()
    # print(f'{succession}: {wait_time}s')
    wait_time = max(0, wait_time)
    if wait_time:
      raise WouldBlockTime(wait_time)
    self.last_when = time.time()
    self.last_which = which


def invalidate_read_preparation(method):
  def new_method(self, *args, **kwargs):
    try:
      res = method(self, *args, **kwargs)
    except WouldBlockTime:
      # either we didn't do anything
      # or we prepared a read in which case attribte was made valid
      raise
    except:
      # could be anything → invalidate
      self._read_vcpopcode = None
      raise
    else:
      # successful read/write → invalidate
      self._read_vcpopcode = None
      return res
  return new_method

def returns_cancel_scope(afunc):
  async def f(*args, task_status=trio.TASK_STATUS_IGNORED, **kwargs):
    with trio.CancelScope() as cs:
      task_status.started(cs)
      return await afunc(*args, **kwargs)
  return f

def try_again(afunc):
  async def new_afunc(*args, **kwargs):
    for iteration in reversed(range(2)):
      try:
        res = await afunc(*args, **kwargs)
      except CrappyHardwareError:
        if iteration == 0:
          raise
        else:
          continue
      else:
        break
    return res
  return new_afunc


class Mccs:
  class Op(enum.Enum):
    READ = (1, 1)
    READ_REPLY = 2
    WRITE = (3, 1, 2)
    CAPABILITIES = (0xf3, 2)

  def __init__(self, *, file_name, open_config):
    self._ddcci = Ddcci(file_name=file_name, open_config=open_config)
    self._read_vcpopcode = None
    self.safe_delay = self._ddcci.safe_delay
    self.set_delay = self._ddcci.set_delay

  async def optimize_delays(self):
    if self._ddcci.waiter.has_default_delay():
      rw_delays = await TimingTest(self).determine_delays()
      self._ddcci.waiter.remove_default_delays(rw_delays)
    else:
      await trio.sleep(0)

  @staticmethod
  def mccs2ddc(op, /, *args):
    assert type(op) is Mccs.Op
    assert type(op.value) is tuple
    assert len(op.value) == len(args) + 1
    res = [op.value[0]]
    for arg, length in zip(args, op.value[1:]):
      res.extend(arg.to_bytes(length, 'big'))
    return res

  @invalidate_read_preparation
  def write_nowait(self, vcpopcode, value):
    return self._ddcci.write_nowait(Mccs.mccs2ddc(Mccs.Op.WRITE, vcpopcode, value))

  write = async_version_of(write_nowait)

  @invalidate_read_preparation
  def read_nowait(self, vcpopcode, *, compensate=False):
    if self._read_vcpopcode != vcpopcode:
      self._ddcci.write_nowait(Mccs.mccs2ddc(Mccs.Op.READ, vcpopcode))
      self._read_vcpopcode = vcpopcode
    b = self._ddcci.read_nowait(8, compensate=compensate)
    checks = {
      'is feature reply': b[0] == Mccs.Op.READ_REPLY.value,
      'supported VCP opcode': b[1] == 0,
      'answer matches request': b[2] == vcpopcode,
        }
    if False in checks.values():
      raise IOError(checks)
    # present value, max value, VCP type code (0 == Set parameter, 1 = Momentary)?!?
    return int.from_bytes(b[6:8], 'big'), int.from_bytes(b[4:6], 'big'), b[3]

  read = async_version_of(read_nowait)

  @invalidate_read_preparation
  def flush_nowait(self):
    return self._ddcci.write([0x0c])

  @invalidate_read_preparation
  def capabilities_nowait(self):
    self._ddcci.write(Mccs.mccs2ddc(Mccs.Op.CAPABILITIES, 0))
    # ...

  @invalidate_read_preparation
  def timing_nowait(self):
    self._ddcci.write([0x07])
    return self._ddcci.read(6)

  @try_again
  async def get_brightness_both(self):
    c, m, _ = (await self.read(0x10))
    return c, m

  @try_again
  async def get_brightness_max(self):
    return (await self.read(0x10))[1]

  @try_again
  async def get_brightness(self):
    return (await self.read(0x10))[0]

  @returns_cancel_scope
  async def set_brightness(self, value):
    return await self.write(0x10, value)


class BaseSetting:
  def __init__(self, controller, register):
    self.controller = controller
    self.register = register

  def read_prepared(self):
    return self.controller._mccs._read_vcpopcode == self.register

  def max_interaction_index(self):
    return len(self.controller._settings)

  def interaction_index(self):
    il = self.controller._interaction_log
    if self.register in il:
      return list(reversed(il)).index(self.register)
    else:
      return self.max_interaction_index()

class Setting2:
  register = 0x2
  # might change this into a w/o setting base...
  def __init__(self):
    self.new_value = None
    self.writings_left = 0

  def ack_write(self, *args):
    self.writings_left = 0

  def select_operation(self):
    assert self.writings_left
    return 'write', (self.new_value,), self.ack_write

  def _write(self, value):
    self.new_value = value
    self.writings_left = 1
    return True

  def priority(self):
    if self.writings_left:
      return (Setting.writing_cycles+1, )
    else:
      return (-1, )


class Setting52(BaseSetting):
  def __init__(self, controller):
    super().__init__(controller, 0x52)
    self.last_value = None  # set to None on reset52()
    self.next_check = 0

  def _reset52(self):
    self.controller.write(Setting2.register, 0x1)
    self.last_value = None

  def select_operation(self):
    time_left = self.next_check - time.time()
    if time_left <= 0:
      return 'read', (), self.ack_read
    else:
      return 'wait', time_left, 0

  def ack_read(self, result):
    value, *args = result
    if self.last_value not in (None, 0) and self.last_value != value:
      self.controller.needs_reset52.no()
    if value == 0:  # continue polling (no news)
      self.next_check = time.time() + 1
    else:
      setting = self.controller.setting(value)
      if setting:  # we work with this setting
        if setting.writings_left == 0:  # ...and we don’t change sth ourselves rn
          setting.reread(from52=True)  # trigger new read on different register
      else:
        print(f'Setting52: Setting {value:#x} is not handled by me yet.')
        if self.last_value == value and not self.controller.needs_reset52.locked():
          # Avoid getting stuck! Problem:
          # - needs_reset52 is not settled and defaults to False
          # - value is repeating (and not 0)
          # - we don’t have a Setting*() for this value (which drives determination)
          # → either drive determination or reset52() to jump dead point
          self._reset52()
      if self.controller.needs_reset52.val():  # need to advance manually
        self._reset52()
    self.last_value = value

  def priority(self):
    # (self.writings_left, not self.confirmed, self.read_prepared(), self.interaction_index())
    # less important than writing, less than unconfirmed reading, ...vcp...,
    #  ...but more than other confirmed!
    # so I’m like reading, confirmed, read_prepared(), self.max_interaction_index()+1
    return (0, not True, self.read_prepared(), self.max_interaction_index()+1)

class Setting(BaseSetting):
  writing_cycles = 2  # how often we write to hw before checking

  def reread(self, *, from52=False):
    '''Clear any write attempts and trigger read from hardware.
    Do remember old value for future reference, though.'''
    self.before_52_fresh = getattr(self, 'current_value', None) if from52 else None
    self.current_value = None  # suspected or confirmed value in monitor
    self.new_value = None  # value to be sent to monitor
    self.confirmed = False  # current_value is really in hardware
    self.writings_left = 0  # write several times, before even checking

  def __init__(self, controller, register):
    super().__init__(controller, register)
    self.reread()
    self.max = None  # maximum allowed value according to monitor
    self.listeners = set()  # callbacks for changes in current_value
    self.max_listeners = set()  # callbacks for max (called at most once)

  def add_listeners(self, callback, max_callback=None):
    for (cb, value, listeners, one_time) in (
      (callback, self.current_value, self.listeners, False),
      (max_callback, self.max, self.max_listeners, True),
        ):
      if cb is not None:
        if value is not None:
          cb(value)
        if not one_time or value is None:
          listeners.add(cb)

  def _set_current_value(self, new_value, /):
    # actually always called after hw read and hw write
    self.before_52_fresh = None
    if self.current_value != new_value:
      self.current_value = new_value
      for cb in self.listeners:
        cb(new_value)

  def _set_max(self, max):
    if self.max is None:
      self.max = max
      while self.max_listeners:
        self.max_listeners.pop()(max)
    elif self.max != max:
      print(f'Max value on {self.register:#x} changed from {self.max} to {max}. Ignoring.')
    assert not self.max_listeners

  def ack_read(self, result):
    '''Set fields according to hardware read real values.
    Part of the interface to hardware handling code.
    Is either used on first initial hardware read for this setting or
    for the confirmation hardware read after several writes.'''
    value, max, *args = result
    if self.new_value is not None and self.new_value != value:  # writings did not succeed
      if self.new_value > max:  # ...and it probably never will succeed
        self.new_value = value
        print(f'Caught write with value beyond max {max}. Leaving it at current value {value}.')
      else:
        self.writings_left = Setting.writing_cycles
        print(f'Control read on {self.register:#x} was {value} instead of {self.new_value}.')
    else:  # writing worked fine (or not coming from writing: reread, initial read)
      assert self.writings_left == 0
    if self.before_52_fresh == value:  # pre-reset value read
      # needs reset or it was manually set to same value
      self.controller.needs_reset52.yes()
      self.current_value = self.before_52_fresh
    self._set_max(max)
    self._set_current_value(value)
    self.confirmed = True

  def ack_write(self, *args):
    '''Update fields in case self.new_value is written to hardware.
    Part of the interface to hardware handling code.'''
    self._set_current_value(self.new_value)
    self.confirmed = False
    self.writings_left = max(self.writings_left-1, 0)

  def select_operation(self):
    if self.writings_left == 0:
      return 'read', (), self.ack_read
    else:
      return 'write', (self.new_value,), self.ack_write

  def _write(self, value):
    '''Set write wish in fields.
    Part of the interface to users of Setting.
    Returns boolean reflecting possible change in priorities (True).'''
    if self.new_value == value:  # same write is already underway
      return False
    elif self.current_value == value:  # returning to value in monitor
      self.writings_left = 0
    else:
      self.writings_left = Setting.writing_cycles
    self.new_value = value
    return True

  def priority(self):
    # 1. prefer writing
    # 1.1. prefer “first” write instead of rewrites
    # 2. reading
    # 2.1. prefer reading values to be confirmed, not already confirmed
    # 2.2. prefer reading which was prepared already (IMPORTANT; avoids back-and-forth w/ 2 tasks)
    # 3. prefer least recently interacted register (might endless ping-pong reads without 2.2.)
    return (self.writings_left, not self.confirmed, self.read_prepared(),
      self.interaction_index())

class SettingsDict(dict):
  def __init__(self, controller):
    super().__init__()
    self._controller = controller
  def __missing__(self, key):
    self[key] = Setting(self._controller, key)
    return self[key]

class Needs_reset52:
  '''Starts as a fluent False. Will reach definitive state with yes()/no(). While fluent, a no()
  locks it to False, and [max] yes() will lock it to True.'''
  def __init__(self, max, /):
    self._x = 0
    self._max = max

  def locked(self):
    return True if self._x in (-1, self._max) else False

  def no(self):
    if not self.locked():
      print('monitor needs_reset52: no')
      self._x = -1

  def yes(self):
    if not self.locked():
      if self._x == self._max - 1: print('monitor needs_reset52: yes')
      self._x = min(self._max, self._x+1)

  def val(self):
    return False if self._x < self._max else True

class MonitorController:
  def __init__(self, edid_device, nursery):
    self.edid_device = edid_device
    self.open_config = functools.partial(xdg.open_config,
        f'd2see/{edid_device.edid_id}')
    self._mccs = Mccs(file_name=edid_device.file_name, open_config = self.open_config)
    self.operations = dict(read=self._mccs.read_nowait, write=self._mccs.write_nowait)
    self._settings = SettingsDict(self)
    self._settings[0x52] = Setting52(self)
    self._settings[Setting2.register] = Setting2()
    self._prio_changed = trio.Event()  # or possibly changed
    self._interaction_log = {}
    self.needs_reset52 = Needs_reset52(4)
    nursery.start_soon(self._handle_tasks)

  def _interacted(self, setting):
    self._interaction_log.pop(setting.register, None)
    self._interaction_log[setting.register] = setting

  @staticmethod
  def coldplug(nursery):
    edid_datas = set()
    mcs = []
    for dev_name in glob.glob('/dev/i2c-*'):
      try:
        edid_device = EdidDevice(dev_name)
      except IOError:
        continue
      else:
        mcs.append(MonitorController(edid_device=edid_device, nursery=nursery))
        if edid_device.edid256 in edid_datas:
          print('Monitors with the same EDID found. ' \
                'This will probably mess things up.')
        else:
          edid_datas.add(edid_device.edid256)
    return mcs

  async def _next_task(self, sleep):
    # a setting dual functions as a task as well
    '''Return highest priority task. There is always one: the idle task for polling settings.
    Do minimum_sleep unconditionally first, bc it may be interrupted which requires checking
    for new highest prio task.'''
    with trio.move_on_after(sleep):
      await self._prio_changed.wait()
    return max(self._settings.values(), key=lambda item: item.priority())

  def setting(self, reg):
    return self._settings.get(reg, None)

  def add_listeners(self, register, *args, **kwargs):
    return self._settings[register].add_listeners(*args, **kwargs)

  def write(self, register, value):
    if self._settings[register]._write(value):
      self._prio_changed.set()
      self._prio_changed = trio.Event()

  async def _handle_tasks(self):
    await self._mccs.optimize_delays()
    sleep = 0
    while True:
      task = await self._next_task(sleep)
      sleep = 0
      operation, op_args, ack_func = task.select_operation()
      if operation == 'wait':
        sleep = op_args
        continue
      try:
        result = self.operations[operation](task.register, *op_args)
      except WouldBlockTime as e:
        sleep = e.wait_time
      except IOError:
        # traceback.print_exc()
        print(f'IOError on {operation} in handle_tasks(). Keeping operation in schedule.')
      else:
        ack_func(result)
        self._interacted(task)


class TimingTest:
  def __init__(self, monitor):
    self.monitor = monitor

  async def safe_check(self):
    m = self.monitor
    with m.safe_delay():
      orig, mx = await m.get_brightness_both()
      v = 1 if orig == 0 else orig - 1
      await m.set_brightness(v)
      assert await m.get_brightness() == v
      await m.set_brightness(orig)
      assert await m.get_brightness() == orig
      return orig, mx

  def _tokens_repeat(self, failure_rate, tokens=1):
    return tokens, round(tokens / failure_rate)

  async def _test_read(self, failure_rate, mx, r, w):
    m = self.monitor
    tokens, repeat = self._tokens_repeat(failure_rate)
    with m.set_delay(r, w):
      for i in range(repeat):
        v = random.randint(0, mx)
        await m.set_brightness(v)
        try:
          if await m.get_brightness() != v:
            if not tokens:
              return False
            else:
              tokens -= 1
        except OSError:
          return False
    return True

  async def _test_write(self, failure_rate, mx, r, w):
    m = self.monitor
    tokens, repeat = self._tokens_repeat(failure_rate)
    for i in range(repeat):
      burst = random.randint(3, 8)
      with m.set_delay(r, w):
        for j in range(burst):
          v = random.randint(0, mx)
          await m.set_brightness(v)
      with m.safe_delay():
        if await m.get_brightness() != v:
          if not tokens:
            return False
          else:
            tokens -= 1
    return True

  async def _test(self, what, failure_rate, r, w):
    orig, mx = await self.safe_check()
    m = self.monitor
    start = time.time()
    testfunc = self._test_read if what == 'read' else self._test_write
    result = await testfunc(failure_rate, mx, r, w)
    print(f'{"SUCC" if result else "FAIL"} {what[0]} delay ({r}, {w}) took {time.time() - start} seconds')
    return result

  async def determine_delays(self):
    r = 1.5 * await self.binary_search(0, .2, lambda r: self._test('read', .1, r, .2))
    w = 1.5 * await self.binary_search(0, .2, lambda w: self._test('write', .1, r, w))
    r = 1.2 * await self.binary_search(0, r, lambda r: self._test('read', .1, r, w))
    w = 1.2 * await self.binary_search(0, w, lambda w: self._test('write', .1, r, w))
    # assert await self._test('write', .1, r, w)
    # assert await self._test('read', .1, r, w)
    return (r, w)

  @staticmethod
  async def binary_search(a, b, function):
    good = b
    bad = a
    for i in range(5):
      test_point = bad + (good - bad) / 2
      result = await function(test_point)
      if result:
        good = test_point
      else:
        bad = test_point
    return good