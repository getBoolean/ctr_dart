"""Press 3DS buttons through Luma3DS Rosalina InputRedirection (UDP 4950).

Usage: press.py <ip> <button> [<button> ...]   (each pressed then released)
Packet: 5 little-endian u32s: pad (0xfff XOR pressed bits), touch, circle pad,
c-stick/ZL/ZR, interface buttons (HOME=1, POWER=2).
"""
import socket
import struct
import sys
import time

BITS = {'A': 0, 'B': 1, 'SELECT': 2, 'START': 3, 'RIGHT': 4, 'LEFT': 5,
        'UP': 6, 'DOWN': 7, 'R': 8, 'L': 9, 'X': 10, 'Y': 11}
IDLE_TOUCH, IDLE_CIRCLE, IDLE_CPP = 0x2000000, 0x7FF7FF, 0x80800081


def packet(pad_pressed=0, interface=0):
    return struct.pack('<5I', 0xFFF ^ pad_pressed, IDLE_TOUCH, IDLE_CIRCLE,
                       IDLE_CPP, interface)


def main():
    ip, buttons = sys.argv[1], [b.upper() for b in sys.argv[2:]]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (ip, 4950)
    for button in buttons:
        if button == 'HOME':
            down = packet(interface=1)
        else:
            down = packet(1 << BITS[button])
        # Hold for ~150 ms (several packets, UDP may drop one), then release.
        for _ in range(6):
            sock.sendto(down, target)
            time.sleep(0.025)
        for _ in range(4):
            sock.sendto(packet(), target)
            time.sleep(0.025)
        print(f'pressed {button}')
        time.sleep(0.6)


if __name__ == '__main__':
    main()
