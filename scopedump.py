import argparse
import instrument
import numpy
import sys
import time

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Dump data from oscilloscope at set frequencies', epilog='Note: Stop frequency is not included in frequency range')
    parser.add_argument('interval', help='Time (secs) between samples', type=float)
    parser.add_argument('generator', help='Signal Generator VISA ID')
    parser.add_argument('scope', help='Oscilloscope VISA ID')
    parser.add_argument('start', help='Start frequency (Hz)', type=float)
    parser.add_argument('stop', help='Stop frequency (Hz)', type=float)
    parser.add_argument('step', help='Frequency step (Hz)', type=float)

    parser.add_argument('-t', metavar='N', help='Log temperature channel(s) (default: 0)', dest='temp', nargs='+', type=int, default=[0])
    parser.add_argument('-s', metavar='N', help='Log oscilloscope channel(s) (default: 1)', dest='channel', nargs='+', type=int, default=[1])

    args = parser.parse_args()

    gen = instrument.SignalGenerator(args.generator)
    scope = instrument.Scope(args.scope)

    # Generate a range of frequencies
    freq = numpy.arange(args.start, args.stop, args.step)

    # Dump channel(s)

if __name__ == '__main__':
    main()
