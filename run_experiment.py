import argparse
import ConfigParser
import logging
import os
import sys
import time

import equipment
import experiment
import util

def main():
    # Get start time
    start_time_str = time.strftime('%Y%m%d_%H%M%S')


    # Parse command line arguments
    parse = argparse.ArgumentParser(description='Experiment System')

    parse.add_argument('experiment', help='Experiment class to run')
    parse.add_argument('config', help='Configuration file(s)', nargs='+')

    parse.add_argument('-v', help='Verbose output', dest='verbose', action='store_true')
    parse.add_argument('--dry-run', help='Run without regulating experiment conditions', dest='dry_run', action='store_true')
    parse.add_argument('--lock', help='Lock the front panels of test equipment', dest='lock', action='store_true')
    parse.set_defaults(verbose=False)
    parse.set_defaults(notemp=False)
    parse.set_defaults(lock=False)

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

    result_dir = os.path.realpath(result_dir)


    # Setup logging
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger('')
    log.handlers = []

    log_handle_file = logging.FileHandler(log_file_path)
    log_handle_file.setLevel(logging.INFO)
    log_format_file = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%Y%m%d %H:%M:%S')
    log_handle_file.setFormatter(log_format_file)
    log.addHandler(log_handle_file)

    log_handle_console = logging.StreamHandler()
    log_handle_console.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    log_format_console = logging.Formatter(fmt='%(asctime)s [%(levelname)-5s] %(name)s: %(message)s', datefmt='%H:%M:%S')
    log_handle_console.setFormatter(log_format_console)
    log.addHandler(log_handle_console)

    logging.info("jtfadump | hash: {}".format(util.get_git_hash()))
    logging.info("Logging path: {}".format(log_file_path))
    logging.info("Result directory: {}".format(result_dir))


    # Setup experiment
    try:
        logging.info("Loading experiment {}".format(args.experiment))
        experiment_class = util.class_from_str("experiment.{}".format(args.experiment), __name__)
        run_exp = experiment_class(args, cfg, result_dir)
    except:
        logging.exception('Error while attempting to set up experiment')
        return



    # Run the experiment
    try:
        run_exp.run()
    except:
        logging.exception('Error while running experiment')
    finally:
        run_exp.stop()

    logging.info('Experiment stopped')


if __name__ == "__main__":
    main()
