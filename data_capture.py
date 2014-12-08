__author__ = 's3201759'

class DataCapture:
    def read_data(self):
        raise NotImplementedError()


class OscilloscopeData(DataCapture):
    pass


class VNAData(DataCapture):
    pass


class FrequencyCounterData(DataCapture):
    pass
