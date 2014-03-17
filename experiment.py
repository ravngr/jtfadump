import logging
import numpy
import os
import scipy.io as sio
import time

import instrument

class Experiment():
    def __init__(self):
        self._log = logging.getLogger('exp')

    def setup(self, cfg, resultPath, timestr):
        print 'Setup'

    def run(self, cfg, resultPath, meas, endTime, target, uid, n):
        while time.time() < endTime:
            print 'Run'
            time.sleep(1)


    def close(self):
        print 'Close'

class Loop(Experiment):
    def setup(self, cfg, resultPath, timestr):
        # Configuration
        self._interval = cfg.getfloat('loop', 'interval')

        # Setup instruments
        self._count = instrument.Counter(cfg.get('id', 'count'))
        self._log.info('Counter: ' + self._count.get_id())

        self._count.reset()
        self._count.set_z(self._count.impedance.FIFTY)
        self._count.set_meas_time(200e-3)

        # Setup log file
        filename = os.path.join(resultPath, 'loop_%s.csv' % (timestr))

        self._file = open(filename, 'a')
        self._log.info('Loop file: ' + filename)

    def run(self, cfg, resultPath, meas, endTime, target, uid, n):
        n = 0

        while time.time() < endTime:
            t = time.time()
            volt = meas.volt
            tAmb = meas.tAmb
            tSub = meas.tSub
            f = self._count.get_freq()

            self._file.write('%d, %.3f, %.2f, %f.2, %.1f, %.1f, %.1f\n' % (n, t, volt, meas.target, tAmb, tSub, f))
            self._file.flush()

            self._log.info('LOOP: n=%d, T=%.1f, v=%.2f, tAmb=%.1f, tSub=%.1f, f=%.1f' % (n, meas.target, volt, tAmb, tSub, f))

            dt = time.time() - t

            if dt < self._interval:
                    time.sleep(self._interval - dt)

            n += 1

    def close(self):
        self._file.close()

