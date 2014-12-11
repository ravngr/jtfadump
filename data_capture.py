import equipment
import os


class DataCapture:
    def __init__(self, result_path):
        self._result_path = result_path

    def data_read(self, capture_id):
        raise NotImplementedError()


class OscilloscopeData(DataCapture):
    pass


class VNAData(DataCapture):
    PATH_DATA = 'temp.s2p'
    PATH_STATE = 'temp.sta'

    def __init__(self, result_path, vna_connector, vna_setup_path):
        DataCapture.__init__(self, result_path)

        self._vna = equipment.NetworkAnalyzer(vna_connector)

        # Transfer setup file to VNA and then load it
        self._vna.file_transfer(vna_setup_path, self.PATH_STATE, True)
        self._vna.state_load(self.PATH_STATE)
        self._vna.file_delete(self.PATH_STATE)

    def data_read(self, capture_id):
        # Capture file name
        data_path = os.path.join(self._result_path, "vna_{}.s2p".format(capture_id))

        # Capture data


        # Save S2P file and transfer to PC
        self._vna.data_save_snp(self.PATH_DATA, [1, 2])
        self._vna.file_transfer(data_path, self.PATH_DATA, False)
        self._vna.file_delete(self.PATH_DATA)


class FrequencyCounterData(DataCapture):
    pass
