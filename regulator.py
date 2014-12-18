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
    def __init__(self, temp_logger, temp_logger_channel, power_supply, pid_param, pid_period, voltage_limit, pid_invert=False):
        Regulator.__init__(self)

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

    def set_target(self, target):
            self._controller.set_target(target)

    def get_reading(self):
        return self.get_temperature()

    def get_target(self):
        return self._controller.get_target()

    def start(self):
        if not self._controller.is_running():
            self._controller.start()

    def stop(self):
        self._controller.stop()

    def get_current(self):
        return self._power_supply.get_current()

    def get_voltage(self):
        return self._power_supply.get_voltage()

    def get_power(self):
        return self._power_supply.get_power()

    # Function used by PID controller
    def get_temperature(self):
        return self._temp_logger.get_temperature(self._temp_logger_channel)

    def _set_voltage(self, voltage):
        if self._enabled:
            self._power_supply.set_voltage(voltage)


class HumidityRegulator(Regulator):
    pass
