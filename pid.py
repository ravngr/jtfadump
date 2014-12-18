import time
import threading


class Limit:
    def __init__(self, minimum, maximum):
        self._minimum = minimum
        self._maximum = maximum

    def clamp(self, n):
        if n > self._maximum:
            return self._maximum
        elif n < self._minimum:
            return self._minimum
        else:
            return n

    def set_limit(self, minimum, maximum):
        self._minimum = minimum
        self._maximum = maximum


class Controller:
    def __init__(self, in_func, out_func, initial, target, limit, pid_param, period, invert=False):
        self._running = False

        self._input = in_func
        self._output = out_func
        self._target = target
        self._limit = limit

        self._period = period

        self._invert = invert

        self._p = 0
        self._i = 0
        self._d = 0
        self.set_parameters(pid_param)

        # Setup internal variables
        out_func(initial)
        self._output_value = self._limit.clamp(initial)
        self._integral = self._limit.clamp(initial)
        self._input_prev = in_func()

        # Setup thread
        self._thread = threading.Thread(target=self._update)

    def set_target(self, target):
        self._target = target

    def set_parameters(self, pid_param):
        self._p = pid_param.p
        self._i = pid_param.i * self._period
        self._d = pid_param.d / self._period

        if self._invert:
            self._p *= -1
            self._i *= -1
            self._d *= -1

    def set_period(self, period):
        running = self.is_running()

        if running:
            self.stop()

        r = period / self._period

        self._i *= r
        self._d /= r

        self._period = period

        if running:
            self.start()

    def get_p(self):
        return self._p

    def get_i(self):
        return self._i

    def get_d(self):
        return self._d

    def get_period(self):
        return self._period

    def get_target(self):
        return self._target

    def get_output_value(self):
        return self._output_value

    def is_running(self):
        return self._thread.is_alive()

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._thread.join()
        self._running = False

    def _update(self):
        try:
            while True:
                sample_start_time = time.time()

                input_current = self._input()
                input_error = self._target - input_current

                self._integral = self._limit.clamp(self._integral + self._i * input_error)
                input_diff = self._input_prev - input_current

                self._output_value = self._limit.clamp(self._p * input_error + self._integral - self._d * input_diff)
                self._output(self._output_value)

                self._input_prev = input_current

                st = self._period - (time.time() - sample_start_time)

                if st > 0:
                    time.sleep(st)

                if not self._running:
                    break
        except():
            # Set output to zero on exception
            self._output(self._limit.clamp(0))
            raise


class ControllerParameters:
    def __init__(self, p, i, d):
        self.p = p
        self.i = i
        self.d = d
