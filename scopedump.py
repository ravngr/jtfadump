import argparse
import os
import sys
import time

import numpy
import scipy.io as sio

import instrument

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Dump data from oscilloscope at set frequencies', epilog='Note: Stop frequency is not included in frequency range')
    parser.add_argument('generator', help='Signal Generator VISA ID')
    parser.add_argument('scope', help='Oscilloscope VISA ID')
    parser.add_argument('temperature', help='Temperature probe serial ID')
    parser.add_argument('interval', help='Time (mins) between samples', type=int)
    parser.add_argument('resolution', help='Seconds per division (secs)', type=float)
    parser.add_argument('start', help='Start frequency (Hz)', type=float)
    parser.add_argument('stop', help='Stop frequency (Hz)', type=float)
    parser.add_argument('step', help='Frequency step (Hz)', type=float)
    parser.add_argument('result', help='Result directory')

    parser.add_argument('-t', metavar='N', help='Log temperature channel(s) (default: 0)', dest='temps', nargs='+', type=int, default=[0])
    parser.add_argument('--in', metavar='N', help='Oscilloscope input channel (default: 1)', dest='input', type=int, default=1)
    parser.add_argument('--out', metavar='N', help='Oscilloscope output channel (default: 2)', dest='output', type=int, default=2)
    parser.add_argument('-w', metavar='T', help='Pulse width (secs) (default: 500e-6)', dest='width', type=float, default=500e-6)
    parser.add_argument('-l', metavar='T', help='Pulse period (secs) (default: 1e-3)', dest='period', type=float, default=1e-3)
    parser.add_argument('-p', metavar='T', help='Pulse power (dBm) (default: 0dBm)', dest='power', type=float, default=0.0)

    args = parser.parse_args()

    if not os.path.isdir(args.result):
        raise IOError('Result path is not a directory')

    if not os.access(args.result, os.W_OK):
        raise IOError('Result path is not writable')

    gen = instrument.SignalGenerator(args.generator)
    scope = instrument.Scope(args.scope)
    temp = instrument.TemperatureLogger(args.temperature)

    # Generate a range of frequencies
    freq = numpy.arange(args.start, args.stop, args.step)

    # Setup instruments
    gen.reset()
    gen.set_output_power(args.power)
    gen.set_pulsemod_source(gen.pulsemod_source.INT_40M)
    gen.set_pulsemod_count(1)
    gen.set_pulsemod_period(1, args.period)
    gen.set_pulsemod_width(1, args.width)
    gen.set_pulsemod_delay(1, 0.0)
    gen.set_pulsemod(True)

    scope.reset()
    scope.set_ch_display(1, False)
    scope.set_time_scale(args.resolution)
    scope.set_time_reference(scope.time_ref.LEFT)
    scope.set_trigger_sweep(scope.trigger_sweep.NORMAL)
    scope.set_trigger_mode(scope.trigger_mode.EDGE)
    scope.set_trigger_edge_source(scope.trigger_edge_source.EXTERNAL)
    scope.set_trigger_edge_level(1.0)

    # Setup scope channels for input and output
    for ch in [args.input, args.output]:
        scope.set_ch_atten(ch, 0)
        scope.set_ch_couple(ch, scope.ch_couple.DC)
        scope.set_ch_display(ch, True)

    scope.set_ch_label(args.input, 'IN');
    scope.set_ch_label(args.output, 'OUT');

    scope.set_ch_z(args.input, scope.ch_impedance.HIGH);
    scope.set_ch_z(args.output, scope.ch_impedance.FIFTY);

    # Dump channel(s)
    n = 0

    while True:
        result = {}

        result['time'] = time.time()
        result['temp'] = []
        result['freq_data'] = freq
        result['time_data'] = []
        result['in_data'] = []
        result['out_data'] = []

        # Log temperature channels
        for ch in args.temps:
            result['temp'].append(temp.get_temp(ch))

        for f in freq:
            # Set signal generator frequency
            gen.set_output_frequency(f)

            # Trigger scope
            scope.single_trigger()

            # Dump data from scope
            data = scope.get_waveform_smart_multichannel([args.input, args.output])

            if len(result['time_data']) == 0:
                result['time_data'] = [x[2] for x in data[0]]

            result['in_data'].append([x[3] for x in data[0]])
            result['out_data'].append([x[3] for x in data[1]])

        result['capture_time'] = time.time() - result['time']

        # Save result to matlab file
        filename = os.path.join(os.path.dirname(args.file.name), 'dump_%s_%06d.mat' % {time.strftime('YmdHMS'), n})
        sio.savemat(filename, result)
        print 'Wrote \'' + filename + '\''

        n += 1

        dt = time.time() - result['time']

        if dt < interval:
            time.sleep(interval - dt)

if __name__ == '__main__':
    main()
