# -- coding: utf-8 --

import logging
import pickle
import time
import datetime

import equipment
import pid
import regulator
import templogger


class ExperimentException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


class Experiment:
    _CFG_SECTION = 'experiment'

    def __init__(self, args, cfg, result_dir):
        self._args = args
        self._cfg = cfg
        self._result_dir = result_dir

        self._logger = logging.getLogger(__name__)

        if 'max_loops' in [x[0] for x in cfg.items(self._CFG_SECTION)]:
            self._experiment_loops = self._cfg.getint(self._CFG_SECTION, 'max_loops')
        else:
            self._experiment_loops = None
        

    def step(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def is_running(self):
        if self._experiment_loops is None:
            return True
    
        return self._experiment_loops > 0

    def get_remaining_loops(self):
        if self._experiment_loops is None:
            return False
    
        return self._experiment_loops

    def set_remaining_loops(self, remaining_loops):
        self._experiment_loops = remaining_loops

    def finish_loop(self):
        if self._experiment_loops is not None:
            self._experiment_loops -= 1

    def get_result_key(self, state=None):
        raise NotImplementedError()

    def get_result_key_name(self):
        raise NotImplementedError()

    def get_state(self, capture_id):
        state = {
            'experiment': self.__class__.__name__,
            'capture_id': capture_id,
            'capture_time': time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime()),
            'capture_timestamp': time.time()
        }
        
        return state


