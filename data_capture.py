import equipment
import os


class DataCapture:
    def __init__(self, args, cfg, result_dir):
        self._args = args
        self._cfg = cfg
        self._result_dir = result_dir

    def data_read(self, n, capture_id, experiment_state):
        raise NotImplementedError()


class OscilloscopeData(DataCapture):
    pass


class VNAData(DataCapture):
    _PATH_DATA = 'temp.s2p'
    _PATH_STATE = 'temp.sta'

    #, vna_connector, vna_setup_path
    def __init__(self, args, cfg, result_dir):
        DataCapture.__init__(self, args, cfg, result_dir)

        # Get configuration
        vna_address = self._cfg.get('vna', 'address')
        vna_setup_path = self._cfg.get('vna', 'setup')

        vna_connector = equipment.VISAConnector(vna_address)
        self._vna = equipment.NetworkAnalyzer(vna_connector)

        # Transfer setup file to VNA and then load it
        self._vna.file_transfer(vna_setup_path, self._PATH_STATE, True)
        self._vna.state_load(self._PATH_STATE)
        self._vna.file_delete(self._PATH_STATE)

        # Lock the front panel
        if self._args.lock:
            self._vna.lock(True, True, False)

    def data_read(self, n, capture_id, experiment_state):
        # Capture file name
        data_path = os.path.join(self._result_dir, "vna_{}.s2p".format(capture_id))

        # Capture data
        self._vna.trigger_single()
        self._vna.wait_measurement()

        # Save S2P file and transfer to PC
        self._vna.data_save_snp(self._PATH_DATA, [1, 2])
        self._vna.file_transfer(data_path, self._PATH_DATA, False)
        self._vna.file_delete(self._PATH_DATA)


class FrequencyCounterData(DataCapture):
    pass
