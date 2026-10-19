import struct
from .model import Quote

BODY = struct.Struct('<2sBBIIH')
PACKET_SIZE = 16


def crc16(data):
    crc = 0xffff
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
    return crc


def encode(quote):
    body = BODY.pack(b'NQ', 1, int(quote.kill), quote.sequence, quote.price, quote.quantity)
    return body + struct.pack('<H', crc16(body))


def decode(packet):
    if len(packet) != PACKET_SIZE:
        raise ValueError('packet length')
    body = packet[:-2]
    magic, version, flags, sequence, price, quantity = BODY.unpack(body)
    if magic != b'NQ' or version != 1 or flags & ~1:
        raise ValueError('packet header')
    if crc16(body) != struct.unpack('<H', packet[-2:])[0]:
        raise ValueError('packet CRC')
    return Quote(sequence, price, quantity, bool(flags))
