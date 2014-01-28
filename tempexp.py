import instrument
import json
import time
import status
import sys
import threading

def main():
    instrument._debug = False

    f = open('twitter.json', 'r')
    auth = json.loads(f.readline())
    stat = status.TweetStatus(auth)

    tMax = 100.0
    vMax = 7.5
	vStep = 0.25

    tChannels = [0,2]

    stepInterval = 600
    interval = 10

    psu = instrument.PowerSupply("ASRL4::INSTR")
    temp = instrument.TemperatureLogger("COM3")
    count = instrument.Counter("GPIB0::10::INSTR")

    print psu.get_id()
    print count.get_id()

    log = open(time.strftime('%y%m%d%H%M%S') + '.csv', 'a')

    psu.reset()
    psu.set_voltage(0.0)
    psu.set_current(14.0)
    psu.set_output(True)

    count.reset()
    count.set_z(count.impedance.FIFTY)
    count.set_meas_time(200e-3)

    n = 0
    f = 0.0
    t1 = 0.0
    t2 = 0.0
    v = 0.0
    dv = vStep

    while True:
        # Change output voltage
        psu.set_voltage(v)

        # Next voltage change time
        t = time.time()
        nt = t + stepInterval

        # Record frequency and temperature data
        trMax = 0

        while t < nt:
            print 'Run ' + str(t)
            t = time.time()

            log.write(str(t) + ', ' + str(v))

            t1 = temp.get_temp(0)
            t2 = temp.get_temp(2)

            if t2 > trMax:
                    trMax = t2

            log.write(', ' + str(t1))
            log.write(', ' + str(t2))

            f = count.get_freq()
            log.write(', ' + str(f) + '\n')

            log.flush()

            dt = time.time() - t

            if dt < interval:
                time.sleep(interval - dt)

        # Alter output voltage according to state (up/down)
        if v == 0:
            dv = vStep

        if trMax >= tMax or v >= vMax:
            dv = -vStep

        # Log result
        print 'Cycle ' + str(n) + ' done!'
        #stat.send('LOOP: n=%d, v=%.1f, dv=%.1f, t1=%.1f, t2=%.1f, f=%.1f' % (n, v, dv, t1, t2, f))

        v += dv
        n += 1

if __name__ == '__main__':
    main()
