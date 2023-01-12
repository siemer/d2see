import binascii
import logging
import sys
import time

from ddcci.ddcci import Mccs as M, Ddcci as D, I2cDev as I

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, style='{',
    format='{relativeCreated:5.0f} {msg}')
d = log.debug

i = I('/dev/i2c-6', 0x37)

def measure(amount):
    start = time.time()
    i.read(amount)
    return time.time() - start

t1 = measure(1)
t2 = measure(100)

n = (t2 - t1) / (100 - 1)
m = t1 - n

print(f'n = {n}, m = {m}')

o = M.Op

def msg(*args):
    return D.ddc2i2c(M.mccs2ddc(*args))

brightness = msg(o.READ, 0x10)
contrast = msg(o.READ, 0x12)
button = msg(o.READ, 0x52)
reset52 = msg(o.WRITE, 0x2, 0x1)
capas = msg(o.CAPABILITIES, 0)
# i.write(D.ddc2i2c(M.mccs2ddc(0x10)))
#i.write(D.ddc2i2c(M.mccs2ddc(0x2, 0x1)))
#time.sleep(.1)
i.write(contrast)
print(binascii.hexlify(i.read(30), sep=' '))
i.write(contrast)
for _ in range(8):
    print(binascii.hexlify(i.read(4), sep=' '))

sys.exit()

old_time = time.time()
for m in 3 * (capas, button, brightness, contrast, reset52):
    new_time = time.time()
    print('time-diff', new_time-old_time)
    old_time = new_time
    b = i.read(100)
    index = next((i for i, val in enumerate(b) if val), None)
    if index is not None:
        print(index, binascii.hexlify(b[index:index+40], sep=' '))
        ind = []
        pos = -1
        while True:
            pos = b.find(b[index:index+8], pos+1)
            if pos == -1:
                break
            else:
                ind.append(pos)
        print(ind)
    i.write(m)
