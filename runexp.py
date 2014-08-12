import argparse
import ConfigParser
import logging
import os
import pickle
import random
import string
import time

import instrument
import pid

import experiment
from fileinput import filename

class Measurements():
    def __init__(self):
        self.tAmb = 0
        self.tSub = 0
        self.volt = 0
        self.target = 0

exp = experiment.Pulse()
meas = Measurements()

def main():
    global exp
    global meas

    # Start time string
    timestr = time.strftime('%Y%m%d_%H%M%S')

    parser = argparse.ArgumentParser(description='Temperature Experiments')

    parser.add_argument('config', help='Experiment configuration file(s)', nargs='+')

    parser.add_argument('-v', help='Verbose output', dest='verbose', action='store_true')
    parser.add_argument('--no-temp', help='Run without controlling the device temperature', dest='notemp', action='store_true')
    parser.add_argument('--lock', help='Lock the front panels of test equipment', dest='lock', action='store_true')
    parser.set_defaults(verbose=False)
    parser.set_defaults(notemp=False)
    parser.set_defaults(lock=False)

    args = parser.parse_args()

    # Read configuration file(s)
    cfg = ConfigParser.RawConfigParser()
    cfg.read(args.config)

    # Instrument IDs
    idPSU = cfg.get('id', 'psu')
    idTemp = cfg.get('id', 'templog')

    # Experimental parameters
    tMin = cfg.getfloat('param', 'tMin')
    tMax = cfg.getfloat('param', 'tMax')
    tStep = cfg.getfloat('param', 'tStep')
    vMax = cfg.getfloat('param', 'vMax')
    tInterval = cfg.getfloat('param', 'tInterval')
    runs = cfg.getint('param', 'runs')

    # Temperature controller
    Kp = cfg.getfloat('pid', 'Kp')
    Ki = cfg.getfloat('pid', 'Ki')
    Kd = cfg.getfloat('pid', 'Kd')

    # Setup logging
    logPath = cfg.get('path', 'log')

    if not os.path.isdir(logPath):
        raise IOError('Log path is not a directory')

    if not os.access(logPath, os.W_OK):
        raise IOError('Log path is not writable')

    logPath = os.path.realpath(logPath)

    logFilePath = os.path.join(logPath, 'log_%s.txt' % (timestr))
    print 'Logging path: ' + logFilePath
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger('')
    log.handlers = []

    logFile = logging.FileHandler(logFilePath)
    logFile.setLevel(logging.INFO)
    logFileFmt = logging.Formatter(fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%Y%m%d %H:%M:%S')
    logFile.setFormatter(logFileFmt)
    log.addHandler(logFile)

    logConsole = logging.StreamHandler()
    logConsole.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    logConsoleFmt = logging.Formatter(fmt='%(asctime)s [%(levelname)-5s] %(name)s: %(message)s', datefmt='%H:%M:%S')
    logConsole.setFormatter(logConsoleFmt)
    log.addHandler(logConsole)


    # Result path
    resultPath = cfg.get('path', 'result')

    if not os.path.isdir(resultPath):
        raise IOError('Result path is not a directory')

    if not os.access(resultPath, os.W_OK):
        raise IOError('Result path is not writable')

    resultPath = os.path.realpath(resultPath)
    logging.info('Result path: ' + resultPath)


    # Setup experiment
    exp.setup(cfg, resultPath, timestr)


    # Setup PID loop
    tempFilePath = os.path.join(logPath, 'temp_%s.csv' % (timestr))
    tempFile = open(tempFilePath, 'w')

    # Wait for PSU
    tempLog = instrument.TemperatureLogger(idTemp)

    if not args.notemp:
        psu = instrument.PowerSupply(idPSU)
        time.sleep(0.2)

        logging.info('Power Supply: ' + psu.get_id())

        time.sleep(0.2)
        psu.reset()
        # Disable fan alarm
        time.sleep(0.2)
        psu.set_alarm_mask(0x7F7)
        time.sleep(0.2)
        psu.clear_alarm()
        time.sleep(0.2)
        psu.set_voltage(0.0)
        time.sleep(0.2)
        psu.set_current(14.0)
        time.sleep(0.2)
        psu.set_output(True)
        
        if args.lock:
            time.sleep(0.2)
            psu.set_sys_locked(True)
    else:
        logging.warning('Running without temperature control')

    def get_temp():
        global meas

        try:
            t = time.time()
            meas.tAmb = tempLog.get_temp(0)
            meas.tSub = tempLog.get_temp(2)

            tempFile.write('%.3f, %.2f, %.1f, %.1f\n' % (t, meas.volt, meas.tAmb, meas.tSub))
            tempFile.flush()
        except:
            logging.warning('Failed to read temperature!')

        return meas.tSub

    def set_voltage_real(v):
        global meas
        meas.volt = v
        psu.set_voltage(v)

    def set_voltage_dummy(v):
        pass

    set_voltage = set_voltage_dummy if args.notemp else set_voltage_real

    tempCtrlInterval = 3 # Not really worth going faster since temperature probe is slow
    tempCtrlLimit = pid.Limit(0, vMax)

    # Attempt to read any existing temperature to start from (in case of restart)
    try:
        with open('tempTarget.pickle') as f:
            tempTarget, dT = pickle.load(f)
        logging.warning('Resuming temperature = %.2f with tStep = %.2f' % (tempTarget, dT))
    except:
        tempTarget = tMin
        dT = tStep

    tempCtrl = pid.PID(get_temp, set_voltage, 0, tempTarget, tempCtrlLimit, Kp, Ki, Kd, tempCtrlInterval)

    # Save configuration used to results folder
    cfgfilename = os.path.join(logPath, 'config_%s.cfg' % (timestr))
    with open(cfgfilename, 'w') as f:
        cfg.write(f)

    # Start experiment
    tempCtrl.start()
    loop = 0

    try:
        while True:
            # Generate an ID for this loop
            uid = ''.join(random.choice(string.hexdigits[:16]) for x in range(8))

            # Check for operational PID loop
            if not tempCtrl.is_running():
                raise SystemError()

            with open('tempTarget.pickle', 'w') as f:
                pickle.dump((tempTarget, dT), f)

            # Next temperature change time
            startTime = time.time()
            nextTime = startTime + tInterval

            logging.info('Loop %s %d @ %.2f (%.2f)' % (uid, loop, tempTarget, dT))

            # Set new target temperature
            meas.target = tempTarget
            tempCtrl.set_target(tempTarget)

            # Do Science!
            fail = 0
            fail_threshold = 0

            for n in range(0, runs):
                try:
                    exp.run(cfg, resultPath, meas, nextTime, tempTarget, uid, n)
                except:
                    fail += 1

                    if fail > fail_threshold:
                        raise
                    else:
                        logging.warning('Capture failed! Failure %d of %d allowed' % (fail, fail_threshold))

            # Alter output voltage according to state (up/down)
            if tempTarget <= tMin:
                dT = tStep

            if tempTarget >= tMax:
                dT = -tStep

            tempTarget += dT
            loop += 1
    except:
        # Save current PID state
        tempCtrl.stop()
        exp.close()
        raise

if __name__ == '__main__':
    main()
