#!/usr/bin/env python3

import queue
import subprocess
import threading

import paho.mqtt.client as mqtt


LOG_MSGS = False


def pipe(fh, queue):
    for line in fh:
        queue.put(line.rstrip())
    fh.close()
    queue.put(None)


def publish(client, topic, payload):
    if LOG_MSGS:
        print("SEND: t:{} p:{}".format(topic, payload))
    client.publish(topic, payload, 2)


def on_message(client, queue, message):
    if LOG_MSGS:
        print("RECV: t:{} p:{}".format(
            message.topic, message.payload.decode()))
    queue.put(message)


def process(client, message):
    stdout = queue.Queue()
    stderr = queue.Queue()

    # Start shell process
    with subprocess.Popen(["/bin/bash"],
        bufsize=1, universal_newlines=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE) as prc:

        # Start pipe threads (pipe -> queue)
        threads = []
        args_list = [
            (prc.stdout, stdout),
            (prc.stderr, stderr),
        ]
        for args in args_list:
            thread = threading.Thread(target=pipe, args=args)
            thread.daemon = True
            thread.start()
            threads.append(thread)

        # Write input
        prc.stdin.write(message.payload.decode())
        prc.stdin.flush()
        prc.stdin.close()

        # Read queues and send (queue -> MQTT)
        stdout_end, stderr_end = False, False
        while not stdout_end or not stderr_end:
            if not stdout_end:
                try:
                    line = stdout.get(timeout=0.05)
                    if line is not None:
                        publish(client, "mqttsh/stdout/test", "+" + line)
                    else:
                        publish(client, "mqttsh/stdout/test", "-")
                        stdout_end = True
                except queue.Empty:
                    pass
            if not stderr_end:
                try:
                    line = stderr.get(timeout=0.05)
                    if line is not None:
                        publish(client, "mqttsh/stderr/test", "+" + line)
                    else:
                        publish(client, "mqttsh/stderr/test", "-")
                        stderr_end = True
                except queue.Empty:
                    pass

        # Wait
        prc.wait()
        for thread in threads:
            thread.join()


messages = queue.Queue()
client = mqtt.Client(userdata=messages)
client.on_message = on_message
try:
    client.connect("localhost", 1883)
    client.subscribe("mqttsh/stdin/test", 2)
    client.loop_start()
    while True:
        process(client, messages.get())
    client.loop_stop()
finally:
    client.disconnect()
