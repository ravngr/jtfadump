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
    def __init__(self, input, output, start, target, limit, Kp, Ki, Kd, t, invert = False):
        self._running = False;

        self._input = input
        self._output = output
        self._target = target

        self._limit = limit

        self._Kp = Kp
        self._Ki = Ki
        self._Kd = Kd

        self._sample_time = t

        self._invert = invert

        # Setup internal variables
        output(start)
        self._i = limit.clamp(start)
        self._last_in = input()

        # Setup thread
        self._thread = threading.Thread(target=self._update)

    def set_target(self, target):
        self._target = target

    def set_tuning(self, Kp, Ki, Kd):
        self._Kp = Kp
        self._Ki = Ki * self._sample_time
        self._Kd = Kd / self._sample_time

        if self._invert:
            self._Kp *= -1
            self._Ki *= -1
            self._Kd *= -1

    def set_sample_time(self, t):
        self.stop()

        r = t / self._sample_time

        self._Ki *= r
        self._Kd /= r

        self._sample_time = t

        self._start()

    def get_tuning_Kp(self):
        return self._Kp

    def get_tuning_Ki(self):
        return self._Ki

    def get_tuning_Kd(self):
        return self._Kd

    def get_sample_time(self):
        return self._sample_time

    def start(self):
        self._thread.start()
        self._running = True

    def stop(self):
        self._running = False
        self._thread.join()

    def _update(self):
        while self._running:
            t = time.time()

            v = self._input()
            err = self._target - v

            self._i += self._limit.clamp(self._Ki * err)
            dv = self._last_in - v

            self._output(self._limit.clamp(self._Kp * err + self._i - self._Kd * dv))

            self._last_in = v

            st = self._sample_time - (time.time() - t)

            if st > 0:
                time.sleep(st)
