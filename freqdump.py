import instrument
import sys
import time
import visa

def main():
    instrument._debug = False

    channels = [0]

    # Display usage and instrument list if wrong arguments are provided
    if len(sys.argv) < 4 or len(sys.argv) > 5:
        sys.stderr.write("Usage: " + sys.argv[0] + " <time interval (secs)> <frequency counter GPIB ID> <temperature logger serial ID> [temperature channel(s)]\n")
        sys.stderr.write("\nAvailable instruments:\n")

        for i in visa.get_instruments_list(False):
            sys.stderr.write(i + '\n')

        sys.stderr.flush()

        exit(0)

    interval = float(sys.argv[1])

    # Allow user to specify channels
    if len(sys.argv) == 5:
        channels = sys.argv[4].split(',')
        channels = [ int(x) for x in channels ]

    # Connect to instruments
    counter = instrument.Counter(sys.argv[2])
    temp = instrument.TemperatureLogger(sys.argv[3])

    counter.reset()
    counter.set_z(counter.impedance.FIFTY)
    counter.set_meas_time(200e-3)

    while True:
        t = time.time()
        f = counter.get_freq()

        sys.stdout.write(str(t))

        for i in channels:
            sys.stdout.write(', ' + str(temp.get_temp(i)))

        sys.stdout.write(', ' + str(f) + '\n')

        sys.stdout.flush()

        dt = time.time() - t

        if dt < interval:
            time.sleep(interval - dt)

if __name__ == '__main__':
    main()
