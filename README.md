# Home automation with AppDaemon and HomeAssistant

## Content

This repository contains software for remote monitoring of the inverters, battery, and firewood boiler as used in our home automation system.
Specifically, we use

* 1 x Sofar HYD 10KTL-3PH inverter
* 2 x Hoymiles HMS-1600-4T microinverters with 3Gen DTU-Pro
* 1 x Froeling firewood boiler with Lambdatronic S3100 control unit

The code here defines four [`AppDaemon`](https://appdaemon.readthedocs.io/en/latest/index.html) apps that connect to these devices and provide data for our [`HomeAssistant`](https://www.home-assistant.io) installation.

## Intended usage

In the unlikely case that your setup overlaps precisely with ours, you can download the entire repository and include it into your `AppDaemon` instance.

In the much more likely case that only some components are useful for you, you can simply take what you need. Each device is handled by two `python` modules that follow a particular nomenclature. The following components are available:

* The Sofar inverter is controlled by `sofar.py` and `solar_mgr.py`.
  - `sofar.py` connects to the inverter through Modbus-RTU and provides a general interface to read information from / send commands to the inverter. This module is independent of `AppDaemon` and can be integrated in whatever home automation system you decide to use.
  - `solar_mgr.py` is an `AppDaemon` app that uses `sofar.py` to periodically read the inverter status and forwards this data to `HomeAssistant`, where it can be displayed or otherwise used. It also relies on information provided by the Hoymiles inverters (see below) to calculate the global system output. (You might want to edit the code to adapt it to your needs.)
* The Hoymiles microinverters are read out through Modbus-TCP as provided by the DTU. This device interface is defined in `hoymiles.py`, while `hoymiles_mgr.py` is the corresponding `AppDaemon` app.
* Similarly, data from the Froeling boiler is handled by `froeling.py` and `froeling_mgr.py`. This part is a partial `python` implementation of the (outstanding!) [`Radiator`](https://github.com/dhoepfl/Radiator) project by Daniel Hoepfl, who also nicely documented the protocol used by the boiler.

