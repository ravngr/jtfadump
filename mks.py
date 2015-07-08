# -- coding: utf-8 --

import re
import logging
import serial
import time
import threading


class MKSField:
    _RELAY_BITS = 4
    _RELAY_SEGMENTS = 2
    _RELAY_OUTPUTS = _RELAY_BITS * _RELAY_SEGMENTS
    _RELAY_REGEX = re.compile('^' + '-'.join(["([0-1]{{{}}})".format(_RELAY_BITS)] * _RELAY_SEGMENTS) + '$')

    _TIME_FORMAT = '%d/%m/%Y %H:%M:%S'
    # _TIME_REGEX = re.compile('^\d{1,2}/\d{1,2}/\d{2,4} \d{2}:\d{2}:\d{2}$')

    DATA_TYPE_STRING = 0
    DATA_TYPE_INT = 1
    DATA_TYPE_FLOAT = 2
    DATA_TYPE_RELAY = 3
    DATA_TYPE_TIME = 4

    def __init__(self, name, length, valid_length=None, data_type=DATA_TYPE_STRING, save=True):
        self.name = name

        if data_type is self.DATA_TYPE_TIME:
            # Force length to be 1 if type is a time string
            self.length = 1
            self.valid_length = 1
        else:
            self.length = length
            self.valid_length = length if valid_length is None else valid_length

        self.data_type = data_type
        self.save = save

    def get_default(self):
        if self.data_type is self.DATA_TYPE_STRING:
            return [''] * self.valid_length
        elif self.data_type is self.DATA_TYPE_INT:
            return [0] * self.valid_length
        elif self.data_type is self.DATA_TYPE_FLOAT:
            return [0.0] * self.valid_length
        elif self.data_type is self.DATA_TYPE_RELAY:
            return [False] * self.valid_length * self._RELAY_OUTPUTS
        elif self.data_type is self.DATA_TYPE_TIME:
            return 0
        else:
            raise NotImplementedError()

    def validate(self, data_fields):
        if len(data_fields) is not self.valid_length:
            return False

        # Only validate fields that are accepted
        for data in data_fields[:self.valid_length]:
            if data in ['NA', 'n/a', '-']:
                # Unpopulated field
                return False
            elif self.data_type is self.DATA_TYPE_STRING:
                # Strings are always valid
                continue
            elif self.data_type is self.DATA_TYPE_INT:
                try:
                    int(data)
                    continue
                except ValueError:
                    return False
            elif self.data_type is self.DATA_TYPE_FLOAT:
                try:
                    float(data)
                    continue
                except ValueError:
                    return False
            elif self.data_type is self.DATA_TYPE_RELAY:
                if self._RELAY_REGEX.match(data):
                    continue
                else:
                    return False
            elif self.data_type is self.DATA_TYPE_TIME:
                try:
                    time.strptime(data, self._TIME_FORMAT)
                    continue
                except ValueError:
                    return False
            else:
                raise NotImplementedError()

        return True

    def convert(self, data_fields):
        if self.data_type is self.DATA_TYPE_STRING:
            return data_fields
        elif self.data_type is self.DATA_TYPE_INT:
            return [int(x) for x in data_fields]
        elif self.data_type is self.DATA_TYPE_FLOAT:
            return [float(x) for x in data_fields]
        elif self.data_type is self.DATA_TYPE_RELAY:
            relay_state = []

            for data in data_fields:
                relay_group = self._RELAY_REGEX.match(data)

                for relay_seg in relay_group.groups():
                    for bit in relay_seg:
                        relay_state.append(bit is '1')

            # Reverse fields since we read left to right
            return relay_state[::-1]
        elif self.data_type is self.DATA_TYPE_TIME:
            return time.mktime(time.strptime(data_fields[0], self._TIME_FORMAT))
        else:
            raise NotImplementedError()


