# -- coding: utf-8 --

import logging
import time

import pid


class Regulator:
    def __init__(self):
        self._enabled = True

    def get_target(self):
        raise NotImplementedError()

    def get_reading(self):
        raise NotImplementedError()

    def set_enabled(self, enabled):
        self._enabled = enabled

    def set_target(self, target):
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def state_save(self, path):
        raise NotImplementedError()

    def state_load(self, path):
        raise NotImplementedError()


class TemperatureRegulator(Regulator):
    _RAMP_THRESHOLD = 60.0
    _RAMP_SPEED = 3.0
    _RAMP_INTERVAL = 5.0

    def __init__(self, temp_logger, temp_logger_channel, power_supply, pid_param, pid_period, voltage_limit, pid_invert=False):
        Regulator.__init__(self)

        self._logger = logging.getLogger(__name__)

        # Test equipment
        self._temp_logger_channel = temp_logger_channel
        self._temp_logger = temp_logger
        self._power_supply = power_supply

        # PID controller
        initial_value = 0

        self._controller = pid.Controller(
            self.get_temperature,
            self._set_voltage,
            initial_value,
            initial_value,
            voltage_limit,
            pid_param,
            pid_period,
            pid_invert
        )

    def lock_acquire(self):
        return self._controller.lock_acquire()

    def lock_release(self):
        return self._controller.lock_release()

    def set_target(self, target):
        self._controller.set_target(target)

    def get_reading(self):
        return self.get_temperature()

    def get_target(self):
        return self._controller.get_target()

    def is_running(self):
        return self._controller.is_running()

    def get_controller_exception(self):
        return self._controller.get_thread_exception()

    def start(self):
        if not self.is_running():
            self._power_supply.set_output_enable(True)
            self._controller.start()

    def stop(self):
        if self.is_running():
            self._controller.lock_acquire()
            t = self.get_temperature()
            self._controller.lock_release()
            self._controller.set_target(t)

            # Ramp down temperature if necessary
            if t > self._RAMP_THRESHOLD:
                self._logger.warning(u"Temperature is over threshold, ramp temperature down to below {}°C".format(self._RAMP_THRESHOLD))

            while t >= self._RAMP_THRESHOLD:
                t -= self._RAMP_SPEED / (60.0 / self._RAMP_INTERVAL)
                self._logger.info(u"Set temperature: {}°C".format(t))
                self._controller.set_target(t)
                time.sleep(self._RAMP_INTERVAL)

            self._controller.stop()
            self._controller.lock_acquire()
            self._power_supply.set_output_enable(False)
            self._controller.lock_release()

    def get_current(self):
        return self._power_supply.get_current()

    def get_voltage(self):
        return self._power_supply.get_voltage()

    def get_power(self):
        return self._power_supply.get_power()

    # Functions used by PID controller
    def get_temperature(self, channel=None, attempts=3):
        while True:
            try:
                return self._temp_logger.get_temperature(channel or self._temp_logger_channel)
            except:
                attempts -= 1

                if attempts == 0:
                    raise

                self._logger.exception("Failed to read temperature ({} attempt{} remaining)".format(attempts, '' if attempts == 1 else 's'), exc_info=True)


    def _set_voltage(self, voltage):
        if self._enabled:
            self._power_supply.set_voltage(voltage)


class HumidityRegulator(Regulator):
    pass
