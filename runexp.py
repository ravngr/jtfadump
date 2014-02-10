import argparse
import ConfigParser
import logging
import os
import pickle
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

exp = experiment.JTFA()
meas = Measurements()

def main():
    global exp
    global meas

    # Start time string
    timestr = time.strftime('%Y%m%d_%H%M%S')

    parser = argparse.ArgumentParser(description='Temperature Experiments')

    parser.add_argument('config', help='Experiment configuration file(s)', nargs='+')

    parser.add_argument('-v', help='Verbose output', dest='verbose', action='store_true')
    parser.set_defaults(verbose=False)
    parser.set_defaults(visa=False)

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

    #psu = instrument.PowerSupply(idPSU)
    tempLog = instrument.TemperatureLogger(idTemp)
    #logging.info('Power Supply: ' + psu.get_id())

    # Wait for PSU
    time.sleep(0.2)
    #psu.reset()
    time.sleep(0.2)
    #psu.set_voltage(0.0)
    time.sleep(0.2)
    #psu.set_current(14.0)
    time.sleep(0.2)
    #psu.set_output(True)

    def get_temp():
        global meas
        t = time.time()
        meas.tAmb = tempLog.get_temp(0)
        meas.tSub = tempLog.get_temp(2)

        tempFile.write('%.3f, %.2f, %.1f, %.1f\n' % (t, meas.volt, meas.tAmb, meas.tSub))
        return meas.tSub

    def set_voltage(v):
        global meas
        meas.volt = v
        #psu.set_voltage(v)

    tempCtrlInterval = 3 # Not really worth going faster since temperature probe is slow
    tempCtrlLimit = pid.Limit(0, vMax)

    # Attempt to read any existing temperature to start from (in case of restart)
    try:
        with open('tempTarget.pickle') as f:
            tempTarget, dT = pickle.load(f)
        logging.warning('Resuming temperature from %.2f with tStep = %.2f' % (tempTarget, dT))
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
            # Check for operational PID loop
            if not tempCtrl.is_running():
                raise SystemError()

            with open('tempTarget.pickle', 'w') as f:
                pickle.dump((tempTarget, dT), f)

            # Next temperature change time
            startTime = time.time()
            nextTime = startTime + tInterval

            logging.info('Loop %d @ %.2f: %s, Next step: %s' % (loop, tempTarget, str(time.strftime('%Y%m%d %H:%M:%S')), str(time.strftime('%Y%m%d %H:%M:%S', time.localtime(nextTime)))))

            meas.target = tempTarget

            tempCtrl.set_target(tempTarget)

            # Do Science!
            exp.run(cfg, resultPath, meas, nextTime)

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
