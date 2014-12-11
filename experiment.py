import logging


class Experiment:
    def __init__(self, args, cfg, result_dir):
        self._args = args
        self._cfg = cfg
        self._result_dir = result_dir

    def run(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def get_state(self):
        raise NotImplementedError()


class TemperatureExperiment(Experiment):
    def __init__(self, args, cfg, result_dir):
        Experiment.__init__(self, args, cfg, result_dir)

    def setup(self):
        logging.info('Setup')

    def run(self):
        logging.info('Run')

    def stop(self):
        pass

    def get_state(self):
        pass


class HumidityExperiment(Experiment):
    pass


class ExposureExperiment(Experiment):
    pass
