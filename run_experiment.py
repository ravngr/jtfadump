import argparse
import ConfigParser
import datetime
import inspect
import logging
import os
import pickle
import sys
import time
import traceback

import pushover
import pyvisa

import data_capture
import equipment
import experiment
import mks
import post_processor
import regulator
import templogger
import util

_LOOP_STATE_FILE = 'loop.pickle'


def main():
    # Get start time
    start_time_str = time.strftime('%Y%m%d_%H%M%S')


    # Get a list of available modules
    module_list = 'Data cpature modules:\n'

    for m in dir(data_capture):
        m = util.class_from_str("data_capture.{}".format(m), __name__)
        if m is not data_capture.DataCapture and inspect.isclass(m) and issubclass(m, data_capture.DataCapture):
            module_list += "\t{}\n".format(str(m).split('.', 1)[-1])

    module_list += '\nExperiment modules:\n'

    for m in dir(experiment):
        m = util.class_from_str("experiment.{}".format(m), __name__)
        if m is not experiment.Experiment and inspect.isclass(m) and issubclass(m, experiment.Experiment):
            module_list += "\t{}\n".format(str(m).split('.', 1)[-1])

    module_list += '\nPost-processor modules:\n'

    for m in dir(post_processor):
        m = util.class_from_str("post_processor.{}".format(m), __name__)
        if m is not post_processor.PostProcessor and inspect.isclass(m) and issubclass(m, post_processor.PostProcessor):
            module_list += "\t{}\n".format(str(m).split('.', 1)[-1])


    # Parse command line arguments
    parse = argparse.ArgumentParser(description='Experiment System', formatter_class=argparse.RawDescriptionHelpFormatter, epilog=module_list)

    parse.add_argument('experiment', help='Experiment class to run')
    parse.add_argument('capture', help='DataCapture class to run')
    parse.add_argument('config', help='Configuration file(s)', nargs='+')

    parse.add_argument('-p', '--post', help='Option data post-processing class', dest='post', action='append')
    parse.add_argument('-v', help='Verbose output', dest='verbose', action='store_true')
    parse.add_argument('--dry-run', help='Run without regulating experiment conditions', dest='dry_run', action='store_true')
    parse.add_argument('--pushover', help='Send notifications using pushover service', dest='notify', action='store_true')
    parse.add_argument('--lock', help='Lock the front panels of test equipment', dest='lock', action='store_true')
    parse.add_argument('--visa', help='Display VISA traffic in console', dest='visa', action='store_true')
    parse.set_defaults(verbose=False)
    parse.set_defaults(notemp=False)
    parse.set_defaults(notify=False)
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
    regulator_logger = logging.getLogger(regulator.__name__)
    temperature_logger = logging.getLogger(templogger.__name__)
    mks_logger = logging.getLogger(mks.__name__)

    # Set defaults
    for logger in [root_logger, data_logger, equipment_logger, experiment_logger, regulator_logger, temperature_logger, mks_logger]:
        logger.handlers = []
        logger.setLevel(logging.DEBUG)
        logger.addHandler(log_handle_console)
        logger.addHandler(log_handle_file)

    if not args.visa:
        equipment_logger.removeHandler(log_handle_console)
        temperature_logger.removeHandler(log_handle_console)

    root_logger.info("jtfadump | hash: {}".format(util.get_git_hash()))
    root_logger.info("python {}".format(sys.version))
    root_logger.info("pyvisa {}".format(pyvisa.__version__))
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
        root_logger.exception('Exception while loading data capture class', exc_info=True)
        run_exp.stop()
        return

    # Add post-processors
    try:
        if args.post is not None:
            for post_class in args.post:
                root_logger.info("Loading post-processor: {}".format(post_class))
                post_processor_class = util.class_from_str("post_processor.{}".format(post_class), __name__)

                if data_capture_class in post_processor_class.get_supported_data_capture():
                    run_post_processor = post_processor_class(run_exp, run_data_capture, cfg)
                    run_data_capture.add_post_processor(run_post_processor)
                else:
                    root_logger.warning("{} does not support data capture {}".format(post_class))
    except:
        root_logger.exception('Exception while loading post processor class', exc_info=True)
        run_exp.stop()
        return

    # Make sure log file is written before beginning
    log_handle_file.flush()

    
    # Setup notification if required
    if args.notify:
        notify = pushover.Client(user_key=cfg.get('pushover', 'user_key'), api_token=cfg.get('pushover', 'api_key'))
        notify.send_message("Experiment: {}\nData capture: {}".format(args.experiment, args.capture), title='jtfadump Started')
    

    # Run the experiment
    try:
        with open(_LOOP_STATE_FILE, 'r') as f:
            run_exp.set_remaining_loops(pickle.load(f))
            root_logger.info("Loaded existing loop counter from file")
    except:
        root_logger.info("No existing state")

    loop = 0
    loop_runtime = []

    try:
        while run_exp.is_running():
            loop_start_time = time.time()

            capture_id = util.rand_hex_str()
            root_logger.info("Experiment step {} ({} remaining): {}".format(loop, run_exp.get_remaining_loops(), capture_id))

            # Update experimental parameters
            run_exp.step()

            # Capture data from experiment
            run_data_capture.save(capture_id, run_exp)
            run_exp.finish_loop()

            # Show time statistics
            loop_time = time.time() - loop_start_time
            loop_runtime.append(loop_time)

            loop_time_avg = sum(loop_runtime) / len(loop_runtime)
            loop_hours, r = divmod(loop_time_avg, 3600)
            loop_mins, loop_secs = divmod(r, 60)

            if run_exp.get_remaining_loops() is not False:
                loop_est_maxtime = loop_time_avg * run_exp.get_remaining_loops()
                loop_est = datetime.datetime.now() + datetime.timedelta(seconds=loop_est_maxtime)

                root_logger.info("Average loop runtime: {}:{}:{}".format(int(loop_hours), int(loop_mins), round(loop_secs, 3)))
                root_logger.info("Estimated completion {:%Y-%m-%d %H:%M:%S}".format(loop_est))

            loop += 1

            with open(_LOOP_STATE_FILE, 'w') as f:
                pickle.dump(run_exp.get_remaining_loops(), f)

        try:
            os.unlink(_LOOP_STATE_FILE)
        except:
            pass

        root_logger.info('Experiment loop exited normally')
        
        if args.notify:
            notify.send_message("Experiment stopped normally after {} loop{}".format(loop, '' if loop == 1 else 's'), title='jtfadump Stopped')
    except (KeyboardInterrupt, SystemExit):
        root_logger.exception('User terminated experiment', exc_info=True)
    except:
        root_logger.exception('Error while running experiment', exc_info=True)

        if args.notify:
            notify.send_message("Exception occured during experiment! Traceback:\n{}".format(traceback.format_exc()), title='jtfadump Exception')
    finally:
        try:
            run_exp.stop()
        except:
            root_logger.exception('Error while stopping experiment', exc_info=True)

            if args.notify:
                notify.send_message("Exception occured while stopping experiment! Traceback:\n{}".format(traceback.format_exc()), title='jtfadump Exception')

    root_logger.info('jtfadump exiting')


if __name__ == "__main__":
    main()
