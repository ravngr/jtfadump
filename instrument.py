import math
import serial
import struct
import time
import visa
import util

_debug = True

def _cast_bool(c):
	return 'ON' if c else 'OFF'

class BaseInstrument:
	"""Parent class for instruments"""
	def __init__(self, id):
		self.dev = visa.instrument(id)

	def reset(self):
		self.dev.write("*RST")

	def wait(self):
		self.dev.ask("*OPC?")

	def get_id(self):
		return self.dev.ask("*IDN?")

	def ask(self, cmd):
		if _debug:
			print self.dev.resource_name + " <> " + cmd

		return self.dev.ask(cmd)

	def write(self, cmd):
		if _debug:
			print self.dev.resource_name + " <- " + cmd

		self.dev.write(cmd)

class Counter(BaseInstrument):
	"""Frequency counter"""
	impedance = util.enum(FIFTY='50', HIGH='1E6')

	def get_freq(self):
		return float(self.ask(":READ?"))

	def set_meas_time(self, t):
		self.write(":ACQ:APER " + str(t))

	def set_z(self, impedance):
		self.write(":INP:IMP " + impedance)

class Scope(BaseInstrument):
	"""Oscilloscope"""
	channels = 4

	_volt_step = [ 2e-3, 5e-3, 1e-2, 2e-2, 5e-2, 1e-1, 2e-1, 5e-1, 1.0, 2.0, 5.0 ]

	ch_couple = util.enum(AC='AC', DC='DC')
	ch_impedance = util.enum(FIFTY='FIFT', HIGH='ONEM')
	img_format = util.enum(BMP='BMP', BMP8='BMP8', PNG='PNG')
	mode_aq = util.enum(NORMAL='NORM', AVERAGE='AVER', HIGHRES='HRES', PEAK='PEAK')
	mode_run = util.enum(RUN='RUN', STOP='STOP', SINGLE='SING')
	time_mode = util.enum(MAIN='MAIN', WINDOW='WIND', XY='XY', ROLL='ROLL')
	time_ref = util.enum(LEFT='LEFT', CENTER='CENTER', RIGHT='RIGHT')
	trigger_mode = util.enum(EDGE='EDGE', GLITCH='GLIT', PATTERN='PATT', TV='TV', DELAY='DEL', EBURST='EBUR', OR='OR', RUNT='RUNT', SHOLD='SHOL', TRANSITION='TRAN', SBUS_1='SBUS1', SBUS_2='SBUS2', USB='USB')
	trigger_sweep = util.enum(AUTO='AUTO', NORMAL='NORMAL')
	trigger_edge_source = util.enum(CHANNEL='CHAN', DIGITAL='DIG', EXTERNAL='EXT', LINE='LINE', WAVE_GEN='WGEN')
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
		self.write(":CHAN" + str(channel) + ":LAB " + str(label))

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
		self.write(":TIM:SCAL " + reference)

	def set_time_scale(self, t):
		self.write(":TIM:SCAL " + str(t))

	# Trigger
	def set_trigger_holdoff(self, t):
		self.write(":TRIG:HOLD " + str(t))

	def set_trigger_mode(self, mode):
		self.write(":TRIG:MODE " + mode)

	def set_trigger_sweep(self, sweep):
		self.write(":TRIG:SWE " + sweep)

	def set_trigger_edge_level(self, level):
		self.write(":TRIG:EDGE:LEV " + str(level))

	def set_trigger_edge_level_auto(self):
		self.write(":TRIG:LEV:ASET")

	def set_trigger_edge_source(self, source, channel=-1):
		if channel >= 0:
			self.write(":TRIG:EDGE:SOUR " + source + channel)
		else:
			self.write(":TRIG:EDGE:SOUR " + source)

	def trigger(self):
		self.write("*TRG")

	def single_trigger(self, timeout = 0, interval = 0.1):
		self.write("STOP")
		self.write(":TER?")
		self.write(":SING")

		t = 0

		while timeout == 0 or t <= timeout:
			trigger = self.ask(":TER?")

			if len(trigger) > 0 and trigger[1] == '1':
				return True

			time.sleep(interval)

		return False

	# Waveform
	def get_waveform(self, source, channel = -1, highres = False):
		self.write(":WAV:FORM " + ('WORD' if highres else 'BYTE'))
		self.write(":WAV:BYT LSBF")	# LSB first
		self.write(":WAV:UNS 1")	# Unsigned
		self.write(":WAV:POIN:MODE MAX")
		self.write(":WAV:POIN MAX")

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

		if highres:
			wave_size /= 2

		data = []

		for n in range(0, wave_size):
			if highres:
				s = wave_start + n * 2
				m = struct.unpack('>H', waveform[s:s + 2])[0]
			else:
				s = wave_start + n
				m = struct.unpack('>B', waveform[s])[0]

			x = (n - x_ref) * x_step + x_origin
			y = (m - y_ref) * y_step + y_origin

			data.append((n, m, x, y))

		return data

	def get_waveform_smart(self, source, channel = -1, highres = False):
		for v in self._volt_step:
			self.set_ch_scale(channel, v)
			data = self.get_waveform(source, channel, highres)

			flag = True

			for n in data:
				# Check data bounds, discard and switch ranges if clipping has occurred
				if n[1] == 0 or (not highres and n[1] == 255) or (highres and n[1] == 65536):
					flag = False
					break

			if flag:
				break

		return data

	def get_waveform_smart_multichannel(self, channels, highres = False):
		# Make a copy of the channel list so we can edit it
		channels = list(channels)

		return_data = []

		for v in self._volt_step:
			# Set voltage on all active channels
			for n in channels:
				self.set_ch_scale(n, v)

			# Dump data on all active channels
			for i, n in enumerate(channels):
				data = self.get_waveform(self.wave_source.CHANNEL, n, highres)

				flag = True

				for n in data:
					if n[1] == 0 or (not highres and n[1] == 255) or (highres and n[1] == 65536):
						flag = False
						break

				if flag:
					del channels[i]
					return_data.append(data)

			if len(channels) == 0:
				break

		return return_data

