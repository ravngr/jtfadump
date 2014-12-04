import logging
import visa


# Base class for instrument connectors
class InstrumentConnector:
    def __init__(self, identifier):
        self._log = logging.getLogger()

    def write(self, data):

        raise NotImplementedError()

    def query(self, data):
        raise NotImplementedError()

    def query_raw(self, data):
        raise NotImplementedError()


class VISAConnector(InstrumentConnector):
    def __init__(self, address):
        InstrumentConnector.__init__(self, address)

        self._instrument = visa.instrument(address)
        self._instrument.clear()
        self._log.debug("[OPEN] VISA Resource: %s" % (address,))

    def write(self, data):
        self._instrument.write(data)
        self._log.debug("[WRITE] %s <= %s" % (self._instrument.resource_name, data))

    def query(self, data):
        response = self._instrument.ask(data)
        self._log.debug("[QUERY] Q: %s <> %s | Response: %s)" % (self._instrument.resource_name, data, response))
        return response

    def query_raw(self, data):
        response = self._instrument.ask_raw(data)
        response_len = len(response)
        self._log.debug("Q: %s <> %s | Response: %i byte%s" % (self._instrument.resource_name, data, response_len,
                                                               's' if response_len == 1 else ''))
        return response


# Base class for instruments
class Instrument:
    def __init__(self, connector):
        self._connector = connector

    def get_id(self):
        return self._connector.query("*IDN?")

    def reset(self):
        self._connector.write("*RST")

    def wait(self):
        self._connector.query("*OPC?")


# Actual instrument definitions
class FrequencyCounter(Instrument):
    pass


class NetworkAnalyzer(Instrument):
    pass


class Oscilloscope(Instrument):
    pass


class PowerSupply(Instrument):
    def __init__(self, connector):
        Instrument.__init__(self, connector)
        self._connector.term_chars = '\r'
        self._connector.write("*ADR 1")

    def reset(self):
        self._connector.write("*RST")
        # Need to re-address the power supply
        self._connector.write("*ADR 1")

    def clear_alarm(self):
        self._connector.write(":OUTP:PROT:CLE")


class SignalGenerator(Instrument):
    pass
