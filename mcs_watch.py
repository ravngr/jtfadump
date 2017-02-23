import argparse
from datetime import datetime
import json
import logging
import logging.config
import os.path
import serial
import sys
import time
import traceback

import matplotlib.pyplot as plt

import pushover

import util


__version__ = '1.1.0'

_DEFAULT_CONFIG_FILE = 'mcs_watch_config.json'

_app_cfg = {}


def main():
    app_path = os.path.dirname(os.path.realpath(__file__))

    try:
        app_git_hash = util.get_git_hash()
    except OSError:
        app_git_hash = 'not found'

    parse = argparse.ArgumentParser(description='Tool to monitor MCS output')

    parse.add_argument('-c', '--config', help='Path to config file', dest='config_path',
                       default=os.path.join(app_path, _DEFAULT_CONFIG_FILE))
                       
    args = parse.parse_args()
    
    # Read configuration
    with open(args.config_path, 'r') as f:
        config_dict = json.load(f)
        logging_dict = config_dict.pop('log')

        _app_cfg.update(config_dict)
        logging.config.dictConfig(logging_dict)

    # Setup logging
    root_logger = logging.getLogger('main')
    
    root_logger.info("mcs_watch {} | git: {}".format(__version__, app_git_hash))
    root_logger.info("Launch command: {}".format(' '.join(sys.argv)))
    
    # Pushover (if enabled)
    notify = None
    
    if 'pushover' in _app_cfg:
        root_logger.info('Pushover enabled')
        notify = pushover.Client(user_key=_app_cfg['pushover']['user_key'],
                                 api_token=_app_cfg['pushover']['api_key'])
        
    # Open serial port
    port = serial.Serial(_app_cfg['serial']['port'], _app_cfg['serial']['speed'],
                         timeout=_app_cfg['serial']['timeout'])

    while True:
        root_logger.info('Wait for initial packet...')

        # Wait for end of packet before reading full packets
        while port.read() != '\n':
            pass

        if notify is not None:
            notify.send_message('Experiment start', title='mcs_watch')

        root_logger.info('Packed received!')

        log_name = os.path.abspath(os.path.join(_app_cfg['output']['path'], "{}_{}.{}".format(
                _app_cfg['output']['prefix'], time.strftime('%Y%m%d%H%M%S'), _app_cfg['output']['extension'])))

        line_buffer = ''
        tick_counter = 0

        root_logger.info("Writing to file: {}".format(log_name))

        gas_flag = 0

        # Setup plot if enabled
        plot_enable = _app_cfg['output']['plot']

        fig = None
        ax = None
        line = [None, None, None]

        plot_x = []
        plot_y_flow = []
        plot_y_relay = []
        plot_y_temp = []

        if plot_enable:
            fig, ax = plt.subplots(3, 1, sharex=True)

            ax[0].set_title('MCS')
            ax[0].set_ylabel('Relay State')
            ax[1].set_ylabel('Gas Flow')
            ax[2].set_ylabel('Temperature')
            ax[2].set_xlabel('Minutes')

            plt.show(block=False)

        with open(log_name, 'w') as f:
            try:
                while True:
                    # Read byte
                    c = port.read()

                    # root_logger.debug('RX: {}'.format(c))

                    # Check for end of line
                    if len(c) > 0:
                        # Received byte, reset counter
                        tick_counter = 0

                        if c == '\n' or c == '\r':
                            if len(line_buffer) > 0:
                                # Process line
                                root_logger.info("Packet: {}".format(line_buffer))

                                mks_fields = line_buffer.split(_app_cfg['serial']['mcs_delim'])

                                # Validate number of fields
                                if len(mks_fields) != _app_cfg['serial']['mcs_fields']:
                                    root_logger.warn("WARNING: Expected {} fields but got {}!".format(
                                            _app_cfg['serial']['mcs_fields'], len(mks_fields)))
                                elif any([len(x) == 0 for x in mks_fields]):
                                    root_logger.warn('WARNING: Empty field in mcs data!')
                                else:
                                    # Calculate clock offset
                                    try:
                                        mcs_time = datetime.strptime(mks_fields[0],
                                                                     _app_cfg['serial']['mcs_time_format'])
                                        now_time = datetime.now()

                                        root_logger.info("Clock offset: {:3f}".format(
                                            (now_time - mcs_time).total_seconds()))

                                        # Overwrite the time with system time
                                        mks_fields[0] = time.strftime(_app_cfg['serial']['mcs_time_format'])

                                        # Extract data
                                        adam_temp = [float(x) if x != '-' else 0.0 for x in mks_fields[18:25]]
                                        gas_flow = [float(x) if x != '-' else 0.0 for x in mks_fields[5:13]]
                                        relay_logic = [int(x) == 1 for x in mks_fields[2] if x in ('0', '1')]

                                        if abs(_app_cfg['gas']['ideal'] - sum(gas_flow)) >= \
                                                _app_cfg['gas']['threshold']:
                                            gas_flag += 1

                                            if gas_flag == _app_cfg['gas']['count']:
                                                msg = "Gas flow below threshold {:.1f} < {:.1f}".format(
                                                    sum(gas_flow), _app_cfg['gas']['threshold'])
                                                root_logger.warning(msg)

                                                if notify is not None:
                                                    notify.send_message(msg, title='mcs_watch')
                                        else:
                                            if gas_flag >= _app_cfg['gas']['count']:
                                                msg = "Gas flow restored {:.1f} >= {:.1f}".format(
                                                    sum(gas_flow), _app_cfg['gas']['threshold'])
                                                root_logger.warning(msg)

                                                if notify is not None:
                                                    notify.send_message(msg, title='mcs_watch')

                                            gas_flag = 0

                                        # Log line to file
                                        f.write(_app_cfg['serial']['mcs_delim'].join(mks_fields) + '\n')
                                        f.flush()

                                        # Do other stuff
                                        if plot_enable:
                                            plot_x.append(time.time())
                                            plot_y_relay.append([x + 0.8 * y for x, y in enumerate(relay_logic)])
                                            plot_y_flow.append(gas_flow)
                                            plot_y_temp.append(adam_temp)

                                            data_x = [plot_x[-1] - x for x in plot_x]

                                            if line[0] is None:
                                                line[0] = ax[0].plot(data_x, plot_y_relay)
                                                line[1] = ax[1].plot(data_x, plot_y_flow)
                                                line[2] = ax[2].plot(data_x, plot_y_temp)
                                            else:
                                                for n, l in enumerate(line[0]):
                                                    l.set_xdata(data_x)
                                                    l.set_ydata([x[n] for x in plot_y_relay])

                                                for n, l in enumerate(line[1]):
                                                    l.set_xdata(data_x)
                                                    l.set_ydata([x[n] for x in plot_y_flow])

                                                for n, l in enumerate(line[2]):
                                                    l.set_xdata(data_x)
                                                    l.set_ydata([x[n] for x in plot_y_temp])

                                                ax[0].set_xlim(min(data_x), max(data_x))
                                                ax[0].set_ylim(-1, 8)

                                            plt.pause(0.01)
                                    except:
                                        root_logger.exception('Unhandled exception during line read', exc_info=True)

                                # Clear buffer for next line
                                line_buffer = ''
                        else:
                            line_buffer += c
                    else:
                        # Time out occurred
                        tick_counter += 1

                        if tick_counter >= _app_cfg['serial']['timeout_rx']:
                            root_logger.warn('Timeout occured!')
                            break
            except KeyboardInterrupt:
                root_logger.warn('Keyboard interrupt')
                break
            except:
                root_logger.exception('Unhandled exception', exc_info=True)

                if notify is not None:
                    notify.send_message("Exception during monitoring! Traceback: {}".format(traceback.format_exc()),
                                        title='mcs_watch')

                raise
            finally:
                port.close()

            if notify is not None:
                notify.send_message('Experiment end', title='mcs_watch')
        
    root_logger.info('Exiting')


if __name__ == '__main__':
    main()