class PowerSupply(BaseInstrument):
	def __init__(self, id):
		BaseInstrument.__init__(self, id)

		self.dev.term_chars = '\r'
		self.write("*ADR 1")

	def reset(self):
		PowerSupply.reset(self)
		self.write("*ADR 1")

	def get_voltage(self):
		return self.ask(":MEAS?")

	def get_current(self):
		return self.ask(":MEAS:CURR?")

	def get_power(self):
		return self.get_voltage() * self.get_power()

	def set_voltage(self, voltage):
		self.write(":VOLT " + str(voltage))

	def set_current(self, current):
		self.write(":CURR " + str(current))

	def set_output(self, enabled):
		self.write(":OUTP " + _cast_bool(enabled))

class SignalGenerator(BaseInstrument):
	pulsemod_source = util.enum(INT_10M='INT1', INT_40M='INT2', EXT_FRONT='EXT1', EXT_BACK='EXT2')

	def set_output(self, enabled):
		self.write(":OUTP:STAT " + _cast_bool(enabled))

	def set_output_frequency(self, frequency):
		self.write(":FREQ:MODE CW")
		self.write(":FREQ " + str(frequency))

	def set_output_power(self, power):
		self.write(":POW " + str(power) + "dBm")

	def set_pulsemod(self, enabled):
		self.write(":PULM:STAT " + _cast_bool(enabled))

	def set_pulsemod_source(self, source):
		self.write(":PULM:SOUR " + source)

	def set_pulsemod_count(self, count):
		self.write(":PULM:COUN " + str(count))

	def set_pulsemod_period(self, t):
		self.write(":PULS:PER " + str(t))

	def set_pulsemod_width(self, n, t):
		self.write(":PULS:WIDT" + n + " " + str(t))

	def set_pulsemod_delay(self, n, t):
		self.write(":PULS:DEL" + n + " " + str(t))

class VNA(BaseInstrument):
	def file_read(self, path):
		data = self.ask(":MMEM:TRAN " + path + "?")

		if data[0] != '#':
			return ''

		data_start = 2 + int(data[1])
		data_size = int(data[2:data_start])

		return data[data_start:]

	def file_write(self, path, data):
		size = len(data)
		prefix = "#" + str(int(math.ceil(math.log10(size)))) + str(size)
		self.write(":MMEM:TRAN " + path + "," + prefix + data)

	def save_s2p(self, path):
		self.write(":MMEM:STOR:SNP:TYPE:S1P 1")
		self.write(":MMEM:STOR:SNP:TYPE:S2P 1,2")
		self.write(":MMEM:STOR:SNP " + path)

	def set_state(self, path):
		self.write(":MMEM:LOAD " + path)

class TemperatureLogger:
	def __init__(self, port):
		self.port = serial.Serial(port, 9600, timeout=1)

	def get_temp(self, channel=0):
		self.port.write('A')
		self.port.flush()
		r = self.port.read(45)
		return (struct.unpack('>h', r[7+channel:9+channel])[0]) / 10.0
