#!/usr/bin/env python3

import atexit
from collections import namedtuple
import os
import readline
import sys
import threading

import paho.mqtt.client as mqtt


LOG_MSGS = False


class Codes:
    RST_ALL           =  0
    BOLD              =  1
    DIM               =  2
    UNDERLINED        =  4
    BLINK             =  5
    REVERSE           =  7
    HIDDEN            =  8
    RST_ATTR          = 20
    RST_BOLD          = 21
    RST_DIM           = 22
    RST_UNDERLINED    = 24
    RST_BLINK         = 25
    RST_REVERSE       = 27
    RST_HIDDEN        = 28
    FG_BLACK          = 30
    FG_RED            = 31
    FG_GREEN          = 32
    FG_YELLOW         = 33
    FG_BLUE           = 34
    FG_MAGENTA        = 35
    FG_CYAN           = 36
    FG_LIGHT_GRAY     = 37
    RST_FG            = 39
    RST_BG            = 39
    FG_DARK_GRAY      = 90
    FG_LIGHT_RED      = 91
    FG_LIGHT_GREEN    = 92
    FG_LIGHT_YELLOW   = 93
    FG_LIGHT_BLUE     = 94
    FG_LIGHT_MAGENTA  = 95
    FG_LIGHT_CYAN     = 96
    FG_WHITE          = 97


Data = namedtuple("Data", "file event color")

DATA = {
    "stdout": Data(file=sys.stdout, event=threading.Event(),
        color=Codes.FG_LIGHT_BLUE),
    "stderr": Data(file=sys.stderr, event=threading.Event(),
        color=Codes.FG_LIGHT_RED),
}


def code(*args):
    return "\033[{}m".format(";".join([str(a) for a in args]))


def on_message(client, userdata, message):
    payload = message.payload.decode()
    if LOG_MSGS:
        print("RECV: t:{} p:{}".format(message.topic, payload))
    levels = message.topic.split("/")
    file = levels[1]
    topic = "/".join(levels[2:])
    if payload[0] == "-":
        DATA[file].event.set()
    else:
        print("{}{}:{} {}".format(
            code(DATA[file].color),
            topic,
            code(Codes.RST_ALL),
            payload[1:]), file=DATA[file].file)


def publish_and_wait(client, topic, payload):
    for data in DATA.values():
        data.event.clear()
    if LOG_MSGS:
        print("SEND: t:{} p:{}".format(topic, payload))
    client.publish(topic, payload, 2)
    for data in DATA.values():
        data.event.wait()


if __name__ == "__main__":
    # History file
    histfile = os.path.join(os.path.expanduser("~"), ".mqttsh_history")
    try:
        readline.read_history_file(histfile)
        readline.set_history_length(1000)
    except FileNotFoundError:
        pass
    atexit.register(readline.write_history_file, histfile)

    # MQTT connection
    client = mqtt.Client()
    client.on_message = on_message
    try:
        client.connect("localhost", 1883)
        client.subscribe([("mqttsh/stdout/test", 2),
                          ("mqttsh/stderr/test", 2)])

        client.loop_start()

        if sys.stdin.isatty():  # Interactive mode
            while True:
                line = input("{}{}@{}{}:{}{}{}$ ".format(
                    code(Codes.BOLD, Codes.FG_LIGHT_GREEN),
                    "localhost",
                    1883,
                    code(Codes.RST_FG),
                    code(Codes.FG_LIGHT_BLUE),
                    "test",
                    code(Codes.RST_ALL)))
                if line == "exit":
                    break
                publish_and_wait(client, "mqttsh/stdin/test", line)
        else:  # Non-interactive mode
            payload = sys.stdin.read().rstrip()
            publish_and_wait(client, "mqttsh/stdin/test", payload)

        client.loop_stop()
    finally:
        client.disconnect()
