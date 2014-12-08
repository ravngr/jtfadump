class Experiment:
    def setup(self):
        raise NotImplementedError()

    def finish(self):
        raise NotImplementedError()

    def run(self):
        raise NotImplementedError()

    def get_state_variables(self):
        raise NotImplementedError()


class TemperatureExperiment(Experiment):
    def setup(self):
        pass


class HumidityExperiment(Experiment):
    pass


class ExposureExperiment(Experiment):
    pass
