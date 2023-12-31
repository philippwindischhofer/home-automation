import appdaemon.plugins.hass.hassapi as hass
from froeling import LambdatronicS3100

class FroelingMgr(hass.Hass):

    def initialize(self):
        self.publish_message(var_name = "froeling_status",
                             friendly_name = "Status Froeling",
                             msg_text = "Starting")

        self.run_in(self.initialize_froeling, 20)

    def initialize_froeling(self, kwargs):
        self.publish_message(var_name = "froeling_status",
                             friendly_name = "Status Froeling",
                             msg_text = "Initializing")

        # initialize everything
        self.froeling = LambdatronicS3100(host = '192.168.1.147', port = 23, timeout = 0.1, debug = False)
        self.froeling.send_login(mode = "service")

        while True:
            self.froeling.receive_and_parse()
            if self.froeling.init_complete:
                break

        self.froeling.request_status()
            
        self.publish_message(var_name = "froeling_status",
                             friendly_name = "Status Froeling",
                             msg_text = "Active")
            
        # schedule callbacks
        self.run_every(self.handle_protocol, "now", 1)
        self.run_every(self.publish_measurements, "now+10", 1)

    def handle_protocol(self, kwargs):
        try:
            while self.froeling.receive_and_parse():
                pass
        except ConnectionError:
            print("Froeling connection error, scheduling restart.")
            self.schedule_restart()

    def schedule_restart(self):
        self.publish_message(var_name = "froeling_status",
                             friendly_name = "Status Froeling",
                             msg_text = "In restart")        
        self.restart_app("froeling_mgr")

    def publish_measurements(self, kwargs):
        
        self.publish_message(var_name = "froeling_lastdata",
                             friendly_name = "Letzte Aktualisierung der Heizungsdaten",
                             msg_text = self.froeling.parameter_values["last_updated"])

        self.publish_measurement(var_name = "froeling_boiler_temp",
                                 friendly_name = "Froeling Kesseltemperatur",
                                 value = self.froeling.parameter_values.get("Kesseltemp", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_exhaust_temp",
                                 friendly_name = "Froeling Abgastemperatur",
                                 value = self.froeling.parameter_values.get("Abgastemp.", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_exhaust_temp_target",
                                 friendly_name = "Froeling Abgastemperatur Sollwert",
                                 value = self.froeling.parameter_values.get("Abgas. SW", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_forced_air",
                                 friendly_name = "Froeling Saugzug",
                                 value = self.froeling.parameter_values.get("Saugzug", 0.0),
                                 unit = "%")

        self.publish_measurement(var_name = "froeling_prim_air",
                                 friendly_name = "Froeling Prim. Luft",
                                 value = self.froeling.parameter_values.get("Prim.Luft", 0.0),
                                 unit = "%")

        self.publish_measurement(var_name = "froeling_sec_air",
                                 friendly_name = "Froeling Sek. Luft",
                                 value = self.froeling.parameter_values.get("Sek.Luft", 0.0),
                                 unit = "%")
        
        self.publish_measurement(var_name = "froeling_ox_rem",
                                 friendly_name = "Froeling Rest-O2",
                                 value = self.froeling.parameter_values.get("Rest-O2", 0.0),
                                 unit = "%")

        self.publish_measurement(var_name = "froeling_buffer_temp_top_deg",
                                 friendly_name = "Puffertemperatur oben",
                                 value = self.froeling.parameter_values.get("Puffert.ob", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_buffer_temp_mid_deg",
                                 friendly_name = "Puffertemperatur mitte",
                                 value = self.froeling.parameter_values.get("Puffert.mi", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_buffer_temp_bot_deg",
                                 friendly_name = "Puffertemperatur unten",
                                 value = self.froeling.parameter_values.get("Puffert.un", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_outside_temp_deg",
                                 friendly_name = "Aussentemperatur",
                                 value = self.froeling.parameter_values.get("Außentemp", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_loop_1_target_temp_deg",
                                 friendly_name = "Vorlauftemperatur 1 Sollwert",
                                 value = self.froeling.parameter_values.get("Vorlauft.1sw", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_loop_1_temp_deg",
                                 friendly_name = "Vorlauftemperatur 1",
                                 value = self.froeling.parameter_values.get("Vorlauft.1", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_loop_2_target_temp_deg",
                                 friendly_name = "Vorlauftemperatur 2 Sollwert",
                                 value = self.froeling.parameter_values.get("Vorlauft.2sw", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_loop_2_temp_deg",
                                 friendly_name = "Vorlauftemperatur 2",
                                 value = self.froeling.parameter_values.get("Vorlauft.2", 0.0),
                                 unit = "°C")

        self.publish_measurement(var_name = "froeling_board_temp_deg",
                                 friendly_name = "Boardtemperatur",
                                 value = self.froeling.parameter_values.get("Boardtemp.", 0.0),
                                 unit = "°C")
                
    def publish_message(self, var_name, friendly_name, msg_text):
        self.set_state(f"sensor.{var_name}",
                       state = msg_text,
                       attributes = {"friendly_name": friendly_name})
        
    def publish_measurement(self, var_name, friendly_name, value, unit, meas_type = "power"):
        self.set_state(f"sensor.{var_name}",
                       state = value,
                       attributes = {"friendly_name": friendly_name,
                                     "unit_of_measurement": unit,
                                     "state_class": "measurement",
                                     "device_class": meas_type})

