import logging
import time
import struct

import visa

import util


class InstrumentConnector:
    """Base class for instrument connectors"""
    def __init__(self, address):
        self._address = address
        self._logger = logging.getLogger(__name__)

    def get_address(self):
        return self._address

    def write(self, data):
        raise NotImplementedError()
        
    def write_raw(self, data, raw_data):
        raise NotImplementedError()

    def query(self, data):
        raise NotImplementedError()

    def query_raw(self, data):
        raise NotImplementedError()


class VISAConnector(InstrumentConnector):
    def __init__(self, address, term_chars=None, use_bus_address=False):
        InstrumentConnector.__init__(self, address)

        resource_manager = visa.ResourceManager()

        self._use_bus_address = use_bus_address
        self._last_bus_address = False

        # Open resource
        self._instrument = resource_manager.open_resource(address)

        # Specify termination character(s) if provided
        if term_chars is not None:
            self._instrument.read_termination = term_chars
            self._instrument.write_termination = term_chars

        self._instrument.clear()
        
        self._instrument.timeout = 10000

        self._logger.info("{} Connected".format(self.get_address()))

    def select_bus_address(self, bus_address, force=False):
        if self._use_bus_address and bus_address is not None:
            if force or self._last_bus_address != bus_address:
                self._logger.debug("{} Select bus address {}".format(self.get_address(), bus_address))
                self._instrument.write("*ADR {}".format(bus_address))

                self._last_bus_address = bus_address
                
                # Wait
                time.sleep(0.5)

    def write(self, data, bus_address=None):
        self.select_bus_address(bus_address)
        self._logger.debug("{} WRITE: {}".format(self.get_address(), data))

        self._instrument.write(data)
        
    def write_raw(self, data, raw_data, bus_address=None):
        self.select_bus_address(bus_address)
        self._logger.debug("{} WRITE RAW: {}({} bytes)".format(self.get_address(), data, len(raw_data)))

        self._instrument.write_binary_values(data, raw_data, datatype='c')

    def query(self, data, bus_address=None, timeout=False):
        orig_timeout = self._instrument.timeout

        if type(timeout) is not bool:
            self._instrument.timeout = timeout

        self.select_bus_address(bus_address)
        self._logger.debug("{} QUERY: {}".format(self.get_address(), data))

        response = self._instrument.query(data)

        self._logger.debug("{} RESPONSE: {}".format(self.get_address(), response.rstrip()))

        self._instrument.timeout = orig_timeout
        return response

    def query_raw(self, data, bus_address=None, timeout=None):
        orig_timeout = self._instrument.timeout

        if timeout is not None:
            self._instrument.timeout = timeout

        self.select_bus_address(bus_address)
        self._logger.debug("{} QUERY: {}".format(self.get_address(), data))

        self._instrument.write(data)
        response = self._instrument.read_raw()

        response_len = len(response)
        self._logger.debug("{} RESPONSE: {} byte{}".format(self.get_address(), response_len,
                                                           's' if response_len == 1 else ''))

        self._instrument.timeout = orig_timeout
        return response


"""Base class for all instruments"""
class Instrument:
    def __init__(self, connector, bus_address=False):
        self._connector = connector
        self._bus_address = bus_address

    def clear(self):
        self._connector.write("*CLS", self._bus_address)

    def get_event_status_enable(self):
        return int(self._connector.ask("*ESE?", self._bus_address))

    def get_event_status_opc(self):
        return bool(self._connector.query("*OPC?", self._bus_address))

    def get_service_request(self):
        return bool(self._connector.query("*SRE?", self._bus_address))

    def get_status(self):
        return bool(self._connector.query("*STB?", self._bus_address))

    def get_event_status(self):
        return int(self._connector.ask("*ESR?", self._bus_address))

    def set_event_status_enable(self, mask):
        self._connector.write("*ESE {}".format(mask), self._bus_address)

    def set_service_request_enable(self, mask):
        self._connector.write("*SRE {}".format(mask), self._bus_address)

    def set_event_status_opc(self):
        self._connector.write("*OPC", self._bus_address)

    def get_id(self):
        return self._connector.query("*IDN?", self._bus_address)

    def get_options(self):
        return self._connector.query("*OPT?", self._bus_address)

    def reset(self):
        self._connector.write("*RST")

        # Some equipment must be re-addressed after a reset
        self._connector.select_bus_address(self._bus_address, force=True)

    def trigger(self):
        self._connector.write("*TRG", self._bus_address)

    def wait(self):
        self._connector.write("*WAI", self._bus_address)

    def wait_measurement(self):
        self._connector.query("*OPC?", self._bus_address, timeout=None)

    @staticmethod
    def _cast_bool(value):
        return "ON" if value else "OFF"


