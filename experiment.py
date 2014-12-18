# -- coding: utf-8 --

import logging
import pickle
import time

import equipment
import regulator
import pid
import templogger


class Experiment:
    def __init__(self, args, cfg, result_dir):
        self._args = args
        self._cfg = cfg
        self._result_dir = result_dir

        self._running = True

    def run(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def is_running(self):
        return self._running

    def get_state(self):
        raise NotImplementedError()


class TemperatureExperiment(Experiment):
    _STATE_FILE = 'temperature.pickle'

    def __init__(self, args, cfg, result_dir):
        Experiment.__init__(self, args, cfg, result_dir)

        # Experiment parameters and hardware addresses
        self._temperature_min = self._cfg.get('temperature', 'temperature_min')
        self._temperature_max = self._cfg.get('temperature', 'temperature_max')
        self._temperature_step = self._cfg.get('temperature', 'temperature_step')

        self._step_time = self._cfg.get('temperature', 'step_time')

        self._experiment_loops = self._cfg.get('temperature', 'max_loops')

        logger_port = self._cfg.get('temperature', 'logger_port')
        logger_channel = self._cfg.get('temperature', 'logger_channel')

        supply_address = self._cfg.get('temperature', 'supply_address')
        supply_bus_id = self._cfg.get('temperature', 'supply_bus_id')
        supply_limit = pid.Limit(self._cfg.get('temperature', 'voltage_min'), self._cfg.get('temperature', 'voltage_max'))

        pid_param = pid.ControllerParameters(self._cfg.get('temperature', 'pid_p'), self._cfg.get('temperature', 'pid_i'), self._cfg.get('temperature', 'pid_d'))
        pid_period = self._cfg.get('temperature', 'pid_period')

        # Reload experiment state
        try:
            with open(self._STATE_FILE, 'r') as f:
                self._temperature, self._temperature_step = pickle.load(f)
            logging.info(u"Loaded existing experiment state from file")
        except:
            self._temperature = self._temperature_min

        logging.info(u"Initial temperature: {}°C, step: {}°C".format(self._temperature, self._temperature_step))

        # Setup temperature regulation hardware
        logger = templogger.TemperatureLogger(logger_port)

        supply_connector = equipment.VISAConnector(supply_address, term_chars='\r', use_bus_address=True)
        supply = equipment.PowerSupply(supply_connector, supply_bus_id)

        self._temperature_regulator = regulator.TemperatureRegulator(logger, logger_channel, supply, pid_param, pid_period, supply_limit)

    def run(self):
        # Set temperature
        self._temperature_regulator.set_target(self._temperature)
        self._temperature_regulator.start()

        # Save current state
        with open(self._STATE_FILE, 'w') as f:
            pickle.dump((self._temperature, self._temperature_step), f)

        # Wait for temperature to stabilize
        time.sleep(self._step_time)

        # Update for next step
        if (self._temperature >= self._temperature_max and self._temperature_step > 0) or (self._temperature <= self._temperature_min and self._temperature_step < 0):
            self._temperature_step = -self._temperature_step

        self._temperature += self._temperature_step

    def stop(self):
        self._temperature_regulator.stop()

    def get_state(self):
        return {
            'target_temperature': self._temperature_regulator.get_target(),
            'sensor_temperature': self._temperature_regulator.get_temperature(),
            'supply_voltage': self._temperature_regulator.get_voltage(),
            'supply_current': self._temperature_regulator.get_current()
        }


class HumidityExperiment(Experiment):
    pass


class ExposureExperiment(Experiment):
    pass
