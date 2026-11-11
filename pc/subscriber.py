"""Receives the phone's sensor readings from the MQTT broker, prints them and appends them to one CSV file per sensor."""
import argparse
import csv
import getpass
import json
import os

import paho.mqtt.client as mqtt

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('topics', nargs='+', help="topics set in the app, e.g. phone/gps phone/gyroscope, or 'phone/#' for all")
parser.add_argument('--host', required=True, help='broker address, e.g. abc123.ala.us-east-1.emqxsl.com')
parser.add_argument('--port', type=int, default=8883)
parser.add_argument('--user', required=True)
parser.add_argument('--password', help='asked for if omitted')
parser.add_argument('--out', default='log', help='output folder, readings are appended to <sensor>.csv')
args = parser.parse_args()
password = args.password or getpass.getpass('MQTT password: ')
os.makedirs(args.out, exist_ok=True)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f'Connection refused: {reason_code}')
        return
    print(f'Connected, listening on {", ".join(args.topics)}')
    client.subscribe([(topic, 0) for topic in args.topics])


def on_message(client, userdata, message):
    reading = json.loads(message.payload)
    print(reading)
    path = os.path.join(args.out, reading.pop('sensor') + '.csv')
    is_new = not os.path.exists(path)
    with open(path, 'a', newline='') as csv_file:
        csv_writer = csv.DictWriter(csv_file, fieldnames=list(reading))
        if is_new:
            csv_writer.writeheader()
        csv_writer.writerow(reading)


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(args.user, password)
client.tls_set()
client.on_connect = on_connect
client.on_message = on_message
client.connect(args.host, args.port)

try:
    client.loop_forever()
except KeyboardInterrupt:
    client.disconnect()
