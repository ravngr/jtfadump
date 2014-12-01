import logging
import math
import struct
import time
import util

import serial
import visa

_debug = True

def _cast_bool(c):
    return 'ON' if c else 'OFF'

_logger_name = 'visa'

class BaseInstrument:
    """Parent class for instruments"""
    def __init__(self, id):
        self._log = logging.getLogger(_logger_name)
        self._dev = visa.instrument(id)
        self._dev.clear()

    def reset(self):
        self._dev.write('*RST')

    def wait(self):
        self._dev.ask('*OPC?')

    def get_id(self):
        return self.ask('*IDN?')

    def ask(self, cmd):
        response = self._dev.ask(cmd)
        self._log.debug('%s <> %s (%i bytes)' % (self._dev.resource_name, cmd, len(response)))
        return response
    
    def ask_raw(self, cmd):
        self._dev.write(cmd)
        response = self._dev.read_raw()
        self._log.debug('%s <> %s (%i bytes)' % (self._dev.resource_name, cmd, len(response)))
        return response

    def write(self, cmd):
        self._log.debug('%s <- %s' % (self._dev.resource_name, cmd))
        self._dev.write(cmd)

class Counter(BaseInstrument):
    """Frequency counter"""
    impedance = util.enum(FIFTY='50', HIGH='1E6')

    def get_freq(self):
        return float(self.ask(':READ?'))

    def set_meas_time(self, t):
        self.write(':ACQ:APER %f' % (t))

    def set_z(self, impedance):
        self.write(':INP:IMP %s' % (impedance))

