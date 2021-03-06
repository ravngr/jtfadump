import equipment
import logging
import os
import time

import numpy
import scipy.io as sio

import mks
import util


class DataCapture:
    _ROOT_CFG_SECTION = 'data'

    def __init__(self, args, cfg, result_dir):
        self._args = args
        self._cfg = cfg
        self._result_dir = result_dir

        if self._cfg.has_section(self._ROOT_CFG_SECTION):
            self._save_summary = self._cfg.getboolean(self._ROOT_CFG_SECTION, 'save_summary')
        else:
            self._save_summary = False

        self._logger = logging.getLogger(__name__)

        self._post_processing = []

    def save(self, capture_id, run_exp):
        raise NotImplementedError()

    def add_post_processor(self, post_processor):
        self._post_processing.append(post_processor)

    @staticmethod
    def _gen_file_name(prefix, extension, capture_id):
        return "{}_{}_{}.{}".format(prefix, time.strftime('%Y%m%d%H%M%S'), capture_id, extension)

    def _save_state(self, capture_id, run_exp):
        experiment_state = run_exp.get_state(capture_id)
        experiment_state['data_capture'] = self.__class__.__name__

        if not self._save_summary:
            return experiment_state

        txt_path = os.path.join(self._result_dir, DataCapture._gen_file_name('cap', 'txt', capture_id))

        with open(txt_path, 'w') as f:
            for key, value in experiment_state.iteritems():
                f.write("{}: {}\n".format(key, value))

        self._logger.info("Summary file created: {}".format(txt_path))

        return experiment_state

    def _save_mat(self, prefix, capture_id, data):
        for post in self._post_processing:
            data = post.process(data)

        mat_path = os.path.join(self._result_dir, DataCapture._gen_file_name(prefix, 'mat', capture_id))
        sio.savemat(mat_path, data, do_compression=True)
        self._logger.info("MATLAB file created: {}".format(mat_path))


class NullData(DataCapture):
    def __init__(self, args, cfg, result_dir):
        DataCapture.__init__(self, args, cfg, result_dir)

    def save(self, capture_id, run_exp):
        experiment_state = DataCapture._save_state(self, capture_id, run_exp)

        # Save results to .mat file
        self._save_mat('null_mat', capture_id, experiment_state)
        

