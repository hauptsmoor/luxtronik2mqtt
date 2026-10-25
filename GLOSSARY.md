# luxtronik2mqtt

Connects a single Luxtronik heat-pump controller to an MQTT broker. It publishes the controller's values and accepts commands that change its settings.

## Language

**Controller**:
The Luxtronik 2.x unit that runs one heat pump and that the bridge talks to over the network.
_Avoid_: Heat pump (when the electronics are meant), device, Luxtronik box

**Bridge**:
One running instance of luxtronik2mqtt, connected to exactly one Controller and one MQTT broker.
_Avoid_: Gateway, adapter, service

### Interfaces

**CFI**:
The Controller's proprietary configuration interface on port 8889. It exposes Calculations, Parameters and Visibilities.
_Avoid_: Modbus, socket API, port 8889 interface

**SHI**:
The Smart Home Interface: the Controller's Modbus TCP interface for outside control, which exposes Inputs and Holdings.
_Avoid_: Modbus (on its own), GLT, BMS interface

### Values

**Input**:
A read-only value the Controller offers over the SHI, such as a temperature or an operating state.
_Avoid_: Input register, SHI sensor

**Holding**:
A value that outside systems write over the SHI to steer the Controller, such as a hot-water setpoint or a heating lock. The Controller forgets it after a reboot.
_Avoid_: Holding register, SHI parameter

**Command**:
A request sent over MQTT asking the Bridge to set one Holding to a new value. It counts as applied only once reading the Holding back shows the new value.
_Avoid_: Write request, set message, control message

**Calculation**:
A read-only value that the Controller measures or derives, such as a temperature, an operating state or a run-hour counter.
_Avoid_: Sensor, reading, measurement

**Parameter**:
A setting stored on the Controller that a person or system can change, such as a setpoint or an operating mode.
_Avoid_: Config, setting, option

**Visibility**:
A flag from the Controller that says whether a feature, and so the Calculations and Parameters that belong to it, is present on this installation.
_Avoid_: Capability, feature flag
