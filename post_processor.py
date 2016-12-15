# -- coding: utf-8 --

import logging

import matplotlib.pyplot as plt
import numpy

import data_capture
import mks


class PostProcessor:
    def __init__(self, run_experiment, run_data_capture, cfg, notify):
        self._run_experiment = run_experiment
        self._run_data_capture = run_data_capture
        self._cfg = cfg
        self._notify = notify

        self._logger = logging.getLogger(__name__)

    @staticmethod
    def get_supported_data_capture():
        raise NotImplementedError()

    def process(self, data):
        raise NotImplementedError()

    def log(self, level, msg):
        self._logger.log(level, msg)

        if self._notify is not None:
            self._notify.send_message(msg, title='Post-Processor Message')


class ScopeSignalProcessor(PostProcessor):
    def __init__(self, run_experiment, run_data_capture, cfg, notify):
        PostProcessor.__init__(self, run_experiment, run_data_capture, cfg, notify)

        # Setup axes
        # plt.ion()

        self._scope_fig, self._scope_axes = plt.subplots(2, sharex=True)

        self._scope_axes[0].set_title('Signals')

        self._scope_axes[1].set_xlabel('Time (us)')
        self._scope_axes[0].set_ylabel('Input Signal (mV)')
        self._scope_axes[1].set_ylabel('Output Signal (mV)')

        self._scope_axes_line = [None, None]

        plt.show(block=False)

    @staticmethod
    def get_supported_data_capture():
        return data_capture.PulseData,

    def process(self, data):
        time = [x * 1000000 for x in data['result_scope_time']]
        scope = ([x * 1000 for x in data['result_scope_in'][0]], [x * 1000 for x in data['result_scope_out'][0]])

        self._scope_axes[0].set_title("Signals {}".format(data['capture_id']))

        for line in [0, 1]:
            if self._scope_axes_line[line] is None:
                self._scope_axes_line[line], = self._scope_axes[line].plot(time, scope[line])
            else:
                self._scope_axes_line[line].set_ydata(scope[line])

        self._scope_fig.canvas.draw()
        plt.pause(0.001)

        return data

        
class DeltaScopeSignalProcessor(PostProcessor):
    def __init__(self, run_experiment, run_data_capture, cfg, notify):
        PostProcessor.__init__(self, run_experiment, run_data_capture, cfg, notify)

        # Setup axes
        # plt.ion()

        self._scope_fig, self._scope_axes = plt.subplots(2, sharex=True)

        self._scope_axes[0].set_title('Signals')

        self._scope_axes[1].set_xlabel('Time (us)')
        self._scope_axes[0].set_ylabel('Input Signal (mV)')
        self._scope_axes[1].set_ylabel('Output Signal (mV)')

        self._scope_axes_line = [None, None]

        plt.show(block=False)
        
        self._prev = None;

    @staticmethod
    def get_supported_data_capture():
        return data_capture.PulseData,

    def process(self, data):
        time = [x * 1000000 for x in data['result_scope_time']]
        scope = ([x * 1000 for x in data['result_scope_in'][0]], [x * 1000 for x in data['result_scope_out'][0]])
        
        if self._prev is not None:
            delta_scope = [[scope[x][y] - self._prev[x][y] for y in range(0, len(scope[x]))] for x in range(0, 2)]
        
            self._scope_axes[0].set_title("Signals {}".format(data['capture_id']))

            for line in [0, 1]:
                line_data = delta_scope[line]
            
                if self._scope_axes_line[line] is None:
                    self._scope_axes_line[line], = self._scope_axes[line].plot(time, line_data)
                else:
                    self._scope_axes_line[line].set_ydata(line_data)
                
                self._scope_axes[line].set_xlim(min(time), max(time))
                ymax = max([abs(x) for x in line_data])
                self._scope_axes[line].set_ylim(-1.05 * ymax, 1.05 * ymax)

            self._scope_fig.canvas.draw()
            plt.pause(0.001)
        
        self._prev = scope

        return data

        
class FrequencyCountProcessor(PostProcessor):
    def __init__(self, run_experiment, run_data_capture, cfg, notify):
        PostProcessor.__init__(self, run_experiment, run_data_capture, cfg, notify)
        
        self._prev_f = None
        self._rolling_f = []

        self._threshold = 1e6

    @staticmethod
    def get_supported_data_capture():
        return (data_capture.FrequencyData, data_capture.FrequencyDataLegacy,)

    def process(self, data):
        f = data['result_counter_frequency'][0]
        
        if self._prev_f is not None:
            df = f - self._prev_f
        else:
            df = 0
        
        self._rolling_f.append(f)
        
        while len(self._rolling_f) > 32:
            self._rolling_f.pop(0)
        
        a = numpy.array(self._rolling_f)
        
        meana = numpy.mean(a)
        da = numpy.diff(a)
        meandelta = numpy.mean(da)
        stda = numpy.std(a)
        stdd = numpy.std(da)
        
        if abs(df) > self._threshold:
            msg = "Possible mode hop: {} Hz -> {} Hz (delta: {:.1f} Hz)".format(self._prev_f, f, df)

            self.log(logging.WARNING, msg)
        
        self._prev_f = f
        
        self._logger.info("Frequency:       {:.1f} Hz".format(f))
        self._logger.info("Frequency delta: {:.1f} Hz".format(df))
        self._logger.info("Frequency mean:  {:.1f} Hz".format(meana))
        self._logger.info("Frequency dmean: {:.1f} Hz".format(meandelta))
        self._logger.info("Frequency std:   {:.1f} Hz".format(stda))
        self._logger.info("Frequency dstd:  {:.1f} Hz".format(stdd))

        return data