class PulseData(DataCapture):
    _CFG_SECTION = 'pulse'

    def __init__(self, args, cfg, result_dir):
        DataCapture.__init__(self, args, cfg, result_dir)

        self._fail_threshold = self._cfg.getint(self._CFG_SECTION, 'fail_threshold')
        self._save_raw = self._cfg.getboolean(self._CFG_SECTION, 'save_raw')

        self._scope_ch_in = self._cfg.getint(self._CFG_SECTION, 'scope_ch_in')
        self._scope_ch_in_50r = self._cfg.getboolean(self._CFG_SECTION, 'scope_ch_in_50r')
        self._scope_ch_in_scale = self._cfg.getfloat(self._CFG_SECTION, 'scope_ch_in_scale')
        self._scope_ch_in_offset = self._cfg.getfloat(self._CFG_SECTION, 'scope_ch_in_offset')
        self._scope_ch_out = self._cfg.getint(self._CFG_SECTION, 'scope_ch_out')
        self._scope_ch_out_50r = self._cfg.getboolean(self._CFG_SECTION, 'scope_ch_out_50r')
        self._scope_ch_out_scale = self._cfg.getfloat(self._CFG_SECTION, 'scope_ch_out_scale')
        self._scope_ch_out_offset = self._cfg.getfloat(self._CFG_SECTION, 'scope_ch_out_offset')
        self._scope_ch_out_hr_scale = self._cfg.getfloat(self._CFG_SECTION, 'scope_ch_out_hr_scale')
        self._scope_time_div = self._cfg.getfloat(self._CFG_SECTION, 'scope_time_div')
        self._scope_trig_level = self._cfg.getfloat(self._CFG_SECTION, 'scope_trig_level')
        self._scope_trig_pol = self._cfg.getboolean(self._CFG_SECTION, 'scope_trig_pol')
        self._scope_trig_ext = self._cfg.getboolean(self._CFG_SECTION, 'scope_trig_ext')
        self._scope_trig_holdoff = self._cfg.getfloat(self._CFG_SECTION, 'scope_trig_holdoff')
        self._scope_segment = self._cfg.getint(self._CFG_SECTION, 'scope_segment')
        self._scope_align = self._cfg.getboolean(self._CFG_SECTION, 'scope_align')
        
        self._scope_acq_avg = self._cfg.getfloat(self._CFG_SECTION, 'scope_acq_avg')

        self._scope_avg = self._cfg.getint(self._CFG_SECTION, 'scope_avg')

        # Connect to oscilloscope and prepare it for captures
        self._scope_address = self._cfg.get(self._CFG_SECTION, 'scope_address').split(',')
        self._scope_init()

        # Lock the front panel
        if self._args.lock:
            self._scope.lock(True)
    
    def _scope_init(self):
        flag = False
    
        for scope_address in self._scope_address:
            try:
                self._logger.warn("Initializing scope {}".format(scope_address))
                
                scope_connector = equipment.VISAConnector(scope_address)
                self._scope = equipment.Oscilloscope(scope_connector)
            
                # Clear display
                self._scope.reset()
                self._scope.set_channel_enable(self._scope.ALL_CHANNELS, False)

                # Time scale
                self._scope.set_time_scale(self._scope_time_div)
                
                if self._scope_align:
                    self._scope.set_time_reference(self._scope.TIME_REFERENCE.LEFT)

                # Triggering
                self._scope.set_trigger_sweep(self._scope.TRIGGER_SWEEP.NORMAL)
                self._scope.set_trigger_mode(self._scope.TRIGGER_MODE.EDGE)
                
                if self._scope_trig_ext:
                    self._scope.set_trigger_edge_source(self._scope.TRIGGER_SOURCE.EXTERNAL)
                else:
                    self._scope.set_trigger_edge_source(self._scope.TRIGGER_SOURCE.CHANNEL, self._scope_ch_in)
                self._scope.set_trigger_edge_level(self._scope_trig_level,
                                                   polarity=self._scope.TRIGGER_POLARITY.POSITIVE if
                                                   self._scope_trig_pol else self._scope.TRIGGER_POLARITY.NEGATIVE)

                # Channels
                for ch in [self._scope_ch_in, self._scope_ch_out]:
                    self._scope.set_channel_enable(ch, True)
                    self._scope.set_channel_atten(ch, 1)
                    self._scope.set_channel_coupling(ch, self._scope.CHANNEL_COUPLING.DC)

                self._scope.set_channel_impedance(self._scope_ch_in, self._scope.CHANNEL_IMPEDANCE.FIFTY if
                                                  self._scope_ch_in_50r else self._scope.CHANNEL_IMPEDANCE.HIGH)
                self._scope.set_channel_impedance(self._scope_ch_out, self._scope.CHANNEL_IMPEDANCE.FIFTY if
                                                  self._scope_ch_out_50r else self._scope.CHANNEL_IMPEDANCE.HIGH)
                
                self._scope.set_channel_scale(self._scope_ch_in, self._scope_ch_in_scale)
                self._scope.set_channel_scale(self._scope_ch_out, self._scope_ch_out_scale)
                self._scope.set_channel_offset(self._scope_ch_in, self._scope_ch_in_offset)
                self._scope.set_channel_offset(self._scope_ch_out, self._scope_ch_out_offset)

                # Channel labels
                self._scope.set_channel_label_visible(True)
                self._scope.set_channel_label(self._scope_ch_in, 'IN')
                self._scope.set_channel_label(self._scope_ch_out, 'OUT')

                # Setup fast waveform dumping
                # self._scope.setup_waveform_smart()
                
                # Averaging
                if self._scope_acq_avg > 0:
                    self._scope.set_aq_mode(self._scope.ACQUISITION_MODE.AVERAGE, self._scope_acq_avg)
                    
                # self._scope._connector.write(":ACQ:SRAT:ANAL 500E+6")
                self._scope.setup_waveform(self._scope.WAVEFORM_FORMAT.BYTE)
                
                flag = True
                break
            except:
                self._logger.exception('Error while initializing scope', exc_info=True)
            
        if not flag:
            raise Exception('Failed to initialize scope')

    def save(self, capture_id, run_exp):
        experiment_state = DataCapture._save_state(self, capture_id, run_exp)

        fail_count = 0
        scope_result = {}

        scope_result_raw_key = []
        scope_result_raw = []

        # Take multiple captures for averaging
        for run in range(0, self._scope_avg):
            self._logger.info("Capture {} of {}".format(run + 1, self._scope_avg))

            try:
                capture_state = run_exp.get_state(capture_id)
                result_key = run_exp.get_result_key(capture_state)

                # scope_capture = self._scope.get_waveform_smart([self._scope_ch_in, self._scope_ch_out])
                # self._scope.set_channel_scale(self._scope_ch_out, self._scope_ch_out_scale)
                scope_capture = self._scope.get_waveform(self._scope_ch_in)
                scope_capture_time = [x[2] for x in scope_capture]
                scope_capture_in = [x[3] for x in scope_capture]
                scope_capture = self._scope.get_waveform(self._scope_ch_out, trigger=False)
                scope_capture_out = [x[3] for x in scope_capture]
                
                #self._scope.set_channel_scale(self._scope_ch_out, self._scope_ch_out_hr_scale)
                #scope_capture = self._scope.get_waveform(self._scope_ch_out)
                #scope_capture_out_hr = [x[3] for x in scope_capture]
                
                self._logger.info("Received {} samples".format(len(scope_capture_time)))

                if 'result_scope_time' not in experiment_state:
                    experiment_state['result_scope_time'] = scope_capture_time

                if self._save_raw:
                    scope_result_raw_key.append(result_key)
                    #scope_result_raw.append((scope_capture_in, scope_capture_out, scope_capture_out_hr))
                    scope_result_raw.append((scope_capture_in, scope_capture_out))

                if result_key in scope_result:
                    #scope_result[result_key].append((scope_capture_in, scope_capture_out, scope_capture_out_hr))
                    scope_result[result_key].append((scope_capture_in, scope_capture_out))
                else:
                    #scope_result[result_key] = [(scope_capture_in, scope_capture_out, scope_capture_out_hr)]
                    scope_result[result_key] = [(scope_capture_in, scope_capture_out)]
            except:
                fail_count += 1

                if fail_count > self._fail_threshold:
                    self._logger.error("Capture failure limit exceeded")
                    raise
                else:
                    self._logger.exception("Exception during capture ({} of {} allowed)".format(fail_count,
                                                                                                self._fail_threshold))
                    
                    # Reset scope
                    self._scope_init()

        self._logger.info("Capture complete, {} bin{} created".format(len(scope_result),
                                                                      '' if len(scope_result) == 1 else 's'))

        # Combine results based off sensor temperature
        experiment_in_result = []
        experiment_out_result = []
        experiment_out_hr_result = []

        result_key_name = run_exp.get_result_key_name()

        # Allocate fields in result dictionary
        experiment_state['result_avg_length'] = []

        for name in result_key_name:
            experiment_state[name] = []

        # Average across data sets in each bin
        for result_key, scope_capture_set in scope_result.iteritems():
            scope_capture_in_array = numpy.array([x[0] for x in scope_capture_set])
            experiment_in_result.append(numpy.mean(scope_capture_in_array, axis=0).tolist())

            scope_capture_out_array = numpy.array([x[1] for x in scope_capture_set])
            experiment_out_result.append(numpy.mean(scope_capture_out_array, axis=0).tolist())
            
            #scope_capture_out_hr_array = numpy.array([x[2] for x in scope_capture_set])
            #experiment_out_hr_result.append(numpy.mean(scope_capture_out_hr_array, axis=0).tolist())

            experiment_state['result_avg_length'].append(numpy.size(scope_capture_in_array, axis=0))

            for name_idx, param in enumerate(result_key):
                experiment_state[result_key_name[name_idx]].append(param)

        if self._save_raw:
            experiment_state['result_scope_raw_key'] = scope_result_raw_key
            experiment_state['result_scope_raw_in'] = [x[0] for x in scope_result_raw]
            experiment_state['result_scope_raw_out'] = [x[1] for x in scope_result_raw]

        experiment_state['result_scope_in'] = experiment_in_result
        experiment_state['result_scope_out'] = experiment_out_result
        #experiment_state['result_scope_out_hr'] = experiment_out_hr_result
        
        self._logger.debug('Processing complete')

        # Save results to .mat file
        self._save_mat('scope_mat', capture_id, experiment_state)
        self._logger.debug('Save complete')

        
