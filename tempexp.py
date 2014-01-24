import instrument
import json
import time
import status
import sys

def main():
    instrument._debug = False

    f = open('twitter.json', 'r')
    auth = json.loads(f.readline())
    stat = status.TweetStatus(auth)

    tMax = 100.0
    vMax = 40.0

    tChannels = [0,2]

    stepInterval = 10
    interval = 1800

    psu = instrument.PowerSupply("ASRL4::INSTR")
    temp = instrument.TemperatureLogger("COM6")
    count = instrument.Counter("GPIB0::10::INSTR")

    #psu.reset()
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
    dv = 0.5

    while True:
        # Change output voltage
        psu.set_voltage(v)

        # Next voltage change time
        t = time.time()
        nt = t + stepInterval

        # Record frequency and temperature data
        trMax = 0

        while t < nt:
            t = time.time()

            sys.stdout.write(str(t) + ', ' + str(v))

            t1 = temp.get_temp(0)
            t2 = temp.get_temp(2)

            if t2 > trMax:
                    trMax = t2

            sys.stdout.write(', ' + str(t1))
            sys.stdout.write(', ' + str(t2))

            f = count.get_freq()
            sys.stdout.write(', ' + str(f) + '\n')

            sys.stdout.flush()

            dt = time.time() - t

            if dt < interval:
                time.sleep(interval - dt)

        # Alter output voltage according to state (up/down)
        if v == 0:
            dv = 0.5

        if trMax >= tMax or v >= vMax:
            dv = -0.5

        # Log result
        try:
            stat.send('LOOP: n=%d, v=%.1f, dv=%.1f, t1=%.1f, t2=%.1f, f=%.1f' % (n, v, dv, t1, t2, f))
        except:
            pass

        v += dv
        n += 1

if __name__ == '__main__':
    main()
