import argparse
import ConfigParser
import logging
import os
import sys
import time

import data_capture
import equipment
import experiment
import templogger
import util

def main():
    # Get start time
    start_time_str = time.strftime('%Y%m%d_%H%M%S')


    # Parse command line arguments
    parse = argparse.ArgumentParser(description='Experiment System')

    parse.add_argument('experiment', help='Experiment class to run')
    parse.add_argument('capture', help='DataCapture class to run')
    parse.add_argument('config', help='Configuration file(s)', nargs='+')

    parse.add_argument('-v', help='Verbose output', dest='verbose', action='store_true')
    parse.add_argument('--dry-run', help='Run without regulating experiment conditions', dest='dry_run', action='store_true')
    parse.add_argument('--lock', help='Lock the front panels of test equipment', dest='lock', action='store_true')
    parse.add_argument('--visa', help='Display VISA traffic in console', dest='visa', action='store_true')
    parse.set_defaults(verbose=False)
    parse.set_defaults(notemp=False)
    parse.set_defaults(lock=False)
    parse.set_defaults(visa=False)

    args = parse.parse_args()


    # Read configuration file(s)
    cfg = ConfigParser.RawConfigParser()
    cfg.read(args.config)


    # Check paths
    log_dir = cfg.get('path', 'log')

    if not os.path.isdir(log_dir):
        raise IOError('Log path is not a directory')

    if not os.access(log_dir, os.W_OK):
        raise IOError('Log path is not writable')

    log_file_path = os.path.join(os.path.realpath(log_dir), 'log_%s.txt' % (start_time_str))

    result_dir = cfg.get('path', 'result')

    if not os.path.isdir(result_dir):
        raise IOError('Result path is not a directory')

    if not os.access(result_dir, os.W_OK):
        raise IOError('Result path is not writable')

    result_dir = os.path.realpath(os.path.join(result_dir, "experiment_{}".format(start_time_str)))
    os.mkdir(result_dir)


    # Setup logging
    log_handle_console = logging.StreamHandler()
    log_handle_console.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    log_format_console = logging.Formatter(fmt='%(asctime)s [%(levelname)-5s] %(name)s: %(message)s', datefmt='%H:%M:%S')
    log_handle_console.setFormatter(log_format_console)

    log_handle_file = logging.FileHandler(log_file_path)
    log_handle_file.setLevel(logging.DEBUG)
    log_format_file = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%Y%m%d %H:%M:%S')
    log_handle_file.setFormatter(log_format_file)

    # Get all loggers needed
    root_logger = logging.getLogger(__name__)
    data_logger = logging.getLogger(data_capture.__name__)
    equipment_logger = logging.getLogger(equipment.__name__)
    experiment_logger = logging.getLogger(experiment.__name__)
    temperature_logger = logging.getLogger(templogger.__name__)

    # Set defaults
    for logger in [root_logger, data_logger, equipment_logger, experiment_logger, temperature_logger]:
        logger.handlers = []
        logger.setLevel(logging.DEBUG)
        logger.addHandler(log_handle_console)
        logger.addHandler(log_handle_file)

    if not args.visa:
        equipment_logger.removeHandler(log_handle_console)
        temperature_logger.removeHandler(log_handle_console)

    root_logger.info("jtfadump | hash: {}".format(util.get_git_hash()))
    root_logger.info("Started: {}".format(time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime())))
    root_logger.info("Logging path: {}".format(log_file_path))
    root_logger.info("Result directory: {}".format(result_dir))


    # Dump configuration to log
    root_logger.debug("--- BEGIN CONFIGURATION LISTING ---")

    for section in cfg.sections():
        root_logger.debug("[{}]".format(section))

        for item in cfg.items(section):
            root_logger.debug("{}: {}".format(item[0], item[1]))

    root_logger.debug("--- END CONFIGURATION LISTING ---")


    # Setup experiment
    try:
        root_logger.info("Loading experiment: {}".format(args.experiment))
        experiment_class = util.class_from_str("experiment.{}".format(args.experiment), __name__)
        run_exp = experiment_class(args, cfg, result_dir)
    except:
        root_logger.exception('Exception while loading experiment class', exc_info=True)
        return

    # Setup data capture
    try:
        root_logger.info("Loading data capture: {}".format(args.capture))
        data_capture_class = util.class_from_str("data_capture.{}".format(args.capture), __name__)
        run_data_capture = data_capture_class(args, cfg, result_dir)
    except:
        logging.exception('Exception while loading data capture class', exc_info=True)
        run_exp.stop()
        return

    # Make sure log file is written before beginning
    log_handle_file.flush()


    # Run the experiment
    loop = 0

    try:
        while run_exp.is_running():
            capture_id = util.rand_hex_str()
            root_logger.info("Experiment step {}: {}".format(loop, capture_id))

            run_exp.step()
            
            experiment_state = run_exp.get_state()
            experiment_state['capture_id'] = capture_id
            
            run_data_capture.save(loop, capture_id, experiment_state)

            loop += 1
    except:
        root_logger.exception('Error while running experiment', exc_info=True)
    finally:
        run_exp.stop()

    root_logger.info('Experiment stopped')


if __name__ == "__main__":
    main()
