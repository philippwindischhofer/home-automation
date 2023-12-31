from pyModbusTCP.client import ModbusClient
import time, timeutils

class HoymilesInverter:

    def __init__(self, host, port):
        self.c = ModbusClient(host = host, port = port, unit_id = 1,
                              auto_open = True, debug = False, timeout = 3)

        self.power_status = {
            "inverter_0_power_kW": 0.0,
            "inverter_1_power_kW": 0.0,
            "last_updated": "Never"
        }

        self.temperature_status = {
            "temp_inverter_0_deg": 0.0,
            "temp_inverter_1_deg": 0.0,
            "last_updated": "Never"
        }
    
    def update_power_status(self):
        inverter_0_data = [self.get_channel_data(channel, 0x10, 1)[0] for channel in range(0, 4)]
        inverter_1_data = [self.get_channel_data(channel, 0x10, 1)[0] for channel in range(4, 8)]        
        self.power_status["inverter_0_power_kW"] = sum(inverter_0_data) * 1e-4
        self.power_status["inverter_1_power_kW"] = sum(inverter_1_data) * 1e-4
        self.power_status["last_updated"] = timeutils.get_current_timestamp()

    def update_temperature_status(self):
        self.temperature_status["temp_inverter_0_deg"] = self.word_to_L16(self.get_channel_data(0, 0x18, 1)[0]) * 0.1
        self.temperature_status["temp_inverter_1_deg"] = self.word_to_L16(self.get_channel_data(4, 0x18, 1)[0]) * 0.1
        self.temperature_status["last_updated"] = timeutils.get_current_timestamp()

    def word_to_L16(self, word):
        return int.from_bytes(word.to_bytes(2, byteorder = "big", signed = False), byteorder = "big", signed = True)
        
    def get_channel_data(self, channel_id, channel_addr, num_words):
        global_addr = 0x1000 + 0x28 * channel_id + channel_addr
        return self.read_register(global_addr, num_words)

    def limit_power(self, percent):        
        self.write_single_dtu_register(0xC001, int(percent * 65535 / 100.0))
    
    def write_single_dtu_register(self, addr, val):
        import struct        
        if not 0 <= int(addr) <= 0xffff:
            raise ValueError('bit_addr out of range (valid from 0 to 65535)')
        try:
            tx_pdu = struct.pack('>BHH', 0x05, addr, val)
            rx_pdu = self.c._req_pdu(tx_pdu=bytes(tx_pdu), rx_min_len=5)
            resp_coil_addr, resp_coil_value = struct.unpack('>HH', rx_pdu[1:5])
            if (resp_coil_addr != addr) or (resp_coil_value != val):
                return False
            return True
        except ModbusClient._InternalError as e:
            self.c._req_except_handler(e)
            return False
        
    def read_register(self, addr, num_words, verbose = False, timeout = 0.2):
        while True:
            words = self.c.read_holding_registers(addr, num_words)
            if words is None:
                raise RuntimeError("Error: no data received")
            return words

    def power_cycle_dtu(self, hass_instance, switch_name = "switch.philipp"):
        switch = hass_instance.get_entity(switch_name)
        switch.turn_off()
        time.sleep(1)
        switch.turn_on()
                
if __name__ == "__main__":

    hoymiles_inverter = HoymilesInverter(host = '192.168.1.136', port = 502)
        
    while True:
        
        hoymiles_inverter.update_power_status()
        print(hoymiles_inverter.power_status)
        hoymiles_inverter.update_temperature_status()
        print(hoymiles_inverter.temperature_status)