class Scope(BaseInstrument):
    """Oscilloscope"""
    channels = 4

    #_volt_step = [ 5e-3, 1e-2, 2e-2, 5e-2, 1e-1, 2e-1, 5e-1, 1.0, 2.0, 5.0 ]
    _volt_step = [ 5e-3, 1e-2, 2e-2, 5e-2, 1e-1, 2e-1 ]

    ch_couple = util.enum(AC='AC', DC='DC')
    ch_impedance = util.enum(FIFTY='FIFT', HIGH='ONEM')
    img_format = util.enum(BMP='BMP', BMP8='BMP8', PNG='PNG')
    mode_aq = util.enum(NORMAL='NORM', AVERAGE='AVER', HIGHRES='HRES', PEAK='PEAK')
    mode_run = util.enum(RUN='RUN', STOP='STOP', SINGLE='SING')
    time_mode = util.enum(MAIN='MAIN', WINDOW='WIND', XY='XY', ROLL='ROLL')
    time_ref = util.enum(LEFT='LEFT', CENTER='CENTER', RIGHT='RIGHT')
    trigger_mode = util.enum(EDGE='EDGE', GLITCH='GLIT', PATTERN='PATT', TV='TV', DELAY='DEL', EBURST='EBUR', OR='OR', RUNT='RUNT', SHOLD='SHOL', TRANSITION='TRAN', SBUS_1='SBUS1', SBUS_2='SBUS2', USB='USB')
    trigger_sweep = util.enum(AUTO='AUTO', NORMAL='NORM')
    trigger_source = util.enum(CHANNEL='CHAN', DIGITAL='DIG', EXTERNAL='EXT', LINE='LINE', WAVE_GEN='WGEN')
    trigger_polarity = util.enum(POSITIVE='POS', NEGATIVE='NEG', EITHER='EITH', ALTERNATE='ALT')
    trigger_qualifier = util.enum(GREATER='GRE', LESSER='LESS', RANGE='RANG')
    wave_source = util.enum(CHANNEL='CHAN', POD='POD', BUS='BUS', FUNCTION='FUNC', MATH='MATH', WAVE_MEM='WMEM', SBUS='SBUS')

    # Setup
    def setup_auto(self):
        self.write(":AUT")

    def setup_default():
        self.reset()

    # Acquisition mode
    def set_aq_mode(self, mode, count=0):
        self.write(":ACQ:TYPE " + mode)

        if count > 0:
            self.write(":ACQ:COUN " + str(count))

    # Channel configuration
    def set_ch_atten(self, channel, attenuation):
        self.write(":CHAN" + str(channel) + ":PROB " + str(attenuation))

    def set_ch_couple(self, channel, coupling):
        self.write(":CHAN" + str(channel) + ":COUP " + coupling)

    def set_ch_enable(self, channel, enabled=False):
        if channel == 0:
            for n in range(1, (self.channels + 1)):
                self.write(":CHAN" + str(n) + ":DISP " + _cast_bool(enabled))
        else:
            self.write(":CHAN" + str(channel) + ":DISP " + _cast_bool(enabled))

    def set_ch_label(self, channel, label):
        self.write(":CHAN" + str(channel) + ":LAB \"" + str(label) + "\"")

    def set_ch_label_visible(self, visible):
        self.write(":DISP:LAB " + _cast_bool(visible))

    def set_ch_offset(self, channel, offset):
        self.write(":CHAN" + str(channel) + ":OFFS " + str(offset))

    def set_ch_scale(self, channel, scale):
        self.write(":CHAN" + str(channel) + ":SCAL " + str(scale))

    def set_ch_z(self, channel, impedance):
        self.write(":CHAN" + str(channel) + ":IMP " + impedance)

    # Start/stop/single
    def set_run(self, mode):
        self.write(":" + mode)

    # System
    def set_sys_locked(self, locked):
        self.write(":SYST:LOCK " + _cast_bool(locked))

    def sys_message(self, msg):
        self.write(":SYST:DSP \"" + msg + "\"")

    def sys_img(self, filename, format, setup, colour):
        self.write("SAVE:FIL \"" + filename + "\"")
        self.write("SAVE:IMAG:FACT " + _cast_bool(setup))
        self.write("SAVE:IMAG:FORM " + format)
        self.write("SAVE:IMAG:PAL " + ('COL' if colour else 'GRAY'))
        self.write("SAVE:IMAG:INKS " + _cast_bool(not colour))
        self.write("SAVE:IMAG:STAR")

    # Timebase
    def set_time_mode(self, mode):
        self.write(":TIM:MODE " + mode)

    def set_time_offset(self, t):
        self.write(":TIM:POS " + str(t))

    def set_time_reference(self, reference):
        self.write(":TIM:REF " + reference)

    def set_time_scale(self, t):
        self.write(":TIM:SCAL " + str(t))

    # Trigger
    def set_trigger_holdoff(self, t):
        self.write(":TRIG:HOLD " + str(t))

    def set_trigger_mode(self, mode):
        self.write(":TRIG:MODE " + mode)

    def set_trigger_sweep(self, sweep):
        self.write(":TRIG:SWE " + sweep)

    def set_trigger_edge_level(self, level, polarity=trigger_polarity.POSITIVE):
        self.write(":TRIG:SLOP " + polarity)
        self.write(":TRIG:LEV " + str(level))

    def set_trigger_edge_level_auto(self, polarity=trigger_polarity.POSITIVE):
        self.write(":TRIG:SLOP " + polarity)
        self.write(":TRIG:LEV:ASET")

    def set_trigger_edge_source(self, source, channel=-1):
        if channel >= 0:
            self.write(":TRIG:EDGE:SOUR " + source + str(channel))
        else:
            self.write(":TRIG:EDGE:SOUR " + source)

    def set_trigger_glitch_range(self, min=0, max=0):
        if min > 0:
            self.write(":TRIG:GLIT:GRE " + str(min))

        if max > 0:
            self.write(":TRIG:GLIT:LESS " + str(max))

    def set_trigger_glitch_qualifier(self, qualifier):
        self.write(":TRIG:GLIT:QUAL " + qualifier)

    def set_trigger_glitch_source(self, source, channel=-1):
        if channel >= 0:
            self.write(":TRIG:GLIT:SOUR " + source + str(channel))
        else:
            self.write(":TRIG:GLIT:SOUR " + source)

    def set_trigger_glitch_level(self, level, polarity=trigger_polarity.POSITIVE):
        self.write(":TRIG:GLIT:POL " + polarity)
        self.write(":TRIG:GLIT:LEV " + str(level))

    def trigger(self):
        self.write("*TRG")

    def trigger_single(self, timeout = 0, interval = 0.1):
        self.write(":STOP")
        self.ask(":TER?")
        self.write(":SING")

        t = 0

        while timeout == 0 or t <= timeout:
            trigger = self.ask(":TER?")

            if len(trigger) > 0 and trigger[1] == '1':
                return True

            self.write(":SING")

            time.sleep(interval)

            t += interval

        raise Exception('Scope trigger timeout')

    def trigger_window(self, window, timeout = 0):
        self.write(":STOP")
        self.ask(":TER?")

        t = 0

        while timeout == 0 or t <= timeout:
            self.write(":RUN")
            time.sleep(window)
            self.write(":STOP")

            trigger = self.ask(":TER?")

            if len(trigger) > 0 and trigger[1] == '1':
                return True

            t += window

        raise Exception('Scope trigger timeout')

    def get_waveform_init(self, highres = False):
        self._highres = highres

        self.write(":WAV:FORM " + ('WORD' if highres else 'BYTE'))
        self.write(":WAV:BYT LSBF")    # LSB first
        self.write(":WAV:UNS 1")    # Unsigned
        self.write(":WAV:POIN:MODE MAX")
        self.write(":WAV:POIN MAX")

    # Waveform
    def get_waveform(self, source, channel = -1, trigger=True, timeout=5):
        if trigger:
            self.trigger_single(timeout)

        if channel >= 0:
            self.write(":WAV:SOUR " + source + str(channel))
        else:
            self.write(":WAV:SOUR " + source)

        format = self.ask(":WAV:PRE?").split(',')

        if len(format) != 10:
            return []

        x_step = float(format[4])
        x_origin = float(format[5])
        x_ref = int(format[6])
        y_step = float(format[7])
        y_origin = float(format[8])
        y_ref = int(format[9])

        waveform = self.ask(":WAV:DATA?")

        if waveform[0] != '#':
            return []

        wave_start = 2 + int(waveform[1])
        wave_size = int(waveform[2:wave_start])

        if self._highres:
            wave_size /= 2

        data = []

        for n in range(0, wave_size):
            if self._highres:
                s = wave_start + n * 2
                m = struct.unpack('>H', waveform[s:s + 2])[0]
            else:
                s = wave_start + n
                m = struct.unpack('>B', waveform[s])[0]

            x = (n - x_ref) * x_step + x_origin
            y = (m - y_ref) * y_step + y_origin

            data.append((n, m, x, y))

        return data

    def get_waveform_raw(self, source, channel = -1):
        if channel >= 0:
            self.write(":WAV:SOUR " + source + str(channel))
        else:
            self.write(":WAV:SOUR " + source)

        waveform = self.ask_raw(":WAV:DATA?")

        if waveform[0] != '#':
            return []

        wave_start = 2 + int(waveform[1])
        wave_size = int(waveform[2:wave_start])

        data = []

        for n in range(0, wave_size):
            s = wave_start + n
            m = struct.unpack('>B', waveform[s])[0]

            data.append((n, m))

        return data

    def get_waveform_raw_process(self, data):
        format = self.ask(":WAV:PRE?").split(',')

        if len(format) != 10:
            return []

        x_step = float(format[4])
        x_origin = float(format[5])
        x_ref = int(format[6])
        y_step = float(format[7])
        y_origin = float(format[8])
        y_ref = int(format[9])

        return_data = []

        for d in data:
            n = d[0]
            m = d[1]
            x = (n - x_ref) * x_step + x_origin
            y = (m - y_ref) * y_step + y_origin

            return_data.append((n, m, x, y))

        return return_data

    def get_waveform_smart(self, source, channel = -1):
        for v in self._volt_step:
            self.set_ch_scale(channel, v)
            data = self.get_waveform(source, channel)

            flag = True

            for n in data:
                # Check data bounds, discard and switch ranges if clipping has occurred
                if n[1] == 0 or (not self._highres and n[1] == 255) or (self._highres and n[1] == 65536):
                    flag = False
                    break

            if flag:
                break

        return data

    def get_waveform_smart_multichannel(self, channels):
        # Make a copy of the channel list so we can edit it
        channels = list(channels)

        return_data = []

        # Allocate elements in the list for each channel
        for i in channels:
            return_data[i] = []

        for v in self._volt_step:
            # Set voltage on all active channels
            for n in channels:
                self.set_ch_scale(n, v)

            # Dump data on all active channels
            for i, n in enumerate(channels):
                data = self.get_waveform(self.wave_source.CHANNEL, n)

                flag = True

                for n in data:
                    if n[1] == 0 or (not self._highres and n[1] == 255) or (self._highres and n[1] == 65536):
                        flag = False
                        break

                if flag:
                    return_data[i] = data

            # Remove completed channels from the list
            for i, data in enumerate(return_data):
                del channels[i]

            if len(channels) == 0:
                break

        return return_data

    def get_waveform_smart_multichannel_fast_init(self):
        self.get_waveform_init(False)
        self._channel_v_cache = [0] * self.channels

    def get_waveform_smart_multichannel_fast(self, channels, timeout = 5.0, process = True):
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
                self.set_ch_scale(ch, self._volt_step[v[n]])

            # Trigger scope
            self.trigger_single(timeout)

            # Dump data from active channels
            for tup in active_channels:
                i = tup[0]      # Return index
                n = tup[1] - 1  # Channel index (for v cache)
                ch = tup[1]     # Channel number

                data = self.get_waveform_raw(self.wave_source.CHANNEL, ch)
                raw_data = [x[1] for x in data]

                #if 0 in raw_data or 1 in raw_data or 255 in raw_data:
                if any(i in raw_data for i in (0, 1, 255)):
                    # Over threshold, if previous data exists then return it, else change ranges
                    if type(return_data[i]) == list:
                        flags[i] = False

                        # Reset volts setting to correct one
                        self.set_ch_scale(ch, self._volt_step[self._channel_v_cache[n]])
                    elif (v[n] + 1) >= len(self._volt_step):
                            return_data[i] = self.get_waveform_raw_process(data) if process else data
                            self._channel_v_cache[n] = v[n]
                            flags[i] = False
                    else:
                        v[n] += 1
                else:
                    # Data is good
                    return_data[i] = self.get_waveform_raw_process(data) if process else data
                    self._channel_v_cache[n] = v[n]

                    # Check for lower bound, also exit if the previous data was bad (this is the first good step)
                    if v[n] == 0 or loop > 0:
                        flags[i] = False
                    else:
                        # If the maximum of the data is less than the next step down then we can step down to increase resolution
                        f = max((abs(x) for x in raw_data)) - 128 + 2
                        f *= self._volt_step[v[n]] / self._volt_step[v[n] - 1]

                        if f > 127 or f < -127:
                            flags[i] = False
                        else:
                            v[n] -= 1

            loop += 1

        return return_data