class FrequencyDisplayProcessor(PostProcessor):
    _THRESHOLD = [60, 60 * 60, 24 * 60 * 60]

    def __init__(self, run_experiment, run_data_capture, cfg, notify):
        PostProcessor.__init__(self, run_experiment, run_data_capture, cfg, notify)

        self._freq_fig, self._freq_axes = plt.subplots(len(self._THRESHOLD) + 1)
        
        self._freq_axes[0].set_title('Counter Frequency')

        for a in self._freq_axes:
            a.set_xlabel('Time (s)')
            a.set_ylabel('Frequency (Hz)')

        self._freq_axes_line = [None] * (len(self._THRESHOLD) + 1)

        self._plot_values = []

        plt.show(block=False)

    @staticmethod
    def get_supported_data_capture():
        return data_capture.FrequencyData, data_capture.FrequencyDataLegacy,

    def process(self, data):
        t = data['capture_timestamp']
        t = data['capture_timestamp']
        f = data['result_counter_frequency'][0]
        
        self._plot_values.append((t, f,))

        # Only store the last _THRESHOLD seconds for plotting
        while self._plot_values[0][0] < (t - max(self._THRESHOLD)):
            self._plot_values.pop(0)

        # Generate plot sets
        for n in range(1, len(self._THRESHOLD) + 1):
            plot_values = [v for v in self._plot_values if (v[0] >= (t - self._THRESHOLD[n - 1]))]
            
            x = [v[0] - plot_values[-1][0] for v in plot_values]
            y = [v[1] for v in plot_values]
            
            if self._freq_axes_line[n] is None:
                self._freq_axes_line[n], = self._freq_axes[n].plot(x, y)
            else:
                self._freq_axes_line[n].set_xdata(x)
                self._freq_axes_line[n].set_ydata(y)
            
            ymin = min(y)
            ymax = max(y)
            yspan = ymax - ymin
            self._freq_axes[n].set_xlim(min(x), max(x))
            self._freq_axes[n].set_ylim(ymin - 0.05 * yspan, ymax + 0.05 * yspan)
        
        # First plot is for delta frequency over shortest
        plot_values = [v for v in self._plot_values if (v[0] >= (t - self._THRESHOLD[0]))]
        
        if len(plot_values) > 2:
            x = [v[0] - plot_values[-1][0] for v in plot_values]
            y = [v[1] for v in plot_values]
            x = x[:-1]
            y = [y[n] - y[n - 1] for n in range(1, len(y))]
            
            if self._freq_axes_line[0] is None:
                self._freq_axes_line[0], = self._freq_axes[0].plot(x, y)
            else:
                self._freq_axes_line[0].set_xdata(x)
                self._freq_axes_line[0].set_ydata(y)
            
            ymin = min(y)
            ymax = max(y)
            yspan = ymax - ymin
            self._freq_axes[0].set_xlim(min(x), max(x))
            self._freq_axes[0].set_ylim(ymin - 0.05 * yspan, ymax + 0.05 * yspan)

        self._freq_fig.canvas.draw()
        plt.pause(0.001)

        return data


class BlackMagicDetector(PostProcessor):
    def __init__(self, run_experiment, run_data_capture, cfg, notify):
        PostProcessor.__init__(self, run_experiment, run_data_capture, cfg, notify)

        self._prev_timestamp = None

    @staticmethod
    def get_supported_data_capture():
        return data_capture.FrequencyData, data_capture.FrequencyDataLegacy, data_capture.PulseData, \
               data_capture.VNAData

    def process(self, data):
        timestamp = data['capture_timestamp']

        if self._prev_timestamp is not None and timestamp <= self._prev_timestamp:
            dt = timestamp - self._prev_timestamp

            self.log(logging.WARNING, "Negative time shift since last capture dt: {:.3f} sec".format(dt))

        self._prev_timestamp = timestamp

        return data
        

class MKSMonitorPostProcessor(PostProcessor):
    _CFG_SECTION = 'mks'

    def __init__(self, run_experiment, run_data_capture, cfg, notify):
        PostProcessor.__init__(self, run_experiment, run_data_capture, cfg, notify)

        mks_port = self._cfg.get(self._CFG_SECTION, 'port')
        self._expiry = self._cfg.getfloat(self._CFG_SECTION, 'expiry')
        self._timeout = self._cfg.getfloat(self._CFG_SECTION, 'timeout')

        # Connect to MKS
        self._mks = mks.MKSSerialMonitor(mks_port)

    @staticmethod
    def get_supported_data_capture():
        return data_capture.PulseData,

    def process(self, data):
        # If data is too old then wait for an update
        if self._mks.get_lag() > self._expiry:
            self._logger.warn('Waiting for MKS update')

            if not self._mks.update_wait(self._timeout):
                raise mks.MKSException('MKS timed out')

        mks_state = self._mks.get_state()
        
        # Print to logging
        self._logger.info("Recorded MKS Flow: {}sccm".format('sccm, '.join(str(x) for x in mks_state['mks_flow'])))
        self._logger.info("Recorded VGen RTD: {}".format(', '.join(str(x) for x in mks_state['mks_vgen_rtd'])))
        self._logger.info("Recorded VGen RH: {}%".format(str(mks_state['mks_vgen_relative_value'][0])))
        
        data.update(mks_state)

        return data