class SweepData(PulseData):
    def __init__(self, args, cfg, result_dir):
        PulseData.__init__(self, args, cfg, result_dir)
        
    def _scope_init(self):
        PulseData._scope_init(self)
        
        self._scope.set_aq_mode(self._scope.ACQUISITION_MODE.HIGHRES)
        self._scope.set_trigger_holdoff(self._scope_trig_holdoff)
        self._scope.set_segment_count(self._scope_segment)

    def save(self, capture_id, run_exp):
        experiment_state = DataCapture._save_state(self, capture_id, run_exp)

        capture_state = run_exp.get_state(capture_id)
        
        scope_capture = self._scope.get_waveform(self._scope_ch_in, segment=True)
        scope_capture_time = [[x[2] for x in y] for y in scope_capture]
        scope_capture_in = [[x[3] for x in y] for y in scope_capture]
        scope_capture = self._scope.get_waveform(self._scope_ch_out, trigger=False, segment=True)
        scope_capture_out = [[x[3] for x in y] for y in scope_capture]
        
        experiment_state['result_scope_time'] = scope_capture_time
        experiment_state['result_scope_in'] = scope_capture_in
        experiment_state['result_scope_out'] = scope_capture_out
        
        self._logger.debug('Processing complete')

        # Save results to .mat file
        self._save_mat('scope_mat', capture_id, experiment_state)
        self._logger.debug('Save complete')
        

