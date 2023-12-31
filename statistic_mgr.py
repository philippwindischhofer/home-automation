import appdaemon.plugins.hass.hassapi as hass
import os, configparser, datetime, calendar, time

class AccumulatingStatistic:

    def __init__(self, name, accumulator_names, data_namespace):
        self.data_namespace = data_namespace
        self.accumulator_names = accumulator_names
        self.name = name.lower()
        
        self.last_value = 0.0
        self.accumulators = {name: 0.0 for name in self.accumulator_names}

        self._load_state()    

    def get_accumulator(self, name):
        return self.accumulators.get(name, 0.0)

    def reset_accumulator(self, name):
        self.accumulators[name] = 0.0
                
    def accumulate(self, value, delta_T):
        increment = 0.5 * (self.last_value + value) * delta_T
        self.last_value = value
        
        for key in self.accumulator_names:
            self.accumulators[key] += increment

        self._dump_state()
            
    def _dump_state(self):

        self.data_namespace.publish_measurement(var_name = f"accumulating_statistic_{self.name}_last_value",
                                                friendly_name = f"accumulating_statistic_{self.name}_last_value",
                                                value = self.last_value,
                                                unit = "kWh",
                                                meas_type = "power")
        
        for key, value in self.accumulators.items():
            self.data_namespace.publish_measurement(var_name = f"accumulating_statistic_{self.name}_accumulator_{key}",
                                                    friendly_name = f"accumulating_statistic_{self.name}_accumulator_{key}",
                                                    value = value,
                                                    unit = "kWh",
                                                    meas_type = "power")

    def _load_state(self):
               
        self.last_value = self.data_namespace.get_last_from_history(f"sensor.accumulating_statistic_{self.name}_last_value")

        for key in self.accumulator_names:
            self.accumulators[key] = self.data_namespace.get_last_from_history(f"sensor.accumulating_statistic_{self.name}_accumulator_{key}")
            
class StatisticMgr(hass.Hass):

    def initialize(self):

        self.accumulator_names = ["hourly", "daily", "monthly"]
        self.run_in(self.schedule_callbacks, 30)

    def schedule_callbacks(self, kwargs):

        self.global_stats = {
            "energy_produced_kwh": AccumulatingStatistic("energy_produced_kwh", self.accumulator_names, data_namespace = self),
            "energy_sold_kwh": AccumulatingStatistic("energy_sold_kwh", self.accumulator_names, data_namespace = self),
            "energy_bought_kwh": AccumulatingStatistic("energy_bought_kwh", self.accumulator_names, data_namespace = self),
            "energy_used_kwh": AccumulatingStatistic("energy_used_kwh", self.accumulator_names, data_namespace = self)
        }

        self.friendly_names = {
            "energy_produced_kwh": "Produzierte Energie",
            "energy_sold_kwh": "Verkaufte Energie",
            "energy_bought_kwh": "Gekaufte Energie",
            "energy_used_kwh": "Verbrauchte Energie",
        }
        
        self.integration_interval_sec = 4.0    
        self.run_every(self.update_statistics, "now", self.integration_interval_sec)
        self.run_every(self.publish_measurements, "now", self.integration_interval_sec)
        self.run_hourly(self.make_and_publish_snapshots_hourly, datetime.time(0, 0, 0))
        self.run_daily(self.make_and_publish_snapshots_daily, datetime.time(23, 59, 59))
        self.run_daily(self.make_and_publish_snapshots_monthly, datetime.time(23, 59, 59))
        
    def update_statistics(self, kwargs):

        sampling_interval_hr = self.integration_interval_sec / 3600.0
        self.global_stats["energy_produced_kwh"].accumulate(abs(self.read_measurement("global_pv_power")), sampling_interval_hr)
        self.global_stats["energy_used_kwh"].accumulate(abs(self.read_measurement("global_load_power")), sampling_interval_hr)

        grid_power = self.read_measurement("global_grid_power")
        if grid_power > 0.0:
            self.global_stats["energy_sold_kwh"].accumulate(abs(grid_power), sampling_interval_hr)
        else:
            self.global_stats["energy_bought_kwh"].accumulate(abs(grid_power), sampling_interval_hr)

    def make_and_publish_snapshots_hourly(self, kwargs):
        self.publish_as_statistic("hourly", reset_accumulator = True)

    def make_and_publish_snapshots_daily(self, kwargs):
        self.publish_as_statistic("daily", reset_accumulator = True)

    def make_and_publish_snapshots_monthly(self, kwargs):

        def is_last_day_of_month():
            day = datetime.datetime.now().day
            month = datetime.datetime.now().month
            year = datetime.datetime.now().year
            last_day = calendar.monthrange(year, month)[1]

            return day == last_day

        if is_last_day_of_month():
            self.publish_as_statistic("monthly", reset_accumulator = True)
        
    def publish_measurements(self, kwargs):
        self.publish_as_measurement("daily", reset_accumulator = False)
        self.publish_as_measurement("monthly", reset_accumulator = False)
        
    def publish_as_statistic(self, accumulator_name, reset_accumulator = False):

        for name, stat in self.global_stats.items():
            self.publish_statistic(var_name = name + f"_{accumulator_name}",
                                   friendly_name = self.friendly_names[name],
                                   value = self.stat_format(stat.get_accumulator(accumulator_name)),
                                   unit = "kWh",
                                   meas_type = "power",
                                   state_class = "measurement")

            if reset_accumulator:
                stat.reset_accumulator(accumulator_name)

    def publish_as_measurement(self, accumulator_name, reset_accumulator = False):

        for name, stat in self.global_stats.items():
            self.publish_measurement(var_name = name + f"_{accumulator_name}",
                                     friendly_name = self.friendly_names[name],
                                     value = self.disp_format(stat.get_accumulator(accumulator_name)),
                                     unit = "kWh",
                                     meas_type = "power")

            if reset_accumulator:
                stat.reset_accumulator(accumulator_name)

    def get_last_from_history(self, name):
        start_time = datetime.datetime.now() - datetime.timedelta(days = 1)
        data = self.get_history(entity_id = name, start_time = start_time)[0]
        return float(data[-1]["state"])
    
    def read_measurement(self, name):
        raw_value = self.get_entity(f"sensor.{name}").get_state(attribute = "state")
        return float(raw_value) if raw_value else 0.0
                
    def publish_statistic(self, var_name, friendly_name, value, unit, meas_type, state_class):
        self.set_state(f"statistic.{var_name}",
                       state = value,
                       attributes = {"friendly_name": friendly_name,
                                     "unit_of_measurement": unit,
                                     "state_class": state_class,
                                     "device_class": meas_type})
        
    def publish_measurement(self, var_name, friendly_name, value, unit, meas_type):
        self.set_state(f"sensor.{var_name}",
                       state = value,
                       attributes = {"friendly_name": friendly_name,
                                     "unit_of_measurement": unit,
                                     "state_class": "measurement",
                                     "device_class": meas_type})
        
    def disp_format(self, val):
        return round(val, 2)

    def stat_format(self, val):
        return round(val, 4)
