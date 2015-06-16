# -- coding: utf-8 --

import logging
import serial
import struct


class TemperatureLogger:
    _PAYLOAD_REQUEST = 'A'
    _PAYLOAD_SIZE = 45
    _PAYLOAD_DATA_OFFSET_LOW = 7
    _PAYLOAD_DATA_OFFSET_HIGH = 9

    def __init__(self, port):
        # Open serial port
        self._port = serial.Serial(port, 9600, timeout=1)

        self._logger = logging.getLogger(__name__)

    def get_temperature(self, channel=0):
        # Logger returns data when prompted with 'A' character
        self._port.write(self._PAYLOAD_REQUEST)
        self._port.flush()

        r = self._port.read(self._PAYLOAD_SIZE)
        # Unpack data into platform appropriate format
        t = (struct.unpack('>h', r[self._PAYLOAD_DATA_OFFSET_LOW+channel:self._PAYLOAD_DATA_OFFSET_HIGH+channel])[0]) / 10.0

        self._logger.debug(u"{} READ ch{}: {}°C".format(self._port.name, channel, t))

        return t