class JTFA(Experiment):
    def setup(self, cfg, resultPath, timestr):
        # Configuration
        pulsePeriod = cfg.getfloat('jtfa', 'pulsePeriod')
        pulseWidth = cfg.getfloat('jtfa', 'pulseWidth')

        power = cfg.getfloat('jtfa', 'power')

        self._chIn = cfg.getint('jtfa', 'chIn')
        chInImp = cfg.get('jtfa', 'chInImp')
        self._chOut = cfg.getint('jtfa', 'chOut')
        chOutImp = cfg.get('jtfa', 'chOutImp')

        secPerDiv = cfg.getfloat('jtfa', 'secPerDiv')

        self._interval = cfg.getfloat('jtfa', 'interval')

        # Generate frequency span
        fCenter = cfg.get('jtfa', 'fCenter').split(',')
        fSpan = cfg.getfloat('jtfa', 'fSpan')
        fStep = cfg.getfloat('jtfa', 'fStep')

        self._freq = []

        for f in fCenter:
            freq = float(f)
            fMin = freq - fSpan / 2.0
            fMax = freq + fSpan / 2.0 + fStep

            self._freq = numpy.append(self._freq, numpy.arange(fMin, fMax, fStep))

        # Setup instruments
        self._scope = instrument.Scope(cfg.get('id', 'scope'))
        self._gen = instrument.SignalGen(cfg.get('id', 'siggen'))

        self._log.info('Signal Generator: ' + self._gen.get_id())

        self._gen.reset()
        self._gen.set_power(power)
        #self._gen.set_pulse_source(self._gen.pulsemod_source.INT_PULSE)
        self._gen.set_pulse_source(self._gen.pulsemod_source.INT_40M)
        self._gen.set_pulse_count(1)
        self._gen.set_pulse_period(pulsePeriod)
        self._gen.set_pulse_width(1, pulseWidth)
        self._gen.set_pulse(True)
        self._gen.set_output(True)

        self._log.info('Scope: ' + self._scope.get_id())

        self._scope.reset()
        self._scope.set_ch_enable(0, False)
        self._scope.set_time_scale(secPerDiv)
        self._scope.set_time_reference(self._scope.time_ref.LEFT)
        self._scope.set_trigger_sweep(self._scope.trigger_sweep.NORMAL)

        # Glitch trigger to capture pulse
        #self._scope.set_trigger_mode(self._scope.trigger_mode.GLITCH)
        #self._scope.set_trigger_glitch_source(self._scope.trigger_source.CHANNEL, self._chIn)
        #self._scope.set_trigger_glitch_range(min=100e-6)
        #self._scope.set_trigger_glitch_qualifier(self._scope.trigger_qualifier.GREATER)
        #self._scope.set_trigger_glitch_level(30e-3, self._scope.trigger_polarity.NEGATIVE)
        self._scope.set_trigger_mode(self._scope.trigger_mode.EDGE)
        self._scope.set_trigger_edge_source(self._scope.trigger_source.EXTERNAL)
        self._scope.set_trigger_edge_level(0.2)

        self._scope.set_ch_label_visible(True)

        # Input channel setup
        self._scope.set_ch_label(self._chIn, 'IN');
        self._scope.set_ch_atten(self._chIn, 1)
        self._scope.set_ch_couple(self._chIn, self._scope.ch_couple.DC)
        self._scope.set_ch_z(self._chIn, chInImp)
        self._scope.set_ch_enable(self._chIn, True)

        # Output channel setup
        self._scope.set_ch_label(self._chOut, 'OUT');
        self._scope.set_ch_atten(self._chOut, 1)
        self._scope.set_ch_couple(self._chOut, self._scope.ch_couple.DC)
        self._scope.set_ch_z(self._chOut, chOutImp)
        self._scope.set_ch_enable(self._chOut, True)

        # Setup fast channel dumping
        self._scope.get_waveform_smart_multichannel_fast_init()

        # Setup directory for experiment results
        self._result_path = os.path.join(resultPath, 'jtfa_%s' % (timestr))

        if not os.path.exists(self._result_path):
            os.mkdir(self._result_path)
        else:
            raise IOError('Result path already exists')

        if not os.access(self._result_path, os.W_OK):
            raise IOError('Result path is not writable')

        self._log.info('JTFA directory: ' + self._result_path)

    def run(self, cfg, resultPath, meas, endTime, target, uid, iter):
        # Sleep to next window (because of instability caused by temperature change)
        if iter == 0:
            time.sleep(self._interval)

        result = {}

        result['uid'] = uid
        result['iteration'] = iter
        result['capture_start'] = time.time()
        result['capture_time'] = 0
        result['volt'] = []
        result['target'] = target
        result['temp_amb'] = []
        result['temp_sub'] = []
        result['freq'] = self._freq
        result['time_data'] = []
        result['in_data'] = []
        result['out_data'] = []

        for n, f in enumerate(self._freq):
            self._log.info('Capture %.1fHz (%d/%d)' % (f, (n+1), len(self._freq)))

            # Cycle pulse modulator (bugs on E4438C for some reason?) and set output frequency
            self._gen.set_pulse(False)
            self._gen.set_frequency(f)
            self._gen.set_pulse(True)

            # Wait (just to be safe, changing ranges occasionally takes a while)
            #time.sleep(0.5)

            # Range scope
            #self._scope.set_aq_mode(self._scope.mode_aq.NORMAL)

            #fail = 0
            #n_cycles = 16
            #cycles = range(0, n_cycles)
            #
            #in_d = []
            #out_d = []
            #
            #for r in cycles:
            #    try:
            #        d = self._scope.get_waveform_smart_multichannel_fast([self._chIn, self._chOut])
            #    except:
            #        self._log.warn('Failed to get data from scope (%d/%d)!' % (r + 1, cycles))
            #
            #        fail += 1
            #
            #        if fail > (n_cycles / 2):
            #            raise Exception('Too many scope failures in averaging cycle')
            #
            #        continue
            #
            #    # Save time data on first run only
            #    if len(result['time_data']) == 0:
            #        result['time_data'] = [x[2] for x in d[0]]
            #
            #    in_d.append([x[3] for x in d[0]])
            #    out_d.append([x[3] for x in d[1]])
            #
            #result['in_data'].append([sum(x) / len(in_d) for x in zip(*in_d[::-1])])
            #result['out_data'].append([sum(x) / len(out_d) for x in zip(*out_d[::-1])])

            # Get averaged data
            #self._scope.set_aq_mode(self._scope.mode_aq.AVERAGE, 128)
            #self._scope.trigger_window(0.25)

            #data = [0, 0]
            #data[0] = self._scope.get_waveform_raw_process(self._scope.get_waveform_raw(self._scope.wave_source.CHANNEL, self._chIn))
            #data[1] = self._scope.get_waveform_raw_process(self._scope.get_waveform_raw(self._scope.wave_source.CHANNEL, self._chOut))

            # Record temperature
            result['volt'].append(meas.volt)
            result['temp_amb'].append(meas.tAmb)
            result['temp_sub'].append(meas.tSub)

            # Save waveform data
            data = self._scope.get_waveform_smart_multichannel_fast([self._chIn, self._chOut])

            if len(result['time_data']) == 0:
                result['time_data'] = [x[2] for x in data[0]]

            result['in_data'].append([x[3] for x in data[0]])
            result['out_data'].append([x[3] for x in data[1]])

        # Record how long the dump took
        result['capture_time'] = time.time() - result['capture_start']

        self._log.info('Capture time: ' + str(result['capture_time']))

        # Save dump to matlab file
        resultFile = os.path.join(self._result_path, 'data_%s_%03d_%s_%02d.mat' % (time.strftime('%Y%m%d_%H%M%S'), target, uid, iter))
        sio.savemat(resultFile, result, do_compression=True)

        self._log.info('Result: ' + resultFile)

        #time.sleep(self._interval)

    def close(self):
        pass
