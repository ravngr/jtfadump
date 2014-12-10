import equipment
import templogger
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


class TemperatureRegulator(Regulator):
    def __init__(self, temp_logger_port, temp_logger_channel, power_supply_address, pid_param, pid_period, voltage_limit, power_supply_bus_address=False, pid_invert=False):
        Regulator.__init__(self)

        # Test equipment
        self._temp_logger_channel = temp_logger_channel
        self._temp_logger = templogger.TemperatureLogger(temp_logger_port)
        self._power_supply = equipment.PowerSupply(power_supply_address, power_supply_bus_address)

        # PID controller
        self._controller = pid.Controller(
            self.get_temperature(),
            self._power_supply.set_voltage,
            0,
            0,
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
        self._controller.start()

    def stop(self):
        self._controller.stop()

    def get_current(self):
        return self._power_supply.get_current()

    def get_temperature(self):
        return self._temp_logger.get_temperature(self._temp_logger_channel)

    def get_voltage(self):
        return self._power_supply.get_voltage()

    def get_power(self):
        return self._power_supply.get_power()


class HumidityRegulator(Regulator):
    pass
