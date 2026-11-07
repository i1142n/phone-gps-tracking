"""PC side: receives the phone's GPS fixes, prints them and appends them to a CSV file."""
import argparse
import csv
import getpass
import json

import paho.mqtt.client as mqtt

COLUMNS = ['time', 'lat', 'lon', 'altitude', 'speed', 'bearing', 'accuracy']

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('topic', help='same topic as in the app, e.g. phone-gps/1a2b3c4d')
parser.add_argument('--host', default='broker.hivemq.com')
parser.add_argument('--port', type=int, help='default: 8883 (TLS) with --user, else 1883')
parser.add_argument('--user')
parser.add_argument('--password', help='asked for interactively if omitted')
parser.add_argument('--csv', default='gps_log.csv', help='output file (appended)')
args = parser.parse_args()
if args.port is None:
    args.port = 8883 if args.user else 1883  # private brokers (EMQX) only accept TLS on 8883

csv_file = open(args.csv, 'a', newline='')
writer = csv.DictWriter(csv_file, fieldnames=COLUMNS, extrasaction='ignore')
if csv_file.tell() == 0:
    writer.writeheader()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f'Connection refused: {reason_code}')  # e.g. wrong user/password
        return
    print(f'Connected, listening on {args.topic}')
    client.subscribe(args.topic)  # in on_connect, so it resubscribes after a reconnect


def on_message(client, userdata, msg):
    fix = json.loads(msg.payload)
    print(fix)
    writer.writerow(fix)
    csv_file.flush()


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
if args.user:
    client.username_pw_set(args.user, args.password or getpass.getpass('MQTT password: '))
if args.port == 8883:
    client.tls_set()
client.connect(args.host, args.port)
client.loop_forever()
