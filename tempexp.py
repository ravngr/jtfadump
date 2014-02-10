import argparse
import instrument
import json
import os
import pid
import threading
import time
import status
import sys

volt = 0

def main():
    parser = argparse.ArgumentParser(description='Cycle temperatures and monitor resonant frequency')
    parser.add_argument('result', help='Results folder')

    parser.add_argument('-v', help='Verbose output', dest='verbose', action='store_true')
    parser.set_defaults(verbose=False)

    args = parser.parse_args()

    if not os.path.isdir(args.result):
        raise IOError('Result path is not a directory')

    if not os.access(args.result, os.W_OK):
        raise IOError('Result path is not writable')

    # Verbose VISA commands (output for logging)
    instrument._debug = args.verbose

    # Configuration
    tMax = 100.0
    tMin = 30.0
    tStep = 2

    chTAmbient = 0
    chTSubstrate = 2

    stepInterval = 300 # 5 minutes
    interval = 5

    Kp = 1
    Ki = 0.01
    Kd = 0.5

    # Voltage output limit
    pidVoltLimit = pid.Limit(0, 10)

    # Twitter authentication (omitted from git repository)
    f = open('twitter.json', 'r')
    auth = json.loads(f.readline())
    stat = status.TweetStatus(auth)

    # Instrument Connections
    psu = instrument.PowerSupply("ASRL4::INSTR")
    temp = instrument.TemperatureLogger("COM3")
    tempLock = threading.Semaphore()
    count = instrument.Counter("GPIB0::10::INSTR")

    print psu.get_id()
    print count.get_id()

    # Open log file
    filename = os.path.join(os.path.dirname(args.result), 'data_%s.csv' % (time.strftime('%Y%m%d%H%M%S')))
    print('Logging to: ' + filename)
    log = open(filename, 'a')

    # Setup instruments
    count.reset()
    count.set_z(count.impedance.FIFTY)
    count.set_meas_time(200e-3)

    #psu.reset()
    psu.set_voltage(0.0)
    psu.set_current(14.0)
    psu.set_output(True)

    # PID temperature controller
    def get_temp():
        tempLock.acquire()
        t = temp.get_temp(chTSubstrate)
        tempLock.release()
        return t

    def set_volt(v):
        global volt
        volt = v
        psu.set_voltage(v)

    p = pid.PID(get_temp, set_volt, volt, tMin, pidVoltLimit, Kp, Ki, Kd, 3)
    p.start()

    # Setup temperature sweep
    n = 0
    f = 0.0
    t1 = 0.0
    t2 = 0.0
    dT = tStep
    target_temp = tMin

    try:
        while True:
            # Change the temperature
            p.set_target(target_temp)

            # Next temperature change time
            t = time.time()
            nt = t + stepInterval

            # Record frequency and temperature data
            trMax = 0

            while t < nt:
                print 'Run: ' + str(time.strftime('%Y%m%d%H%M%S')) + ' / Next: ' + str(time.strftime('%Y%m%d%H%M%S', time.localtime(nt)))

                log.write(str(t) + ', ' + str(volt))

                tempLock.acquire()
                t1 = temp.get_temp(chTAmbient)
                t2 = temp.get_temp(chTSubstrate)
                tempLock.release()

                if t2 > trMax:
                    trMax = t2

                log.write(', ' + str(t1))
                log.write(', ' + str(t2))

                f = count.get_freq()
                log.write(', ' + str(f) + '\n')

                log.flush()

                deltat = time.time() - t

                print('LOOP: n=%d, T=%.1f, v=%.2f, dT=%.1f, t1=%.1f, t2=%.1f, tM=%.1f, f=%.1f' % (n, target_temp, volt, dT, t1, t2, trMax, f))

                if deltat < interval:
                    time.sleep(interval - deltat)

                t = time.time()

            # Alter output voltage according to state (up/down)
            if target_temp <= tMin:
                dT = tStep

            if trMax >= tMax or target_temp >= tMax:
                dT = -tStep

            # Log result
            print 'Cycle ' + str(n) + ' done!'

            #try:
            #    stat.send('LOOP: n=%d, T=%.1f, v=%.2f, dT=%.1f, t1=%.1f, t2=%.1f, tM=%.1f, f=%.1f' % (n, target_temp, volt, dT, t1, t2, trMax, f))
            #except:
            #    print 'Message failed!'
            #    pass

            target_temp += dT
            n += 1
    except:
        p.stop()
        psu.set_voltage(0)
        psu.set_output(False)
        raise

if __name__ == '__main__':
    main()