class InstrumentException(Exception):
    """ Instrument exceptions"""
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


"""Instrument definitions"""


class FrequencyCounter(Instrument):
    INPUT_IMPEDANCE = util.enum(FIFTY='50', HIGH='1E6')
    AVERAGE_TYPE = util.enum(MIN='MIN', MAX='MAX', MEAN='MEAN', STD_DEVIATION='SDEV')

    def __init__(self, connector, bus_address=False):
        Instrument.__init__(self, connector, bus_address)

        self._average = False

    def trigger(self):
        self._connector.write(":INIT")

    def get_frequency(self):
        if self._average:
            return float(self._connector.query(":CALC:DATA?"))
        else:
            return float(self._connector.query(":READ?"))

    def set_measurement_time(self, secs):
        self._connector.write(":ACQ:APER {}".format(secs))

    def set_impedance(self, impedance):
        self._connector.write(":INP:IMP {}".format(impedance))

    def set_calculate_average(self, enabled, average_type=None, count=128):
        if enabled and count > 1 and average_type is not None:
            self._connector.write(":CALC:AVER:COUN {}".format(count))
            self._connector.write(":CALC:AVER:TYPE {}".format(average_type))
            self._connector.write(":CALC:AVER:STAT ON")
            self._average = True
        else:
            self._connector.write(":AVER:STAT OFF")
            self._average = False