class VNAData(DataCapture):
    _CFG_SECTION = 'vna'
    _PATH_DATA = 'experiment.s2p'
    _PATH_STATE = 'experiment.sta'

    def __init__(self, args, cfg, result_dir):
        DataCapture.__init__(self, args, cfg, result_dir)

        # Get configuration
        vna_address = self._cfg.get(self._CFG_SECTION, 'vna_address')
        self._vna_setup_path_list = self._cfg.get(self._CFG_SECTION, 'vna_setup').split(',')

        vna_connector = equipment.VISAConnector(vna_address)
        self._vna = equipment.NetworkAnalyzer(vna_connector)

        # self._vna.reset()

        # Lock the front panel
        if self._args.lock:
            self._vna.lock(True, True, False)

    def save(self, capture_id, run_exp):
        experiment_state = DataCapture._save_state(self, capture_id, run_exp)

        # Capture VNA data
        snp_frequency_full = []
        snp_data_full = []

        for vna_setup_path in self._vna_setup_path_list:
            vna_setup_name = os.path.splitext(os.path.basename(vna_setup_path))[0]
            snp_path = os.path.join(self._result_dir, self._gen_file_name("vna_snp_{}".format(vna_setup_name), 's2p',
                                                                          capture_id))

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

            experiment_state['result_snp_type'] = snp_data[0]
            experiment_state['result_snp_r'] = snp_data[1]
            snp_data_merge = snp_data[2]

            # Append VNA data
            snp_frequency_full.extend([d[0] for d in snp_data_merge])
            snp_data_full.extend([d[1] for d in snp_data_merge])

        experiment_state['result_snp_frequency'] = snp_frequency_full
        experiment_state['result_snp_data'] = snp_data_full

        # Save to .mat file with state data
        self._save_mat('vna_mat', capture_id, experiment_state)


