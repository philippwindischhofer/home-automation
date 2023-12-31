from pyModbusTCP.client import ModbusClient
import time, timeutils

class SofarInverter:

    def __init__(self, host, port):
        self.c = ModbusClient(host = host, port = port, unit_id = 1,
                              auto_open = True, debug = False, timeout = 0.1)

        self.sys_state_map = {
            0: "Waiting",
            1: "Detection",
            2: "Connected to grid",
            3: "Emergency power",
            4: "Recoverable fault",
            5: "Permanent fault",
            6: "Upgrade",
            7: "Self-charging"
        }
        
        self.battery_status = {
            "temp_ambient_deg": 0.0,
            "temp_BMS_deg_0": 0.0,
            "temp_BMS_deg_1": 0.0,
            "temp_BMS_deg_2": 0.0,
            "temp_BMS_deg_3": 0.0,
            "soc": 0,
            "soh": 0,
            "cycle_cnt": 0,
            "latency_ms": -1,
            "last_updated": "Never"
        }

        self.power_status = {
            "battery_power_charge_kW": 0.0,
            "pv_power_kW": 0.0,
            "inverter_power_kW": 0.0,
            "grid_power_kW": 0.0,
            "latency_ms": -1,
            "last_updated": "Never"
        }

        self.temperature_status = {
            "temp_env_deg_1": 0.0,
            "temp_env_deg_2": 0.0,
            "temp_heat_sink_deg_1": 0.0,
            "temp_heat_sink_deg_2": 0.0,
            "temp_heat_sink_deg_3": 0.0,
            "temp_heat_sink_deg_4": 0.0,
            "temp_heat_sink_deg_5": 0.0,
            "temp_heat_sink_deg_6": 0.0,
            "temp_inv_deg_1": 0.0,
            "temp_inv_deg_2": 0.0,
            "temp_inv_deg_3": 0.0,
            "last_updated": "Never"
        }
        
        self.inverter_status = {
            "sys_state": -1,
            "sys_state_string": "N/A",
            "last_updated": "Never"
        }

    def update_temperature_status(self):
        words = self.read_register(0x0418, 11)
        self.temperature_status["temp_env_deg_1"] = self.word_to_L16(words[0])
        self.temperature_status["temp_env_deg_2"] = self.word_to_L16(words[1])
        self.temperature_status["temp_heat_sink_deg_1"] = self.word_to_L16(words[2])
        self.temperature_status["temp_heat_sink_deg_2"] = self.word_to_L16(words[3])
        self.temperature_status["temp_heat_sink_deg_3"] = self.word_to_L16(words[4])
        self.temperature_status["temp_heat_sink_deg_4"] = self.word_to_L16(words[5])
        self.temperature_status["temp_heat_sink_deg_5"] = self.word_to_L16(words[6])
        self.temperature_status["temp_heat_sink_deg_6"] = self.word_to_L16(words[7])
        self.temperature_status["temp_inv_deg_1"] = self.word_to_L16(words[8])
        self.temperature_status["temp_inv_deg_2"] = self.word_to_L16(words[9])
        self.temperature_status["temp_inv_deg_3"] = self.word_to_L16(words[10])
        self.temperature_status["last_updated"] = timeutils.get_current_timestamp()
        
    def update_battery_status(self):
        start_time = timeutils.get_current_time()
        words = self.read_register(0x0607, 4)
        self.battery_status["temp_ambient_deg"] = self.word_to_L16(words[0])
        self.battery_status["soc"] = self.word_to_U16(words[1])
        self.battery_status["soh"] = self.word_to_U16(words[2])
        self.battery_status["cycle_cnt"] = self.word_to_U16(words[3])

        words = self.read_register(0x906B, 4)
        self.battery_status["temp_BMS_pack_0_deg"] = self.word_to_L16(words[0]) * 0.1
        self.battery_status["temp_BMS_pack_1_deg"] = self.word_to_L16(words[1]) * 0.1
        self.battery_status["temp_BMS_pack_2_deg"] = self.word_to_L16(words[2]) * 0.1
        self.battery_status["temp_BMS_pack_3_deg"] = self.word_to_L16(words[3]) * 0.1
        end_time = timeutils.get_current_time()
        
        self.battery_status["last_updated"] = timeutils.get_timestamp(end_time)
        self.battery_status["latency_ms"] = timeutils.measure_time_ms(start_time, end_time)

    def update_inverter_status(self):
        sys_state = self.read_U16(0x0404)
        self.inverter_status["sys_state"] = sys_state
        self.inverter_status["sys_state_string"] = self.sys_state_map[sys_state]
        self.inverter_status["last_updated"] = timeutils.get_current_timestamp()
        
    def update_power_status(self, inter_read_sleep = 0.01):
        start_time = timeutils.get_current_time()
        self.power_status["battery_power_charge_kW"] = self.read_L16(0x0606) * 0.01
        self.power_status["inverter_power_kW"] = self.read_L16(0x0485) * 0.01
        time.sleep(inter_read_sleep)
        self.power_status["pv_power_kW"] = self.read_U16(0x05C4) * 0.1
        time.sleep(inter_read_sleep)
        self.power_status["grid_power_kW"] = self.read_L16(0x0488) * 0.01
        end_time = timeutils.get_current_time()
        self.power_status["last_updated"] = timeutils.get_timestamp(end_time)
        self.power_status["latency_ms"] = timeutils.measure_time_ms(start_time, end_time)

    def set_remote(self, timeout = 10):
        self.write_and_verify_register(0x1184, [self.U16_to_word(timeout), 1])
        self.write_and_verify_register(0x1110, [3])

    def set_local(self):
        self.write_and_verify_register(0x1110, [0])

    def set_battery_power_charge_kW(self, power):
        power_W = int(1000 * power)
        data = [0, 0] + self.L32_to_words(power_W) + self.L32_to_words(power_W)
        self.write_register(0x1187, data)
        
    def read_U16(self, addr):
        return self.word_to_U16(self.read_register(addr, 1)[0])

    def read_L16(self, addr):
        return self.word_to_L16(self.read_register(addr, 1)[0])
        
    def L16_to_word(self, val):
        return int.from_bytes(val.to_bytes(2, byteorder = "big", signed = True), byteorder = "big", signed = False)

    def word_to_L16(self, word):
        return int.from_bytes(word.to_bytes(2, byteorder = "big", signed = False), byteorder = "big", signed = True)

    def U16_to_word(self, val):
        return val

    def word_to_U16(self, val):
        return val

    def L32_to_words(self, val):
        val_bytes = val.to_bytes(4, byteorder = "big", signed = True)
        words = []
        for ind in range(0, len(val_bytes), 2):
            words.append(int.from_bytes(val_bytes[ind:ind+2], byteorder = "big", signed = False))
        return words

    def words_to_L32(self, words):
        val_bytes = []
        for word in words:
            val_bytes += word.to_bytes(2, byteorder = "big", signed = False)
        return int.from_bytes(val_bytes, byteorder = "big", signed = True)

    def U32_to_words(self, val):
        val_bytes = val.to_bytes(4, byteorder = "big", signed = False)
        words = []
        for ind in range(0, len(val_bytes), 2):
            words.append(int.from_bytes(val_bytes[ind:ind+2], byteorder = "big", signed = False))
        return words

    def words_to_U32(self, words):
        val_bytes = []
        for word in words:
            val_bytes += word.to_bytes(2, byteorder = "big", signed = False)
        return int.from_bytes(val_bytes, byteorder = "big", signed = False)    
        
    def read_register(self, addr, num_words, verbose = False, timeout = 0.2):
        while True:
            try:
                words = self.c.read_holding_registers(addr, num_words)
                if words is None:
                    raise RuntimeError("Error: no data received")
                return words
            except:
                if verbose:
                    print("{}: Sofar modbus communication error.".format(timeutils.get_current_timestamp()))
                time.sleep(timeout)

    def write_and_verify_register(self, addr, words_to_write, inter_read_sleep = 0.01, timeout = 0.2, verbose = True):
        while True:
            self.write_register(addr, words_to_write)
            time.sleep(inter_read_sleep)
            readback = self.read_register(addr, len(words_to_write))
            if words_to_write == readback:
                break
            else:
                print("{}: Sofar write error.".format(timeutils.get_current_timestamp()))
                time.sleep(timeout)
                
    def write_register(self, addr, words_to_write):        
        return self.c.write_multiple_registers(addr, words_to_write)
    
if __name__ == "__main__":

    sofar_inverter = SofarInverter(host = '192.168.1.146', port = 26)

    sofar_inverter.set_local()
    
    while True:
        sofar_inverter.update_power_status()
        print(sofar_inverter.power_status)
        sofar_inverter.update_battery_status()
        print(sofar_inverter.battery_status)
        time.sleep(1)