class NetworkAnalyzer(Instrument):
    CAL_SETUP = util.enum(RESPONSE_OPEN='OPEN', RESPONSE_SHORT='SHOR', RESPONS_THROUGH='THRU', FULL_1PORT='SOLT1',
                          FULL_2PORT='SOLT2', FULL_3PORT='SOLT3', FULL_4PORT='SOLT4')
    CAL_TYPE = util.enum(OPEN='OPEN', SHORT='SHOR', LOAD='LOAD', THROUGH='THRU', ISOLATION='ISOL')
    SNP_FORMAT = util.enum(AUTO='AUTO', LOGMAG_ANG='MA', LINMAG_ANG='DB', REAL_IMAG='RI')

    def __init__(self, connector):
        Instrument.__init__(self, connector, False)

    def trigger(self):
        # Select manual as trigger source so wait_measurement() will work properly
        self._connector.write(":TRIG:SOUR MAN")
        self._connector.write(":TRIG:SING")

    def trigger_single(self, channel=1):
        # Setup for single measurement
        self._connector.write(":INIT{}".format(channel))
        self.trigger()

    def cal_calculate(self, channel=1):
        self._connector.write(":SENS{}:CORR:COLL:SAVE".format(channel))

    def cal_measure(self, cal_type, ports=None, channel=1):
        if not ports:
            if cal_type in [self.CAL_TYPE.OPEN, self.CAL_TYPE.SHORT, self.CAL_TYPE.LOAD]:
                ports = '1'
            elif cal_type in [self.CAL_TYPE.THROUGH, self.CAL_TYPE.ISOLATION]:
                ports = '1,2'
        else:
            ports = ','.join(ports)

        self._connector.write(":SENS{}:CORR:COLL:{} {}".format(channel, cal_type, ports))

    def cal_setup(self, cal_setup, ports=None, channel=1):
        if not ports:
            if cal_setup in [self.CAL_SETUP.RESPONSE_OPEN, self.CAL_SETUP.RESPONSE_SHORT,
                             self.CAL_SETUP.RESPONS_THROUGH]:
                ports = '1'
            elif cal_setup in [self.CAL_TYPE.FULL_1PORT, self.CAL_TYPE.FULL_2PORT, self.CAL_TYPE.FULL_3PORT,
                               self.CAL_TYPE.FULL_4PORT]:
                ports = '1,2'
        else:
            ports = ','.join(ports)

        self._connector.write(":SENS{}:CORR:COLL:METH:{} {}".format(channel, cal_setup, ports))

    def data_save_snp(self, path, ports, snp_format=SNP_FORMAT.AUTO):
        port_count = len(ports)

        if port_count < 1 or port_count > 4:
            raise InstrumentException("Unsupported number of ports in SNP format")

        self._connector.write(":MMEM:STOR:SNP:TYPE:S{}P {}".format(port_count, ','.join(str(x) for x in ports)))
        self._connector.write(":MMEM:STOR:SNP:FORM {}".format(snp_format))
        self._connector.write(":MMEM:STOR:SNP \"{}\"".format(path))

    def lock(self, key_lock=False, mouse_lock=False, backlight=False):
        self._connector.write(":SYST:KLOC:KBD {}".format(self._cast_bool(not key_lock)))
        self._connector.write(":SYST:KLOC:MOUS {}".format(self._cast_bool(not mouse_lock)))
        self._connector.write(":SYST:BACK {}".format(self._cast_bool(not backlight)))

    def file_delete(self, path):
        self._connector.write(":MMEM:DEL \"{}\"".format(path))

    def file_read(self, path):
        data = self._connector.query_raw(":MMEM:TRAN? \"{}\"".format(path))

        if data[0] != '#':
            return ''

        data_start = 2 + int(data[1])
        data_size = int(data[2:data_start])

        return data[data_start:(data_start + data_size)]

    def file_write(self, path, data):
        # size = len(data)
        # prefix = "#" + str(int(math.ceil(math.log10(size)))) + str(size)
        self._connector.write_raw(":MMEM:TRAN \"{}\",".format(path), data)

    def file_transfer(self, local_path, remote_path, to_vna):
        file_mode = "rb" if to_vna else "wb"

        with open(local_path, file_mode) as f:
            if to_vna:
                data = f.read()
                self.file_write(remote_path, data)
            else:
                data = self.file_read(remote_path)
                f.write(data)

    def state_load(self, path):
        self._connector.write(":MMEM:LOAD \"{}\"".format(path))

    def state_save(self, path):
        self._connector.write(":MMEM:STOR \"{}\"".format(path))

    def clear_average(self, channel=1):
        self._connector.write(":SENS{}:AVER:CLE".format(channel))

    def get_errors(self):
        err_list = []
        err_flag = True

        while err_flag:
            err_str = self._connector.query(":SYST:ERR?")

            # Parse error string
            err_str = err_str.split(',', 1)
            err = (int(err_str[0]), err_str[1])

            if err[0] < 0:
                err_flag = False
            else:
                err_list.extend(err)

        return err_list

    def is_ready(self):
        return self._connector.query(":SYST:TEMP")[0] is '1'