class TemperatureExperiment(Experiment):
    _CFG_SECTION = 'temperature'
    _STATE_FILE = 'temperature.pickle'

    def __init__(self, args, cfg, result_dir):
        Experiment.__init__(self, args, cfg, result_dir)

        # Experiment parameters and hardware addresses
        self._temperature_min = self._cfg.getfloat(self._CFG_SECTION, 'temperature_min')
        self._temperature_max = self._cfg.getfloat(self._CFG_SECTION, 'temperature_max')
        self._temperature_step = self._cfg.getfloat(self._CFG_SECTION, 'temperature_step')
        self._temperature_repeat = self._cfg.getfloat(self._CFG_SECTION, 'temperature_repeat')
        self._temperature_n = 0

        self._step_time = self._cfg.getint(self._CFG_SECTION, 'step_time')

        logger_port = self._cfg.get('temperature', 'logger_port')
        logger_ambient_channel = self._cfg.getint(self._CFG_SECTION, 'logger_ambient_channel')
        logger_sensor_channel = self._cfg.getint(self._CFG_SECTION, 'logger_sensor_channel')

        supply_address = self._cfg.get(self._CFG_SECTION, 'supply_address')
        supply_bus_id = self._cfg.getint(self._CFG_SECTION, 'supply_bus_id')
        supply_limit = pid.Limit(self._cfg.getfloat(self._CFG_SECTION, 'voltage_min'), self._cfg.getfloat(self._CFG_SECTION, 'voltage_max'))

        pid_param = pid.ControllerParameters(self._cfg.getfloat(self._CFG_SECTION, 'pid_p'), self._cfg.getfloat(self._CFG_SECTION, 'pid_i'), self._cfg.getfloat(self._CFG_SECTION, 'pid_d'))
        pid_period = self._cfg.getfloat(self._CFG_SECTION, 'pid_period')

        # Reload experiment state
        try:
            with open(self._STATE_FILE, 'r') as f:
                self._temperature, self._temperature_step = pickle.load(f)
            self._logger.info("Loaded existing experiment state from file")
        except:
            self._temperature = self._temperature_min

        self._logger.info(u"Initial temperature: {}°C, step: {}°C".format(self._temperature, self._temperature_step))

        # Setup temperature regulation hardware
        logger = templogger.TemperatureLogger(logger_port)

        supply_connector = equipment.VISAConnector(supply_address, term_chars='\r', use_bus_address=True)
        supply = equipment.PowerSupply(supply_connector, supply_bus_id)

        self._logger_ambient_channel = logger_ambient_channel
        self._logger_sensor_channel = logger_sensor_channel
        self._temperature_regulator = regulator.TemperatureRegulator(logger, logger_sensor_channel, supply, pid_param, pid_period, supply_limit)

    def step(self):
        self._temperature_n -= 1
    
        if self._temperature_n <= 0:
            # Set temperature
            self._logger.info(u"Target temperature: {}°C".format(self._temperature))
            self._temperature_regulator.set_target(self._temperature)
            self._temperature_regulator.start()

            # Save current state
            with open(self._STATE_FILE, 'w') as f:
                pickle.dump((self._temperature, self._temperature_step), f)
                
            self._temperature_n = self._temperature_repeat
            

        # Wait for temperature to stabilize
        resume_time = datetime.datetime.now() + datetime.timedelta(seconds=self._step_time)
        self._logger.info("Wait to {:%H:%M:%S}".format(resume_time))

        try:
            time.sleep(self._step_time)
        except (KeyboardInterrupt):
            self._logger.info("Wait interrupted")
            user_input = raw_input("Continue? ")
            if not user_input.lower() in ['y', 'yes', 'true', '1']:
                raise

        # Check that the regulator is still working
        if not self._temperature_regulator.is_running():
            self._logger.error('Temperature regulator is not running')
            raise self._temperature_regulator.get_controller_exception()

        # Update for next step
        if (self._temperature >= self._temperature_max and self._temperature_step > 0) or (self._temperature <= self._temperature_min and self._temperature_step < 0):
            self._temperature_step = -self._temperature_step

        self._temperature += self._temperature_step

    def stop(self):
        self._logger.info("Stopping temperature regulator")
        self._temperature_regulator.stop()

    def get_result_key(self, state=None):
        if not state:
            self._temperature_regulator.lock_acquire()

            key = self._temperature_regulator.get_temperature(),

            self._temperature_regulator.lock_release()
        else:
            key = state['sensor_temperature'],

        return key

    def get_result_key_name(self):
        return 'result_sensor_temperature',

    def get_state(self, capture_id):
        parent_state = Experiment.get_state(self, capture_id)

        self._temperature_regulator.lock_acquire()

        state = {
            'target_temperature': self._temperature_regulator.get_target(),
            'ambient_temperature': self._temperature_regulator.get_temperature(self._logger_ambient_channel),
            'sensor_temperature': self._temperature_regulator.get_temperature(),
            'supply_voltage': self._temperature_regulator.get_voltage(),
            'supply_current': self._temperature_regulator.get_current()
        }

        self._temperature_regulator.lock_release()

        return dict(state.items() + parent_state.items())


class HumidityExperiment(Experiment):
    def get_result_key_name(self):
        return ('sensor_temperature', 'sensor_humidity')


class ExposureExperiment(Experiment):
    def get_result_key_name(self):
        return ('sensor_temperature', 'sensor_analyte')


class TimeExperiment(Experiment):
    _CFG_SECTION = 'time'

    def __init__(self, args, cfg, result_dir):
        Experiment.__init__(self, args, cfg, result_dir)

        self._step_time = self._cfg.getint(self._CFG_SECTION, 'step_time')

    def step(self):
        # Just sleep until next time increment
        try:
            time.sleep(self._step_time)
        except KeyboardInterrupt:
            self._logger.info("Wait interrupted")
            user_input = raw_input("Continue? ")
            if not user_input.lower() in ['y', 'yes', 'true', '1']:
                raise

    def stop(self):
        pass

    def get_result_key(self, state=None):
        return 0,

    def get_result_key_name(self):
        return 'result_n',


class InfiniteExperiment(TimeExperiment):
    def __init__(self, args, cfg, result_dir):
        TimeExperiment.__init__(self, args, cfg, result_dir)
        
        self._experiment_loops = None
