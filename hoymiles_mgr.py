import appdaemon.plugins.hass.hassapi as hass
import time, timeutils
from hoymiles import HoymilesInverter

class HoymilesMgr(hass.Hass):

    def initialize(self):
        self.run_in(self.connect_to_inverter, 10)

    def connect_to_inverter(self, kwargs):
        
        self.hoymiles_inverter = HoymilesInverter(host = '192.168.1.136', port = 502)             
        self.hoymiles_inverter.power_cycle_dtu(self)

        self.publish_message(var_name = "hoymiles_last_dtu_reset",
                             friendly_name = "Letzter Reset der DTU",
                             msg_text = timeutils.get_current_timestamp())
        
        self.run_in(self.schedule_callbacks, 15)
        
    def schedule_callbacks(self, kwargs):
        
        self.run_every(self.update_power_status, "now", 4)
        self.run_every(self.update_aux_status, "now", 10)
        self.run_every(self.publish_measurements, "now", 4)
        self.run_every(self.data_integrity_watchdog, "now", 4)

    def data_integrity_watchdog(self, kwargs):

        def _is_anomalous_val(val):
            return abs(val) < 1e-3

        def _sun_shines():
            sun_state = self.get_entity("sun.sun").get_state(attribute = "state")
            return sun_state == "above_horizon"
        
        if _sun_shines() and \
           _is_anomalous_val(self.hoymiles_inverter.power_status["inverter_0_power_kW"]) and \
           _is_anomalous_val(self.hoymiles_inverter.power_status["inverter_1_power_kW"]) and \
           _is_anomalous_val(self.hoymiles_inverter.temperature_status["temp_inverter_0_deg"]) and \
           _is_anomalous_val(self.hoymiles_inverter.temperature_status["temp_inverter_1_deg"]):
            self.schedule_restart()
            
    def schedule_restart(self):

        self.hoymiles_inverter.power_status["inverter_0_power_kW"] = 0.0
        self.hoymiles_inverter.power_status["inverter_1_power_kW"] = 0.0
        self.hoymiles_inverter.power_status["last_updated"] = "in_restart"
        self.hoymiles_inverter.temperature_status["temp_inverter_0_deg"] = 0.0
        self.hoymiles_inverter.temperature_status["temp_inverter_1_deg"] = 0.0
        self.hoymiles_inverter.temperature_status["last_updated"] = "in_restart"
        self.publish_measurements_hoymiles()
        self.restart_app("hoymiles_mgr")
        
    def update_power_status(self, kwargs):
        try:
            self.hoymiles_inverter.update_power_status()
        except:
            self.schedule_restart()

    def update_aux_status(self, kwargs):
        try:
            self.hoymiles_inverter.update_temperature_status()
        except:
            self.schedule_restart()

    def publish_measurements(self, kwargs):
        self.publish_measurements_hoymiles()

    def publish_measurements_hoymiles(self):

        self.publish_measurement(var_name = "hoymiles_inverter_0_power",
                                 friendly_name = "Gaupe Ost Ausgangsleistung",
                                 value = self.disp_format(self.hoymiles_inverter.power_status["inverter_0_power_kW"]),
                                 unit = "kW",
                                 meas_type = "power")

        self.publish_measurement(var_name = "hoymiles_inverter_1_power",
                                 friendly_name = "Gaupe West Ausgangsleistung",
                                 value = self.disp_format(self.hoymiles_inverter.power_status["inverter_1_power_kW"]),
                                 unit = "kW",
                                 meas_type = "power")

        self.publish_message(var_name = "hoymiles_power_lastdata",
                             friendly_name = "Letzte Aktualisierung der Leistungsdaten",
                             msg_text = self.hoymiles_inverter.power_status["last_updated"])

        self.publish_measurement(var_name = "hoymiles_inverter_0_temp_deg",
                                 friendly_name = "Gaupe Ost Temperatur",
                                 value = self.disp_format(self.hoymiles_inverter.temperature_status["temp_inverter_0_deg"]),
                                 unit = "°C",
                                 meas_type = "power")

        self.publish_measurement(var_name = "hoymiles_inverter_1_temp_deg",
                                 friendly_name = "Gaupe West Temperatur",
                                 value = self.disp_format(self.hoymiles_inverter.temperature_status["temp_inverter_1_deg"]),
                                 unit = "°C",
                                 meas_type = "power")

        self.publish_message(var_name = "hoymiles_temp_lastdata",
                             friendly_name = "Letzte Aktualisierung der Temperaturdaten",
                             msg_text = self.hoymiles_inverter.temperature_status["last_updated"])

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
