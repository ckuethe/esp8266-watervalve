#!/usr/bin/env micropython
# coding: utf-8
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 syn=python

from machine import Pin, Timer, enable_irq, disable_irq, time_pulse_us  # pylint: disable=import-error
from time import sleep
import network  # pylint: disable=import-error

config = {
    "meter_pin": 12,  # D6  GPIO12
    "open_valve_pin": 14,  # D5  GPIO14
    "close_valve_pin": 16,  # D0  GPIO16
    "pulse_wait_us": 100_000,
    "detection_time": 5,  # detection latency, in seconds
    "flow_poll_ms": 500,  # how often to poll water flow state
}

try:
    from config import config as userconfig

    config.update(userconfig)
except ImportError:
    pass


try:
    led_pin = Pin(config["led_pin"], Pin.OUT)
except Exception:
    led_pin = None
close_valve_pin = Pin(config["close_valve_pin"], Pin.OUT, value=0)
open_valve_pin = Pin(config["open_valve_pin"], Pin.OUT, value=0)
meter_pin = Pin(config["meter_pin"], Pin.IN)

response_time = 5


flow_num_samples = config["detection_time"] * 1000 // config["flow_poll_ms"]
flow_samples = []
valve_state = None


class CriticalSection(object):
    imask = None

    def __enter__(self):
        self.imask = disable_irq()

    def __exit__(self, *args):
        enable_irq(self.imask)


def valve_open():
    # Simple: deassert the close_valve_pin, wait a moment, then assert the open_valve_pin
    global valve_state
    close_valve_pin.off()
    sleep(0.01)
    open_valve_pin.on()
    valve_state = True


def valve_close():
    # Simple: deassert the open_valve_pin, wait a moment, then assert the close_valve_pin
    global valve_state
    open_valve_pin.off()
    sleep(0.01)
    close_valve_pin.on()
    valve_state = False


def sample_flow(tmr=None):
    # periodically, check the sensor to see if pulses are coming in.
    global flow_samples
    pulse_time = 0
    with CriticalSection():
        pulse_time = time_pulse_us(meter_pin, 1, config["pulse_wait_us"])  # XXX is 100,000us (0.1s) enough? too much?

    flow_samples.append(1 if pulse_time > 0 else 0)
    if len(flow_samples) > flow_num_samples:
        flow_samples = flow_samples[-flow_num_samples:]

    if tmr:
        tmr.init(period=config["flow_poll_ms"], mode=Timer.ONE_SHOT, callback=sample_flow)


def valve_control(_=None):
    vsum = 0
    # with CriticalSection():
    if True:
        vsum = sum(flow_samples)

    if vsum == 0 and valve_state != True:
        # no flow
        valve_open()
        print("opening valve")
    elif vsum == flow_num_samples and valve_state != False:
        # flow for the last... however long
        valve_close()
        print("closing valve")


def network_config():
    wl = network.WLAN(network.STA_IF)
    wl.active()
    try:
        wl.config(dhcp_hostname=config["hostname"])
    except KeyError:
        pass
    try:
        s, p = config["ssid"], config["psk"]
        wl.disconnect()
        wl.connect(s, p)
    except KeyError:
        pass


def main():
    network_config()

    # eye-candy: toggle LED whenever pulses are detected
    if led_pin:
        meter_pin.irq(trigger=Pin.IRQ_FALLING, handler=lambda x: led_pin.value(led_pin.value() ^ 1))

    flow_timer = Timer(-1)
    flow_timer.init(period=config["flow_poll_ms"], mode=Timer.ONE_SHOT, callback=sample_flow)

    control_timer = Timer(-1)
    control_timer.init(period=1000, mode=Timer.PERIODIC, callback=valve_control)