class PowerSupply(BaseInstrument):
    def __init__(self, id):
        BaseInstrument.__init__(self, id)

        self._dev.term_chars = '\r'
        self.write("*ADR 1")

    def reset(self):
        self.write("*RST")
        self.write("*ADR 1")
    
    def clear_alarm(self):
        self.write(":OUTP:PROT:CLE")

    def get_voltage(self):
        return self.ask(":MEAS?")

    def get_current(self):
        return self.ask(":MEAS:CURR?")

    def get_power(self):
        return self.get_voltage() * self.get_power()
    
    def set_alarm_mask(self, mask):
        self.write(":SYST:PROT " + str(mask))
    
    def set_sys_locked(self, lock):
        self.write(":SYST:REM:STAT " + "REM" if lock else "LOC")

    def set_voltage(self, voltage):
        self.write(":VOLT " + str(voltage))

    def set_current(self, current):
        self.write(":CURR " + str(current))

    def set_output(self, enabled):
        self.write(":OUTP " + _cast_bool(enabled))

class SignalGen(BaseInstrument):
    pulsemod_source = util.enum(INT_PULSE='INT', INT_SQUARE='INT', INT_10M='INT1', INT_40M='INT2', EXT_FRONT='EXT1', EXT_BACK='EXT2')

    def set_output(self, enabled):
        self.write(":OUTP:STAT " + _cast_bool(enabled))

    def set_frequency(self, frequency):
        self.write(":FREQ:MODE CW")
        self.write(":FREQ " + str(frequency))

    def set_power(self, power):
        self.write(":POW " + str(power) + "dBm")

    def set_pulse(self, enabled):
        self.write(":PULM:STAT " + _cast_bool(enabled))

    def set_pulse_source(self, source, pulse=True):
        self.write(":PULM:SOUR " + source)

        if source == self.pulsemod_source.INT_PULSE:
            self.write(":PULM:INT:FUNC:SHAP PULS")
        elif source == self.pulsemod_source.INT_SQUARE:
            self.write(":PULM:INT:FUNC:SHAP SQU")

    def set_pulse_count(self, count):
        self.write(":PULM:COUN " + str(count))

    def set_pulse_period(self, t):
        self.write(":PULS:PER " + str(t))

    def set_pulse_width(self, n, t):
        self.write(":PULS:WIDT" + str(n) + " " + str(t))

    def set_pulse_delay(self, n, t):
        self.write(":PULS:DEL" + str(n) + " " + str(t))

class VNA(BaseInstrument):
    def file_read(self, path):
        data = self.ask(":MMEM:TRAN? \"%s\"" % (path,))

        if data[0] != '#':
            return ''

        data_start = 2 + int(data[1])
        data_size = int(data[2:data_start])

        return data[data_start:]

    def file_write(self, path, data):
        size = len(data)
        prefix = "#" + str(int(math.ceil(math.log10(size)))) + str(size)
        self.write(":MMEM:TRAN \"%s\",%s%s" % (path, prefix, data))

    def save_s2p(self, path):
        self.write(":MMEM:STOR:SNP:TYPE:S1P 1")
        self.write(":MMEM:STOR:SNP:TYPE:S2P 1,2")
        self.write(":MMEM:STOR:SNP \"%s\"" % (path,))

    def set_state(self, path):
        self.write(":MMEM:LOAD \"%s\"" % (path,))

class TemperatureLogger:
    def __init__(self, port):
        self.port = serial.Serial(port, 9600, timeout=1)

    def get_temp(self, channel=0):
        self.port.write('A')
        self.port.flush()
        r = self.port.read(45)
        return (struct.unpack('>h', r[7+channel:9+channel])[0]) / 10.0