class Oscilloscope(Instrument):
    _TIMEOUT_DEFAULT = 5.0
    _VOLTAGE_STEPS = [5e-3, 1e-2, 2e-2, 5e-2, 1e-1, 2e-1, 5e-1, 1e0]

    ALL_CHANNELS = 0

    CHANNEL_COUPLING = util.enum(AC='AC', DC='DC')
    CHANNEL_IMPEDANCE = util.enum(FIFTY='FIFT', HIGH='ONEM')
    IMAGE_FORMAT = util.enum(BMP='BMP', BMP8='BMP8', PNG='PNG')
    ACQUISITION_MODE = util.enum(NORMAL='NORM', AVERAGE='AVER', HIGHRES='HRES', PEAK='PEAK')
    RUN_STATE = util.enum(RUN='RUN', STOP='STOP', SINGLE='SING')
    TIME_MODE = util.enum(MAIN='MAIN', WINDOW='WIND', XY='XY', ROLL='ROLL')
    TIME_REFERENCE = util.enum(LEFT='LEFT', CENTER='CENTER', RIGHT='RIGHT')
    TRIGGER_MODE = util.enum(EDGE='EDGE', GLITCH='GLIT', PATTERN='PATT', TV='TV', DELAY='DEL', EBURST='EBUR', OR='OR',
                             RUNT='RUNT', SHOLD='SHOL', TRANSITION='TRAN', SBUS_1='SBUS1', SBUS_2='SBUS2', USB='USB')
    TRIGGER_SWEEP = util.enum(AUTO='AUTO', NORMAL='NORM')
    TRIGGER_SOURCE = util.enum(CHANNEL='CHAN', DIGITAL='DIG', EXTERNAL='EXT', LINE='LINE', WAVE_GEN='WGEN')
    TRIGGER_POLARITY = util.enum(POSITIVE='POS', NEGATIVE='NEG', EITHER='EITH', ALTERNATE='ALT')
    TRIGGER_QUALIFIER = util.enum(GREATER='GRE', LESSER='LESS', RANGE='RANG')
    WAVEFORM_FORMAT = util.enum(BYTE='BYTE', WORD='WORD')
    WAVEFORM_SOURCE = util.enum(CHANNEL='CHAN', POD='POD', BUS='BUS', FUNCTION='FUNC', MATH='MATH', WAVE_MEM='WMEM',
                                SBUS='SBUS')

    def __init__(self, connector, channels=4):
        Instrument.__init__(self, connector, False)

        self._channels = channels
        self._smart_ready = False
        self._channel_v_cache = []
        self._waveform_format = self.WAVEFORM_FORMAT.BYTE

    def setup_auto(self):
        self._connector.write(":AUT")

    def setup_default(self):
        self.reset()

    # Acquisition mode
    def set_aq_mode(self, mode, count=0):
        self._connector.write(":ACQ:TYPE {}".format(mode))

        if count > 0:
            self._connector.write(":ACQ:COUN {}".format(count))
    
    # Segmented memory functions
    def set_segment_count(self, count=1):
        if count > 1:
            self._connector.write(":ACQ:SEGM:COUN {}".format(count))
            self._connector.write(':ACQ:MODE SEGM')
        else:
            self._connector.write(':ACQ:MODE RTIM')

    # Channel configuration
    def set_channel_atten(self, channel, attenuation):
        self._connector.write(":CHAN{}:PROB {}".format(channel, attenuation))

    def set_channel_coupling(self, channel, coupling):
        self._connector.write(":CHAN{}:COUP {}".format(channel, coupling))

    def set_channel_enable(self, channel=ALL_CHANNELS, enabled=False):
        if channel == 0:
            for n in range(1, (self._channels + 1)):
                self._connector.write(":CHAN{}:DISP {}".format(n, self._cast_bool(enabled)))
        else:
            self._connector.write(":CHAN{}:DISP {}".format(channel, self._cast_bool(enabled)))

    def set_channel_label(self, channel, label):
        self._connector.write(":CHAN{}:LAB \"{}\"".format(channel, label))

    def set_channel_label_visible(self, visible):
        self._connector.write(":DISP:LAB {}".format(self._cast_bool(visible)))

    def set_channel_offset(self, channel, offset):
        self._connector.write(":CHAN{}:OFFS {}".format(channel, offset))

    def set_channel_scale(self, channel, scale):
        self._connector.write(":CHAN{}:SCAL {}".format(channel, scale))

    def set_channel_impedance(self, channel, impedance):
        self._connector.write(":CHAN{}:IMP {}".format(channel, impedance))

    # Run state
    def set_run_state(self, state):
        self._connector.write(":{}".format(state))

    # System commands
    def lock(self, locked):
        self._connector.write(":SYST:LOCK {}".format(self._cast_bool(locked)))

    def message(self, text):
        self._connector.write(":SYST:DSP \"{}\"".format(text))

    # Timebase
    def set_time_mode(self, mode):
        self._connector.write(":TIM:MODE {}".format(mode))

    def set_time_offset(self, secs):
        self._connector.write(":TIM:POS {}".format(secs))

    def set_time_reference(self, reference):
        self._connector.write(":TIM:REF {}".format(reference))

    def set_time_scale(self, secs_per_div):
        self._connector.write(":TIM:SCAL {}".format(secs_per_div))

    # Trigger
    def set_trigger_holdoff(self, secs):
        self._connector.write(":TRIG:HOLD {}".format(secs))

    def set_trigger_mode(self, mode):
        self._connector.write(":TRIG:MODE {}".format(mode))

    def set_trigger_sweep(self, sweep):
        self._connector.write(":TRIG:SWE {}".format(sweep))

    def set_trigger_edge_level(self, level, polarity=TRIGGER_POLARITY.POSITIVE):
        self._connector.write(":TRIG:SLOP {}".format(polarity))
        self._connector.write(":TRIG:LEV {}".format(level))

    def set_trigger_edge_level_auto(self, polarity=TRIGGER_POLARITY.POSITIVE):
        self._connector.write(":TRIG:SLOP {}".format(polarity))
        self._connector.write(":TRIG:LEV:ASET")

    def set_trigger_edge_source(self, source, channel=-1):
        self._connector.write(":TRIG:EDGE:SOUR {}{}".format(source, channel if channel >= 0 else ''))

    def set_trigger_glitch_range(self, minimum=0, maximum=0):
        if min > 0:
            self._connector.write(":TRIG:GLIT:GRE {}".format(minimum))

        if max > 0:
            self._connector.write(":TRIG:GLIT:LESS {}".format(maximum))

    def set_trigger_glitch_qualifier(self, qualifier):
        self._connector.write(":TRIG:GLIT:QUAL {}".format(qualifier))

    def set_trigger_glitch_source(self, source, channel=-1):
        self._connector.write(":TRIG:GLIT:SOUR {}{}".format(source, channel if channel >= 0 else ''))

    def set_trigger_glitch_level(self, level, polarity=TRIGGER_POLARITY.POSITIVE):
        self._connector.write(":TRIG:GLIT:POL {}".format(polarity))
        self._connector.write(":TRIG:GLIT:LEV {}".format(level))

    def trigger_single(self, timeout=0.0, interval=0.1):
        # self._connector.write(":ACQ:SRAT:ANAL 500E+6")
        # self._connector.write(":ACQ:POIN:ANAL 200000")
    
        # Stop capture and clear trigger event register
        self._connector.write(":STOP")
        self._connector.query(":TER?")
        self._connector.write(":DIG")
        # self._connector.write(":SING")

        t = 0

        while timeout == 0 or t <= timeout:
            trigger = self._connector.query(":TER?")

            if len(trigger) > 0 and trigger[1] == '1':
                return True

            self._connector.write(":SING")

            time.sleep(interval)

            t += interval

        raise InstrumentException('Oscilloscope trigger timeout')

    # Data capture commands
    def save_image(self, path, image_format=IMAGE_FORMAT.PNG, setup=False, color=True):
        self._connector.write(":SAVE:IMAG:FIL \"{}\"".format(path))
        self._connector.write(":SAVE:IMAG:FACT {}".format(self._cast_bool(setup)))
        self._connector.write(":SAVE:IMAG:FORM {}".format(image_format))
        self._connector.write(":SAVE:IMAG:INKS {}".format('COL' if color else 'GRAY'))
        self._connector.write(":SAVE:IMAG:STAR")

    def setup_waveform(self, waveform_format=WAVEFORM_FORMAT.BYTE):
        self._waveform_format = waveform_format

        self._connector.write(":WAV:FORM {}".format(waveform_format))
        self._connector.write(":WAV:BYT LSBF")
        self._connector.write(":WAV:UNS 1")
        # self._connector.write(":WAV:POIN:MODE MAX")
        self._connector.write(":WAV:POIN 200000")
        # self._connector.write(":WAV:POIN 10000")

    def setup_waveform_smart(self):
        self.setup_waveform(self.WAVEFORM_FORMAT.BYTE)
        self._channel_v_cache = [0] * self._channels

        self._smart_ready = True

    # Waveform capture
    def get_waveform_raw(self, source, channel=-1, segment=False):
        # Select data source
        self._connector.write(":WAV:SOUR {}{}".format(source, channel if channel >= 0 else ''))

        # Get segment count
        if segment:
            wave_count = int(self._connector.query(":WAV:SEGM:COUN?"));
        else:
            wave_count = 1
        
        wave_data = []
        
        for segment in range(0, wave_count):
            # Select segment
            self._connector.write(":ACQ:SEGM:IND {}".format(segment + 1))
            
            waveform_data = self._connector.query_raw(":WAV:DATA?")

            if waveform_data[0] != '#':
                return []

            wave_start = 2 + int(waveform_data[1])
            wave_size = int(waveform_data[2:wave_start])

            if self._waveform_format == self.WAVEFORM_FORMAT.WORD:
                wave_size /= 2

            data = []

            for x in range(0, wave_size):
                if self._waveform_format == self.WAVEFORM_FORMAT.WORD:
                    i = wave_start + x * 2
                    y = struct.unpack('<H', waveform_data[i:i + 2])[0]
                else:
                    i = wave_start + x
                    y = struct.unpack('>B', waveform_data[i])[0]

                data.append((x, y))
            
            wave_data.append(data)

        if segment:
            return wave_data
        else:
            return wave_data[0]

    def process_waveform(self, data, segment=False):
        if segment:
            # Select segment
            self._connector.write(':ACQ:SEGM:IND 1')
            
            wave_count = int(self._connector.query(":WAV:SEGM:COUN?"));
        else:
            wave_count = 1
            
            data = [data];
    
        header = self._connector.query(":WAV:PRE?").split(',')

        if len(header) != 10:
            return []

        t_step = float(header[4])
        t_origin = float(header[5])
        t_ref = int(header[6])
        v_step = float(header[7])
        v_origin = float(header[8])
        v_ref = int(header[9])

        segment_data = []
        
        for segment in range(0, wave_count):
            return_data = []

            for d in data[segment]:
                t = (d[0] - t_ref) * t_step + t_origin
                v = (d[1] - v_ref) * v_step + v_origin

                return_data.append((d[0], d[1], t, v))
            
            segment_data.append(return_data)

        if segment:
            return segment_data
        else:
            return segment_data[0]

    def get_waveform(self, channel, trigger=True, timeout=_TIMEOUT_DEFAULT, source=None, segment=False):
        if source is None:
            source = self.WAVEFORM_SOURCE.CHANNEL
    
        if trigger:
            self.trigger_single(timeout)

        data = self.get_waveform_raw(source, channel, segment=segment)
        return self.process_waveform(data, segment=segment)

    def get_waveform_auto(self, source, channel=-1):
        data = []

        for v in self._VOLTAGE_STEPS:
            self.set_channel_scale(channel, v)
            data = self.get_waveform(source, channel)

            flag = True

            for n in data:
                # Check data bounds, discard and switch ranges if clipping has occurred
                if n[1] == 0 or \
                        (self._waveform_format == self.WAVEFORM_FORMAT.BYTE and n[1] == 255) or \
                        (self._waveform_format == self.WAVEFORM_FORMAT.WORD and n[1] == 65536):
                    flag = False
                    break

            if flag:
                break

        return data

    def get_waveform_smart(self, channels, timeout=_TIMEOUT_DEFAULT, process=True):
        if not self._smart_ready:
            raise InstrumentException('Oscilloscope has not been initialized for smart capture')

        flags = [True] * len(channels)
        return_data = [0] * len(channels)
        v = self._channel_v_cache

        loop = 0

        while True in flags:
            active_channels = [(i, ch) for i, ch in enumerate(channels) if flags[i]]

            for tup in active_channels:
                n = tup[1] - 1  # Channel index (for v cache)
                ch = tup[1]     # Channel number

                # Set channel(s) volts per division
                self.set_channel_scale(ch, self._VOLTAGE_STEPS[v[n]])

            # Trigger scope
            self.trigger_single(timeout)

            # Dump data from active channels
            for tup in active_channels:
                i = tup[0]      # Return index
                n = tup[1] - 1  # Channel index (for v cache)
                ch = tup[1]     # Channel number

                data = self.get_waveform_raw(self.WAVEFORM_SOURCE.CHANNEL, ch)
                raw_data = [x[1] for x in data]

                if any((n in raw_data) for n in (0, 1, 255)):
                    # Over threshold, if previous data exists then return it, else change ranges
                    if type(return_data[i]) == list:
                        flags[i] = False

                        # Reset volts setting to correct one
                        self.set_channel_scale(ch, self._VOLTAGE_STEPS[self._channel_v_cache[n]])
                    elif (v[n] + 1) >= len(self._VOLTAGE_STEPS):
                            return_data[i] = self.process_waveform(data) if process else data
                            self._channel_v_cache[n] = v[n]
                            flags[i] = False
                    else:
                        v[n] += 1
                else:
                    # Data is good
                    return_data[i] = self.process_waveform(data) if process else data
                    self._channel_v_cache[n] = v[n]

                    # Check for lower bound, also exit if the previous data was bad (this is the first good step)
                    if v[n] == 0 or loop > 0:
                        flags[i] = False
                    else:
                        # If maximum in data is less than next step down then step down to increase resolution
                        f = max((abs(x) for x in raw_data)) - 128 + 2
                        f *= self._VOLTAGE_STEPS[v[n]] / self._VOLTAGE_STEPS[v[n] - 1]

                        if f > 127 or f < -127:
                            flags[i] = False
                        else:
                            v[n] -= 1

            loop += 1

        return return_data


