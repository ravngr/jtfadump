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

        
class FrequencyCountProcessor(PostProcessor):
    def __init__(self, run_experiment, run_data_capture, cfg, notify):
        PostProcessor.__init__(self, run_experiment, run_data_capture, cfg, notify)
        
        self._prev_f = None
        self._rolling_f = []

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
        
        if abs(df) > 1e6:
            msg = "Possible mode hop: {} Hz -> {} Hz (delta: {:.1f} Hz)".format(self._prev_f, f, df)
        
            self._logger.warn(msg)
            
            if self._notify is not None:
                self._notify.send_message(msg, title='jtfadump Mode Hop Detector')
        
        self._prev_f = f
        
        self._logger.info("Frequency:       {:.1f} Hz".format(f))
        self._logger.info("Frequency delta: {:.1f} Hz".format(df))
        self._logger.info("Frequency mean:  {:.1f} Hz".format(meana))
        self._logger.info("Frequency dmean: {:.1f} Hz".format(meandelta))
        self._logger.info("Frequency std:   {:.1f} Hz".format(stda))
        self._logger.info("Frequency dstd:  {:.1f} Hz".format(stdd))

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
