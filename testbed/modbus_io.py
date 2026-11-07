"""Modbus/TCP interface: a server that exposes the plant's REPORTED state, and a client
the agent's tools use to read it. Uses pymodbus 3.6.x.

The server runs in a background thread for the whole experiment; before each episode
`publish(plant)` writes the current reported values into its holding registers.
"""
import logging
import threading
import time

from . import config as C

try:
    from pymodbus.datastore import (ModbusSequentialDataBlock, ModbusServerContext,
                                    ModbusSlaveContext)
    from pymodbus.server import StartTcpServer, ServerStop
    from pymodbus.client import ModbusTcpClient
    HAVE_PYMODBUS = True
except ImportError:  # pragma: no cover
    HAVE_PYMODBUS = False

logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

MACHINE_IDS = list(C.MACHINES)


def base_address(mid):
    return 100 * (MACHINE_IDS.index(mid) + 1)


def encode(sig):
    return [max(0, min(65535, int(round(float(sig[f]) * s)))) for f, s in C.REG_FIELDS]


def decode(regs):
    out = {}
    for (f, s), v in zip(C.REG_FIELDS, regs):
        out[f] = v / s if s != 1 else int(v)
    return out


class ModbusPlantServer:
    def __init__(self, host=C.MODBUS_HOST, port=C.MODBUS_PORT):
        if not HAVE_PYMODBUS:
            raise RuntimeError("pymodbus is not installed: pip install pymodbus==3.6.9")
        self.host, self.port = host, port
        block = ModbusSequentialDataBlock(0, [0] * 400)
        self.slave = ModbusSlaveContext(hr=block, zero_mode=True)
        self.context = ModbusServerContext(slaves={C.MODBUS_UNIT: self.slave}, single=False)
        self.thread = None

    def start(self):
        self.thread = threading.Thread(
            target=StartTcpServer,
            kwargs=dict(context=self.context, address=(self.host, self.port)),
            daemon=True)
        self.thread.start()
        # wait until it accepts connections
        for _ in range(50):
            c = ModbusTcpClient(self.host, port=self.port)
            if c.connect():
                c.close()
                return self
            time.sleep(0.1)
        raise RuntimeError("Modbus server did not start")

    def publish(self, plant):
        for mid in MACHINE_IDS:
            self.slave.setValues(3, base_address(mid), encode(plant.reported_signals(mid)))

    def stop(self):
        try:
            ServerStop()
        except Exception:
            pass


class ModbusReader:
    """What the agent's get_machine_status tool uses."""

    def __init__(self, host=C.MODBUS_HOST, port=C.MODBUS_PORT):
        self.client = ModbusTcpClient(host, port=port)
        self.client.connect()

    def read(self, mid):
        rr = self.client.read_holding_registers(base_address(mid), len(C.REG_FIELDS),
                                                slave=C.MODBUS_UNIT)
        if rr.isError():
            raise RuntimeError(f"Modbus read failed for {mid}: {rr}")
        return decode(rr.registers)

    def close(self):
        self.client.close()


class DirectReader:
    """Fallback without Modbus (for quick tests): reads the plant's reported state directly."""

    def __init__(self, plant_ref):
        self.plant_ref = plant_ref  # callable returning current plant

    def read(self, mid):
        return decode(encode(self.plant_ref().reported_signals(mid)))

    def close(self):
        pass