class PowerSupply(Instrument):
    def __init__(self, connector, bus_address = False):
        Instrument.__init__(self, connector, bus_address)

    def clear_alarm(self):
        self._connector.write(":OUTP:PROT:CLE", self._bus_address)

    def get_current(self):
        return float(self._connector.query(":MEAS:CURR?", self._bus_address))

    def get_voltage(self):
        return float(self._connector.query(":MEAS?", self._bus_address))

    def get_power(self):
        return self.get_voltage() * self.get_current()

    def set_output_enable(self, enabled):
        self._connector.write(":OUTP {}".format(self._cast_bool(enabled)), self._bus_address)

    def set_voltage(self, voltage):
        self._connector.write(":VOLT {}".format(voltage), self._bus_address)

    def set_current(self, current):
        self._connector.write(":CURR {}".format(current), self._bus_address)


class SignalGenerator(Instrument):
    PULSEMOD_SOURCE = util.enum(INT_PULSE='INT', INT_SQUARE='INT', INT_10M='INT1', INT_40M='INT2', EXT_FRONT='EXT1',
                                EXT_BACK='EXT2')

    def set_output(self, enabled):
        self._connector.write(":OUTP:STAT {}".format(self._cast_bool(enabled)))

    def set_frequency(self, frequency):
        self._connector.write(":FREQ:MODE CW")
        self._connector.write(":FREQ {}".format(frequency))

    def set_power(self, power):
        self._connector.write(":POW {}dBm".format(power))

    def set_pulse(self, enabled):
        self._connector.write(":PULM:STAT ".format(self._cast_bool(enabled)))

    def set_pulse_source(self, source):
        self._connector.write(":PULM:SOUR {}".format(source))

        if source == self.PULSEMOD_SOURCE.INT_PULSE:
            self._connector.write(":PULM:INT:FUNC:SHAP PULS")
        elif source == self.PULSEMOD_SOURCE.INT_SQUARE:
            self._connector.write(":PULM:INT:FUNC:SHAP SQU")

    def set_pulse_count(self, count):
        self._connector.write(":PULM:COUN {}".format(count))

    def set_pulse_period(self, t):
        self._connector.write(":PULS:PER {}".format(t))

    def set_pulse_width(self, n, t):
        self._connector.write(":PULS:WIDT{} {}".format(n, t))

    def set_pulse_delay(self, n, t):
        self._connector.write(":PULS:DEL{} {}".format(n, t))
