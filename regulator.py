class Regulator:
    def get_target(self):
        raise NotImplementedError()

    def get_reading(self):
        raise NotImplementedError()

    def set_target(self, target):
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()


class TemperatureRegulator(Regulator):
    pass


class HumidityRegulator(Regulator):
    pass
