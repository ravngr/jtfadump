import time
import threading


class Limit:
    def __init__(self, min, max):
        self.set_limit(min, max)

    def clamp(self, n):
        if n > self._max:
            return self._max
        elif n < self._min:
            return self._min
        else:
            return n

    def set_limit(self, min, max):
        self._min = min
        self._max = max


class PID:
    def __init__(self, in_func, out_func, initial, target, limit, Kp, Ki, Kd, period, invert=False):
        self._running = False

        self._input = in_func
        self._output = out_func
        self._target = target
        self._limit = limit

        self._period = period

        self._invert = invert

        self.set_tuning(Kp, Ki, Kd)

        # Setup internal variables
        out_func(initial)
        self._output_value = self._limit.clamp(initial)
        self._i = self._limit.clamp(initial)
        self._last_in = in_func()

        # Setup thread
        self._thread = threading.Thread(target=self._update)

    def set_target(self, target):
        self._target = target

    def set_tuning(self, Kp, Ki, Kd):
        self._Kp = Kp
        self._Ki = Ki * self._period
        self._Kd = Kd / self._period

        if self._invert:
            self._Kp *= -1
            self._Ki *= -1
            self._Kd *= -1

    def set_period(self, period):
        running = self.is_running()

        if running:
            self.stop()

        r = period / self._period

        self._Ki *= r
        self._Kd /= r

        self._period = period

        if running:
            self.start()

    def get_Kp(self):
        return self._Kp

    def get_Ki(self):
        return self._Ki

    def get_Kd(self):
        return self._Kd

    def get_period(self):
        return self._period

    def get_output_value(self):
        return self._output_value

    def is_running(self):
        return self._thread.is_alive()

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False
        self._thread.join()

    def _update(self):
        try:
            while True:
                t = time.time()

                v = self._input()
                err = self._target - v

                self._i += self._limit.clamp(self._Ki * err)
                dv = self._last_in - v

                self._output_value = self._limit.clamp(self._Kp * err + self._i - self._Kd * dv)
                self._output(self._output_value)

                self._last_in = v

                st = self._period - (time.time() - t)

                if st > 0:
                    time.sleep(st)

                if not self._running:
                    break
        except():
            # Set output to zero on exception
            self._output(self._limit.clamp(0))
