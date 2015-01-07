import equipment
import logging
import os

import scipy.io as sio

import util


class DataCapture:
    def __init__(self, args, cfg, result_dir):
        self._args = args
        self._cfg = cfg
        self._result_dir = result_dir

        self._logger = logging.getLogger(__name__)

    def save(self, n, capture_id, experiment_state):
        raise NotImplementedError()
    
    def _save_summary(self, capture_id, experiment_state):
        txt_path = os.path.join(self._result_dir, "cap_{}.txt".format(capture_id))
        
        with open(txt_path, 'w') as f:
            for key, value in experiment_state.iteritems():
                f.write("{}: {}\n".format(key, value))
        
        self._logger.info("Summary file created: {}".format(txt_path))
        
        return txt_path


class OscilloscopeData(DataCapture):
    pass


class VNAData(DataCapture):
    _PATH_DATA = 'experiment.s2p'
    _PATH_STATE = 'experiment.sta'

    #, vna_connector, vna_setup_path
    def __init__(self, args, cfg, result_dir):
        DataCapture.__init__(self, args, cfg, result_dir)

        # Get configuration
        vna_address = self._cfg.get('vna', 'address')
        self._vna_setup_path_list = self._cfg.get('vna', 'setup').split(',')

        vna_connector = equipment.VISAConnector(vna_address)
        self._vna = equipment.NetworkAnalyzer(vna_connector)

        # Lock the front panel
        if self._args.lock:
            self._vna.lock(True, True, False)

    def save(self, n, capture_id, experiment_state):
        self._save_summary(capture_id, experiment_state)

        # Capture file name
        mat_path = os.path.join(self._result_dir, "dat_{}.mat".format(capture_id))
        
        snp_frequency_full = []
        snp_data_full = []
        
        for vna_setup_path in self._vna_setup_path_list:
            vna_setup_name = os.path.splitext(os.path.basename(vna_setup_path))[0]
            snp_path = os.path.join(self._result_dir, "vna_{}_{}.s2p".format(capture_id, vna_setup_name))
            
            # Transfer setup file to VNA and then load it
            self._vna.file_transfer(vna_setup_path, self._PATH_STATE, True)
            self._vna.state_load(self._PATH_STATE)
            self._vna.file_delete(self._PATH_STATE)
            self._logger.info("Loaded VNA setup file: {}".format(vna_setup_path))

            # Capture data
            self._logger.info("Trigger capture")
            self._vna.trigger()
            self._vna.wait_measurement()

            # Save S2P file and transfer to PC
            self._vna.data_save_snp(self._PATH_DATA, [1, 2])
            self._vna.file_transfer(snp_path, self._PATH_DATA, False)
            self._vna.file_delete(self._PATH_DATA)
            self._logger.info("Transfered SNP file: {}".format(snp_path))

            # Read touchstone file
            snp_data = util.read_snp(snp_path)
            
            experiment_state['snp_type'] = snp_data[0]
            experiment_state['snp_r'] = snp_data[1]
            snp_data = snp_data[2]
            
            # Save to .mat file with state data
            snp_frequency_full.extend([d[0] for d in snp_data])
            snp_data_full.extend([d[1] for d in snp_data])
        
        experiment_state['snp_frequency'] = snp_frequency_full
        experiment_state['snp_data'] = snp_data_full

        sio.savemat(mat_path, experiment_state, do_compression=True)
        self._logger.info("MATLAB file created: {}".format(mat_path))

class FrequencyCounterData(DataCapture):
    pass
