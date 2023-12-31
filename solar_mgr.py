import appdaemon.plugins.hass.hassapi as hass
from sofar import SofarInverter
import datetime, math

class SolarMgr(hass.Hass):

    def initialize(self):

        self.turn_off("input_boolean.scheduler_remote")
        self.listen_state(self.scheduler_remote_on, "input_boolean.scheduler_remote", new = "on")
        self.listen_state(self.scheduler_remote_off, "input_boolean.scheduler_remote", new = "off")
        
        self.sofar_inverter = SofarInverter(host = '192.168.1.146', port = 26)
        self.sofar_inverter.set_local()

        self.scheduler_status = {
            "state": "inactive",
            "user_override": None
        }

        self.scheduler_params = {
            "battery_charge_power_max_kW": 2.0,
            "battery_scheduler_soc_max": 99
        }
        
        self.global_status = {
            "grid_power_kW": 0.0,
            "load_power_kW": 0.0,
            "pv_power_kW": 0.0,
            "last_updated": "Never"
        }
        
        self.run_every(self.update_power_status, "now", 4)
        self.run_every(self.update_aux_status, "now", 15)
        self.run_every(self.publish_measurements, "now", 4)
        self.run_every(self.scheduler, "now", 4)

    def scheduler_remote_on(self, entity, attribute, old, new, kwargs):
        self.scheduler_status["user_override"] = "active_local"

    def scheduler_remote_off(self, entity, attribute, old, new, kwargs):
        self.scheduler_status["user_override"] = "to_inactive"

    def scheduler(self, kwargs):

        if self.scheduler_status["user_override"] is not None:
            self.scheduler_status["state"] = self.scheduler_status["user_override"]
            self.scheduler_status["user_override"] = None
                    
        if self.scheduler_status["state"] == "to_inactive":
            self.scheduler_status["state"] = "inactive"
            self.sofar_inverter.set_battery_power_charge_kW(0.0)
            self.sofar_inverter.set_local()
            
        elif self.scheduler_status["state"] == "active_local":
            self.sofar_inverter.set_local()
            if self.sofar_inverter.power_status["battery_power_charge_kW"] > self.scheduler_params["battery_charge_power_max_kW"] + 0.1 and self.sofar_inverter.battery_status["soc"] < self.scheduler_params["battery_scheduler_soc_max"]:
                self.scheduler_status["state"] = "active_remote_charge_power_charge_limit"
                
        elif self.scheduler_status["state"] == "active_remote_charge_power_charge_limit":
            self.sofar_inverter.set_remote()
            self.sofar_inverter.set_battery_power_charge_kW(self.scheduler_params["battery_charge_power_max_kW"])            

            if self.global_status["grid_power_kW"] < 0.0 or self.sofar_inverter.battery_status["soc"] >= self.scheduler_params["battery_scheduler_soc_max"]:
                self.scheduler_status["state"] = "active_local"
            
        elif self.scheduler_status["state"] == "inactive":
            pass
        
        self.publish_message("scheduler_status", "scheduler_status", self.scheduler_status["state"])
                        
    def update_global_status(self):

        hoymiles_inverter_power_status = {
            "inverter_0_power_kW": self.read_measurement("hoymiles_inverter_0_power"),
            "inverter_1_power_kW": self.read_measurement("hoymiles_inverter_1_power")
        }
        
        self.global_status["grid_power_kW"] = self.sofar_inverter.power_status["grid_power_kW"]        
        self.global_status["pv_power_kW"] = self.sofar_inverter.power_status["pv_power_kW"] + hoymiles_inverter_power_status["inverter_0_power_kW"] + hoymiles_inverter_power_status["inverter_1_power_kW"]
        self.global_status["load_power_kW"] = hoymiles_inverter_power_status["inverter_0_power_kW"] + hoymiles_inverter_power_status["inverter_1_power_kW"] + self.sofar_inverter.power_status["inverter_power_kW"] - self.global_status["grid_power_kW"]
        self.global_status["last_updated"] = self.sofar_inverter.power_status["last_updated"]
        
    def update_power_status(self, kwargs):
        
        self.sofar_inverter.update_power_status()
        self.update_global_status()

    def update_aux_status(self, kwargs):
        
        self.sofar_inverter.update_battery_status()
        self.sofar_inverter.update_inverter_status()
        self.sofar_inverter.update_temperature_status()
        
    def publish_measurements(self, kwargs):
        
        self.publish_measurements_global()
        self.publish_measurements_sofar()
        self.publish_measurements_diagnosis()

    def publish_measurements_diagnosis(self):

        self.publish_measurement(var_name = "sofar_power_latency",
                                 friendly_name = "sofar_power_latency",
                                 value = self.sofar_inverter.power_status["latency_ms"],
                                 unit = "ms",
                                 meas_type = "power")

        self.publish_measurement(var_name = "sofar_battery_latency",
                                 friendly_name = "sofar_battery_latency",
                                 value = self.sofar_inverter.battery_status["latency_ms"],
                                 unit = "ms",
                                 meas_type = "power")        
        
    def publish_measurements_global(self):

        self.publish_measurement(var_name = "global_pv_power",
                                 friendly_name = "PV Leistung",
                                 value = self.disp_format(self.global_status["pv_power_kW"]),
                                 unit = "kW",
                                 meas_type = "power")
        
        self.publish_measurement(var_name = "global_grid_power",
                                 friendly_name = "Netzbezug",
                                 value = self.disp_format(self.global_status["grid_power_kW"]),
                                 unit = "kW",
                                 meas_type = "power")

        self.publish_measurement(var_name = "global_load_power",
                                 friendly_name = "Verbrauch",
                                 value = self.disp_format(self.global_status["load_power_kW"]),
                                 unit = "kW",
                                 meas_type = "power")
        
    def publish_measurements_sofar(self):
        
        self.publish_measurement(var_name = "sofar_inverter_power",
                                 friendly_name = "Sofar Wechselrichter Ausgangsleistung",
                                 value = self.disp_format(self.sofar_inverter.power_status["inverter_power_kW"]),
                                 unit = "kW",
                                 meas_type = "power")

        self.publish_measurement(var_name = "sofar_pv_power",
                                 friendly_name = "Sofar PV Leistung",
                                 value = self.disp_format(self.sofar_inverter.power_status["pv_power_kW"]),
                                 unit = "kW",
                                 meas_type = "power")
        
        self.publish_measurement(var_name = "sofar_battery_power",
                                 friendly_name = "Sofar Akku Leistung",
                                 value = self.disp_format(self.sofar_inverter.power_status["battery_power_charge_kW"]),
                                 unit = "kW",
                                 meas_type = "power")
        
        self.publish_message(var_name = "sofar_power_lastdata",
                             friendly_name = "Letzte Aktualisierung der Lastdaten",
                             msg_text = self.sofar_inverter.power_status["last_updated"])
        
        self.publish_measurement(var_name = "sofar_battery_SOC",
                                 friendly_name = "Sofar Akku Ladezustand",
                                 value = self.sofar_inverter.battery_status["soc"],
                                 unit = "%",
                                 meas_type = "power")

        self.publish_measurement(var_name = "sofar_battery_SOH",
                                 friendly_name = "Sofar Akku Kapazitaet",
                                 value = self.sofar_inverter.battery_status["soh"],
                                 unit = "%",
                                 meas_type = "power")
        
        self.publish_measurement(var_name = "sofar_battery_cyclecount",
                                 friendly_name = "Sofar Akku Zyklen",
                                 value = self.sofar_inverter.battery_status["cycle_cnt"],
                                 unit = "cycles",
                                 meas_type = "power")

        self.publish_measurement(var_name = "sofar_battery_temp_ambient_deg",
                                 friendly_name = "Sofar Akku Umgebungstemperatur",
                                 value = self.disp_format(self.sofar_inverter.battery_status["temp_ambient_deg"]),
                                 unit = "°C",
                                 meas_type = "power")

        self.publish_measurement(var_name = "sofar_battery_temp_BMS_pack_0_deg",
                                 friendly_name = "Sofar Akku BMS Temperatur",
                                 value = self.disp_format(self.sofar_inverter.battery_status["temp_BMS_pack_0_deg"]),
                                 unit = "°C",
                                 meas_type = "power")

        self.publish_measurement(var_name = "sofar_battery_temp_BMS_pack_1_deg",
                                 friendly_name = "Sofar Akku BMS Temperatur",
                                 value = self.disp_format(self.sofar_inverter.battery_status["temp_BMS_pack_1_deg"]),
                                 unit = "°C",
                                 meas_type = "power")

        self.publish_measurement(var_name = "sofar_battery_temp_BMS_pack_2_deg",
                                 friendly_name = "Sofar Akku BMS Temperatur",
                                 value = self.disp_format(self.sofar_inverter.battery_status["temp_BMS_pack_2_deg"]),
                                 unit = "°C",
                                 meas_type = "power")

        self.publish_measurement(var_name = "sofar_battery_temp_BMS_pack_3_deg",
                                 friendly_name = "Sofar Akku BMS Temperatur",
                                 value = self.disp_format(self.sofar_inverter.battery_status["temp_BMS_pack_3_deg"]),
                                 unit = "°C",
                                 meas_type = "power")
                        
        self.publish_message(var_name = "sofar_battery_lastdata",
                             friendly_name = "Letzte Aktualisierung der Batteriedaten",
                             msg_text = self.sofar_inverter.battery_status["last_updated"])

        self.publish_measurement(var_name = "sofar_temp_env_deg",
                                 friendly_name = "Sofar Umgebungstemperatur",
                                 value = self.disp_format(self.sofar_inverter.temperature_status["temp_env_deg_1"]),
                                 unit = "°C",
                                 meas_type = "power")        

        self.publish_measurement(var_name = f"sofar_temp_heat_sink_deg",
                                 friendly_name = f"Sofar Kuehlkoerpertemperatur",
                                 value = self.disp_format(self.sofar_inverter.temperature_status["temp_heat_sink_deg_1"]),
                                 unit = "°C",
                                 meas_type = "power")        

        self.publish_measurement(var_name = f"sofar_temp_inv_deg",
                                 friendly_name = f"Sofar Wechselrichtertemperatur",
                                 value = self.disp_format(self.sofar_inverter.temperature_status["temp_inv_deg_1"]),
                                 unit = "°C",
                                 meas_type = "power")

        self.publish_message(var_name = "sofar_temperature_lastdata",
                             friendly_name = "Letzte Aktualisierung der Temperaturdaten",
                             msg_text = self.sofar_inverter.temperature_status["last_updated"])            
        
        self.publish_message(var_name = "sofar_status",
                             friendly_name = "Sofar Status",
                             msg_text = self.sofar_inverter.inverter_status["sys_state_string"])
                
    def disp_format(self, val):
        return round(val, 2)
    
    def publish_message(self, var_name, friendly_name, msg_text):
        self.set_state(f"sensor.{var_name}",
                       state = msg_text,
                       attributes = {"friendly_name": friendly_name})
        
    def publish_measurement(self, var_name, friendly_name, value, unit, meas_type):
        self.set_state(f"sensor.{var_name}",
                       state = value,
                       attributes = {"friendly_name": friendly_name,
                                     "unit_of_measurement": unit,
                                     "state_class": "measurement",
                                     "device_class": meas_type})

    def read_measurement(self, name):
        raw_value = self.get_entity(f"sensor.{name}").get_state(attribute = "state")
        return float(raw_value) if raw_value else 0.0