class FrequencyData(DataCapture):
    _CFG_SECTION = 'frequency'

    def __init__(self, args, cfg, result_dir):
        DataCapture.__init__(self, args, cfg, result_dir)

        counter_address = cfg.get(self._CFG_SECTION, 'counter_address')
        counter_impedance = equipment.FrequencyCounter.INPUT_IMPEDANCE.FIFTY if \
            cfg.getboolean(self._CFG_SECTION, 'counter_50r') else equipment.FrequencyCounter.INPUT_IMPEDANCE.HIGH
        counter_period = cfg.getfloat(self._CFG_SECTION, 'counter_period')
        self._counter_average = cfg.getint(self._CFG_SECTION, 'counter_average')
        self._counter_delay = cfg.getfloat(self._CFG_SECTION, 'counter_delay')

        # Connect to frequency counter
        counter_connector = equipment.VISAConnector(counter_address)
        self._counter = equipment.FrequencyCounter(counter_connector)

        self._counter.reset()
        self._counter.set_impedance(counter_impedance)
        self._counter.set_measurement_time(counter_period)

        # if counter_average > 1:
        #    self._counter.set_calculate_average(True, equipment.FrequencyCounter.AVERAGE_TYPE.MEAN, counter_average)

    def save(self, capture_id, run_exp):
        experiment_state = DataCapture._save_state(self, capture_id, run_exp)

        # Get frequency from counter
        self._counter.trigger()
        self._counter.wait_measurement()

        experiment_state['result_counter_frequency'] = []

        for run in range(self._counter_average):
            time.sleep(self._counter_delay)
            experiment_state['result_counter_frequency'].append(self._counter.get_frequency())

        self._save_mat('freq', capture_id, experiment_state)


class FrequencyDataLegacy(FrequencyData):
    _DELIMITER = ','

    def __init__(self, args, cfg, result_dir):
        FrequencyData.__init__(self, args, cfg, result_dir)

        # Create .freq file
        self._data_path = os.path.join(self._result_dir, self._gen_file_name('legacy', 'freq', '0'))

        self._logger.info("Result file: {}".format(self._data_path))

    def save(self, capture_id, run_exp):
        fail_count = 0

        while True:
            result_frequency = []

            try:
                for run in range(self._counter_average):
                    time.sleep(self._counter_delay)
                    result_frequency.append(self._counter.get_frequency())

                break
            except:
                self._logger.exception('Exception during capture')

        # Get capture time
        date_str = time.strftime('%d/%m/%Y %H:%M:%S')
        
        # Get state for post-processing
        experiment_state = DataCapture._save_state(self, capture_id, run_exp)
        experiment_state['result_counter_frequency'] = result_frequency
        
        for post in self._post_processing:
            post.process(experiment_state)

        # Take mean of measured values
        result_frequency = sum(result_frequency) / len(result_frequency)
        
        freq_str = "{:.2f}".format(result_frequency)

        with open(self._data_path, 'a') as f:
            f.write(self._DELIMITER.join([date_str, freq_str, freq_str]) + '\n')


class MKSData(DataCapture):
    _CFG_SECTION = 'mks'

    def __init__(self, args, cfg, result_dir):
        DataCapture.__init__(self, args, cfg, result_dir)

        mks_port = self._cfg.get(self._CFG_SECTION, 'port')
        self._expiry = self._cfg.getfloat(self._CFG_SECTION, 'expiry')
        self._timeout = self._cfg.getfloat(self._CFG_SECTION, 'timeout')

        # Connect to MKS
        self._mks = mks.MKSSerialMonitor(mks_port)

    def save(self, capture_id, run_exp):
        # If data is too old then wait for an update
        if self._mks.get_lag() > self._expiry:
            self._logger.info('Waiting for MKS update')

            if not self._mks.update_wait(self._timeout):
                raise mks.MKSException('MKS timed out')

        # Get existing experiment data
        experiment_state = DataCapture._save_state(self, capture_id, run_exp)

        # Append MKS data
        experiment_state.update(self._mks.get_state())

        self._save_mat('mks', capture_id, experiment_state)
