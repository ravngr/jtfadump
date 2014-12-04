import serial
import struct


class TemperatureLogger:
    def __init__(self, port):
        self._port = serial.Serial(port, 9600, timeout=1)

    def get_temperture(self, channel = 0):
        self._port.write('A')
        self._port.flush()
        # Logger return exactly 45 chars
        r = self._port.read(45)
        return (struct.unpack('>h', r[7+channel:9+channel])[0]) / 10.0
