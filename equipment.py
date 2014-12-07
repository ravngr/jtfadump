import logging
import math
import visa
import util


"""Base class for instrument connectors"""
class InstrumentConnector:
    def __init__(self, address):
        self._address = address
        self._log = logging.getLogger()

    def get_address(self):
        return self._address

    def write(self, data):
        raise NotImplementedError()

    def query(self, data):
        raise NotImplementedError()

    def query_raw(self, data):
        raise NotImplementedError()


class VISAConnector(InstrumentConnector):
    def __init__(self, address, term_chars=False, use_bus_address=False):
        InstrumentConnector.__init__(self, address)

        resource_manager = visa.ResourceManager()

        self._use_bus_address = use_bus_address
        self._last_bus_address = False

        # Open resource
        self._instrument = resource_manager.open_resource(address)

        # Specify termination character(s) if provided
        if term_chars is not False:
            #self._instrument.read_termination = term_chars
            self._instrument.write_termination = term_chars

        self._instrument.clear()

        self._log.debug("[OPEN] VISA Resource: {}".format(address))

    def select_bus_address(self, bus_address, force=False):
        if self._use_bus_address and bus_address is not False:
            if force or self._last_bus_address != bus_address:
                self._instrument.write("*ADR {}".format(bus_address))
                self._log.debug("[BUS] Select bus address {}".format(bus_address))

            self._last_bus_address = bus_address

    def write(self, data, bus_address=False):
        self.select_bus_address(bus_address)
        self._instrument.write(data)
        self._log.debug("[{}] WRITE: {}".format(self.get_address(), data))

    def query(self, data, bus_address=False):
        self.select_bus_address(bus_address)
        response = self._instrument.ask(data)
        self._log.debug("[{}] QUERY: {} | RESPONSE: {})".format(self.get_address(), data, response))
        return response

    def query_raw(self, data, bus_address=False):
        self.select_bus_address(bus_address)
        response = self._instrument.ask_raw(data)
        response_len = len(response)
        self._log.debug("[{}] RAW QUERY: {} | RESPONSE: {} byte{}".format(self.get_address(), data, response_len,
                                                               's' if response_len == 1 else ''))
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
        self._connector.select_bus_address(self._bus_address, force=True)

    def wait(self):
        self._connector.write("*WAI", self._bus_address)

    @staticmethod
    def _cast_bool(value):
        return "ON" if value else "OFF"


""" Instrument exceptions"""
class InstrumentException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


"""Instrument definitions"""
class FrequencyCounter(Instrument):
    IMPEDANCE = util.enum(FIFTY='50', HIGH='1E6')

    def __init__(self, connector, bus_address = False):
        Instrument.__init__(self, connector, bus_address)

    def get_frequency(self):
        return float(self._connector.query(":READ?"))

    def set_measurement_time(self, time):
        self._connector.write(":ACQ:APER {}".format(time))

    def set_impedance(self, impedance):
        self._connector.write(":INP:IMP {}".format(impedance))


class NetworkAnalyzer(Instrument):
    SNP_FORMAT = util.enum(AUTO='AUTO', LOGMAG_ANG='MA', LINMAG_ANG='DB', REAL_IMAG='RI')

    def __init__(self, connector):
        Instrument.__init__(self, connector, False)
        self._temp_path = '\\temp'

    def data_save_snp(self, path, ports, format=SNP_FORMAT.AUTO):
        port_count = len(ports)

        if port_count < 1 or port_count > 4:
            raise InstrumentException("Unsupported number of ports in SNP format")

        self._connector.write(":MMEM:STOR:SNP:TYPE:S{}P {}".format(port_count, ','.join(ports)))
        self._connector.write(":MMEM:STOR:SNP \"{}\"".format(path))

    def lock(self, key_lock=False, mouse_lock=False, backlight=False):
        self._connector.write(":SYST:KLOC:KBD {}".format(self._cast_bool(not key_lock)))
        self._connector.write(":SYST:KLOC:MOUS {}".format(self._cast_bool(not mouse_lock)))
        self._connector.write(":SYST:BACK {}".format(self._cast_bool(not backlight)))

    def file_delete(self, path):
        self._connector.write(":MMEM:DEL \"{}\"".format(path))

    def file_read(self, path):
        data = self._connector.query(":MMEM:TRAN? \"{}\"".format(path))

        if data[0] != '#':
            return ''

        data_start = 2 + int(data[1])
        data_size = int(data[2:data_start])

        return data[data_start:(data_start + data_size)]

    def file_write(self, path, data):
        size = len(data)
        prefix = "#" + str(int(math.ceil(math.log10(size)))) + str(size)
        self._connector.write(":MMEM:TRAN \"{}\",{}{}".format(path, prefix, data))

    def file_transfer(self, local_path, remote_path, to_VNA):
        file_mode = "rb" if to_VNA else "wb"

        with open(local_path, file_mode) as f:
            if to_VNA:
                data = f.readall()
                self.file_write(remote_path, data)
            else:
                data = self.file_read(remote_path)
                f.write(data)

    def state_load(self, path):
        self._connector.write(":MMEM:LOAD \"{}\"".format(path))

    def state_save(self, path):
        self._connector.write(":MMEM:STOR \"{}\"".format(path))

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


class Oscilloscope(Instrument):
    def __init__(self, connector, channels=4):
        Instrument.__init__(self, connector, False)

        self._channels = channels


class PowerSupply(Instrument):
    def __init__(self, connector, bus_address = False):
        Instrument.__init__(self, connector, bus_address)

    def clear_alarm(self):
        self._connector.write(":OUTP:PROT:CLE")

    def set_output_enable(self, enabled):
        self._connector.write(":OUTP {}".format(self._cast_bool(enabled)), self._bus_address)

    def set_voltage(self, voltage):
        pass

    def set_current(self, current):
        pass

    def get_voltage(self):
        pass

    def get_current(self):
        pass

    def get_power(self):
        return self.get_voltage() * self.get_current()


class SignalGenerator(Instrument):
    pass
