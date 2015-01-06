# -- coding: utf-8 --

import logging
import serial
import struct


class TemperatureLogger:
    PAYLOAD_REQUEST = 'A'
    PAYLOAD_SIZE = 45
    PAYLOAD_DATA_OFFSET_LOW = 7
    PAYLOAD_DATA_OFFSET_HIGH = 9

    def __init__(self, port):
        # Open serial port
        self._port = serial.Serial(port, 9600, timeout=1)

        self._logger = logging.getLogger(__name__)

    def get_temperature(self, channel=0):
        # Logger returns data when prompted with 'A' character
        self._port.write(self.PAYLOAD_REQUEST)
        self._port.flush()

        r = self._port.read(self.PAYLOAD_SIZE)
        # Unpack data into platform appropriate format
        t = (struct.unpack('>h', r[self.PAYLOAD_DATA_OFFSET_LOW+channel:self.PAYLOAD_DATA_OFFSET_HIGH+channel])[0]) / 10.0

        self._logger.debug(u"{} READ ch{}: {}°C".format(self._port.name, channel, t))

        return t
