# -- coding: utf-8 --

import matplotlib.pyplot as plt

import data_capture


class PostProcessor:
    def __init__(self, run_experiment, run_data_capture, cfg):
        self._run_experiment = run_experiment
        self._run_data_capture = run_data_capture
        self._cfg = cfg

    @staticmethod
    def get_supported_data_capture():
        raise NotImplementedError()

    def process(self, data):
        raise NotImplementedError()


class ScopeSignalProcessor(PostProcessor):
    def __init__(self, run_experiment, run_data_capture, cfg):
        PostProcessor.__init__(self, run_experiment, run_data_capture, cfg)

        # Setup axes
        plt.ion()

        self._scope_fig, self._scope_axes = plt.subplots(2, sharex=True)

        self._scope_axes[0].set_title('Signals')

        self._scope_axes[1].set_xlabel('Time (us)')
        self._scope_axes[0].set_ylabel('Input Signal (V)')
        self._scope_axes[1].set_ylabel('Output Signal (V)')

        self._scope_axes_line = (None, None)

        plt.show()

    @staticmethod
    def get_supported_data_capture():
        return data_capture.PulseData,

    def process(self, data):
        time = data['result_scope_time']
        scope = (data['result_scope_in'][0], data['result_scope_out'][0])

        self._scope_axes[0].set_title("Signals {} ({:.2f}°C)".format(data['capture_id'], data['sensor_temperature']))

        for line in [1, 2]:
            if self._scope_axes_line[line] is None:
                self._scope_axes_line[line] = self._scope_axes[line].plot(time, scope[line])
            else:
                self._scope_axes_line[line].set_ydata(scope[line])

        self._scope_fig.canvas.draw()

        return data