class MKSException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class MKSSerialMonitor:
    _SERIAL_SPEED = 115200
    _SERIAL_TIMEOUT = 1

    # Mapping of delimited data to export fields
    _MKS_FIELD_PREFIX = 'mks_'
    _MKS_FIELD_MAPPING = [
        MKSField('controller_time', 1, data_type=MKSField.DATA_TYPE_TIME),
        MKSField('loop_time', 1, data_type=MKSField.DATA_TYPE_INT),
        MKSField('relay', 1, data_type=MKSField.DATA_TYPE_RELAY),
        MKSField('power_supply', 1, save=False),
        MKSField('flow', 8, valid_length=2, data_type=MKSField.DATA_TYPE_FLOAT),
        MKSField('vgen_relative_value', 1, data_type=MKSField.DATA_TYPE_FLOAT),
        MKSField('vgen_temperature', 1, data_type=MKSField.DATA_TYPE_FLOAT),
        MKSField('pressure', 1, save=False),
        MKSField('jcs', 3, save=False),
        MKSField('dynacal_temperature', 1, data_type=MKSField.DATA_TYPE_FLOAT, save=False),
        MKSField('adam', 8, data_type=MKSField.DATA_TYPE_FLOAT, save=False)
    ]

    _MKS_FIELD_LENGTH = sum([x.length for x in _MKS_FIELD_MAPPING])

    _MKS_EOL = '\n'
    _MKS_DELIMITER = '\t'

    def __init__(self, port):
        self._port_name = port
        self._logger = logging.getLogger(__name__)
        
        self._logger.debug('Setting up receiver for MKS system')

        # Generate export fields with default values
        self._export_fields = {
            x.name: x.get_default() for x in self._MKS_FIELD_MAPPING if x.save
        }

        # Append initial time information
        self._export_fields.update({
            self._MKS_FIELD_PREFIX + 'time': time.strftime('%a, %d %b %Y %H:%M:%S +0000', 0),
            self._MKS_FIELD_PREFIX + 'timestamp': 0
        })

        # Start receiver thread
        self._update = threading.Event()
        self._working = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()

        self._thread = threading.Thread(target=self._receive)
        self._thread.daemon = True

        self._thread.start()

    def stop(self, wait=False):
        self._stop.set()

        if wait:
            self._thread.join()

    def is_running(self):
        return not self._stop.is_set()

    def is_working(self):
        return self._working.is_set()

    def update_wait(self, timeout=None):
        self._update.clear()
        return self._update.wait(timeout)

    def get_state(self):
        with self._lock:
            r = self._export_fields

        return r

    def get_lag(self):
        with self._lock:
            lag = time.time() - self._export_fields[self._MKS_FIELD_PREFIX + 'timestamp']

        return lag

    @staticmethod
    def process_mks_line(line):
        valid_fields = {}

        # Split line into fields
        line_fields = line.split(MKSSerialMonitor._MKS_DELIMITER)

        if len(line_fields) is not MKSSerialMonitor._MKS_FIELD_LENGTH:
            raise MKSException("Expected {} fields but got {}".format(MKSSerialMonitor._MKS_FIELD_LENGTH,
                                                                      len(line_fields)))

        for field_n in range(0, len(MKSSerialMonitor._MKS_FIELD_MAPPING)):
            # Get field
            mks_field = MKSSerialMonitor._MKS_FIELD_MAPPING[field_n]

            if not mks_field.save:
                # Skip unsaved fields
                continue

            # Calculate data offset
            field_offset_start = sum([x.length for x in MKSSerialMonitor._MKS_FIELD_MAPPING[0:field_n]])
            field_offset_end = field_offset_start + mks_field.valid_length

            # Get field(s)
            field_data = line_fields[field_offset_start:field_offset_end]

            # Validate data in field(s)
            if not mks_field.validate(field_data):
                raise MKSException("Field {} ({} to {}) failed validation, data: [{}]"
                                   .format(mks_field.name, field_offset_start, field_offset_end - 1,
                                           ', '.join(field_data)))

            # Save field data
            valid_fields[MKSSerialMonitor._MKS_FIELD_PREFIX + mks_field.name] = mks_field.convert(field_data)

        return valid_fields

    def _receive(self):
        line_buffer = ''

        try:
            # Open monitor port
            self._port = serial.Serial(self._port_name, self._SERIAL_SPEED, timeout=self._SERIAL_TIMEOUT)

            self._logger.info('Waiting for first MKS packet...')

            # Wait for end of packet before reading full packets
            while self._port.read() != '\n':
                pass

            # Unblock any waiting threads
            self._working.set()

            self._logger.info('MKS packet received!')

            while not self._stop.is_set():
                # Read byte
                c = self._port.read()

                # Check for end of line
                if len(c) > 0:
                    if c == self._MKS_EOL:
                        # Process line
                        self._logger.debug("MKS packet: {}".format(line_buffer))

                        try:
                            export_fields = MKSSerialMonitor.process_mks_line(line_buffer)

                            # Append current time
                            export_fields[self._MKS_FIELD_PREFIX + 'time'] = time.strftime(
                                '%a, %d %b %Y %H:%M:%S +0000', time.gmtime())
                            export_fields[self._MKS_FIELD_PREFIX + 'timestamp'] = time.time()

                            with self._lock:
                                self._export_fields = export_fields
                        except MKSException as e:
                            self._logger.warn(e.msg)

                        # Clear buffer for next line
                        line_buffer = ''

                        # Wake all waiting threads
                        self._update.set()
                    else:
                        line_buffer += c
        except:
            self._stop.set()
            self._working.clear()
            self._logger.exception('Exception occurred in MKS thread', exc_info=True)
            raise
