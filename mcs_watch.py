from __future__ import print_function

import os.path
import serial
import time


_FILE_PATH = '.'
_FILE_PREFIX = 'mcs'
_FILE_EXTENSION = 'log'

_SERIAL_SPEED = 115200
_SERIAL_TIMEOUT = 1

_MKS_FIELDS = 30
_MKS_EOL = '\n'
_MKS_DELIMITER = '\t'


def main():
    port = serial.Serial(self._port_name, _SERIAL_SPEED, timeout=_SERIAL_TIMEOUT)

    print('Waiting for initial packet... ', end='')

    # Wait for end of packet before reading full packets
    while port.read() != '\n':
        pass

    print('OK!')

    log_name = os.path.abspath(os.path.join((_FILE_PATH, "{}_{}.{}".format(_FILE_PREFIX, time.strftime('%Y%m%d%H%M%S'),
                                                                           _FILE_EXTENSION))))
    
    line_buffer = ''

    print("Logging to file: {}".format(log_name))

    with open(log_name, 'w') as f:
        try:
            while True:
                # Read byte
                c = port.read()

                # Check for end of line
                if len(c) > 0:
                    if c == _MKS_EOL:
                        # Process line
                        print("Packet: {}".format(line_buffer))

                        mks_fields = line_buffer.split(_MKS_DELIMITER)

                        # Validate number of fields
                        if len(mks_fields) != _MKS_FIELDS:
                            print("ERROR: Expected {} fields but got {}!".format(_MKS_FIELDS, len(mks_fields)))
                            continue

                        # Overwrite the time with system time
                        mks_fields[0] = time.strftime('%d/%m/%Y %H:%M:%S')

                        # Log line to file
                        f.write(_MKS_DELIMITER.join(mks_fields) + '\r\n')

                        # Clear buffer for next line
                        line_buffer = ''
                    else:
                        line_buffer += c
        except KeyboardInterrupt:
            print('Exiting...')
        finally:
            port.close()


if __name__ == '__main__':
    main()
