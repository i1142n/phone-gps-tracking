"""Receives the phone's GPS fixes from the MQTT broker, prints them and appends them to a CSV file."""
import argparse
import csv
import getpass
import json

import paho.mqtt.client as mqtt

COLUMNS = ['time', 'lat', 'lon', 'altitude', 'speed', 'bearing', 'accuracy']

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('topic', help='topic shown in the app, e.g. phone-gps')
parser.add_argument('--host', required=True, help='broker address, e.g. abc123.ala.us-east-1.emqxsl.com')
parser.add_argument('--port', type=int, default=8883)
parser.add_argument('--user', required=True)
parser.add_argument('--password', help='asked for if omitted')
parser.add_argument('--csv', default='gps_log.csv', help='output file, new fixes are appended')
args = parser.parse_args()
password = args.password or getpass.getpass('MQTT password: ')

csv_file = open(args.csv, 'a', newline='')
csv_writer = csv.DictWriter(csv_file, fieldnames=COLUMNS, extrasaction='ignore')
if csv_file.tell() == 0:
    csv_writer.writeheader()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f'Connection refused: {reason_code}')
        return
    print(f'Connected, listening on {args.topic}')
    client.subscribe(args.topic)


def on_message(client, userdata, message):
    fix = json.loads(message.payload)
    print(fix)
    csv_writer.writerow(fix)
    csv_file.flush()


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
    csv_file.close()
