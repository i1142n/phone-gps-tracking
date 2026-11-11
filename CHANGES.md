# Changes

## 11.11.2026: several sensors, one topic per sensor

**Files:** `app/main.py`, `pc/subscriber.py`, `README.md`

**Reason:** publish more sensors than GPS for a localization simulation, each on its own configurable topic, and subscribe to any combination of them.

- `app/main.py`: the single Topic field became one row per sensor (checkbox + topic, default `phone/<sensor>`). Every message carries a `sensor` field. Accelerometer, gyroscope, compass, barometer, gravity and orientation come from plyer and are polled every 0.2 s (`POLL_INTERVAL`), the fixed rate plyer reads them at. Removed the unused `import uuid`.
- `pc/subscriber.py`: takes one or more topics (wildcards allowed) and appends to `<sensor>.csv` per sensor in `--out` (default `log/`), with the columns taken from the message; `--csv` and `COLUMNS` are gone.
- Breaking: the default GPS topic is now `phone/gps` (was `phone-gps`), and the subscriber needs the `sensor` field, so it does not work with the old APK.
- Dropped again the same day on the user's request: a "Rate (Hz)" field and `app/sensors.py` (own pyjnius sensor listener with a settable rate).

**Built/tested:** built (`cd app && PATH=$HOME/miniconda3/envs/buildozer/bin:$PATH JAVA_HOME=/usr/lib/jvm/java-17-openjdk buildozer android debug`, APK in `app/bin/` from 11.11.2026 11:08, matches the code). Installed and started on the phone at 11:10 (`cd app && PATH=$HOME/miniconda3/envs/buildozer/bin:$PATH buildozer android deploy run`): the app reaches the Kivy main loop without a Python error; pressing Start and the sensors are not checked yet. Tested on the PC with stubbed widgets and fake plyer sensors against `broker.emqx.io:8883`:

```bash
python -m venv venv && venv/bin/pip install kivy plyer paho-mqtt certifi
venv/bin/python pc/subscriber.py '<prefix>/gps' '<prefix>/imu' '<prefix>/accelerometer' '<prefix>/barometer' --host broker.emqx.io --user u --password p --out out
```

With a 1 s poll interval all readings arrived in the right CSV files, including two sensors sharing one topic; an unticked sensor and a sensor without data published nothing; Stop disabled every enabled sensor. The public broker delivers only about 10 messages/s, so the real 0.2 s interval was not tested end to end. The widget tree was built headless with `SDL_VIDEODRIVER=offscreen` (rows, saved settings and sizes correct; no usable screenshot).

**Revert:** `git checkout 6938d7a -- app/main.py pc/subscriber.py README.md`

**Diff:**

```diff
diff --git a/app/main.py b/app/main.py
index fbb615a..064f981 100644
--- a/app/main.py
+++ b/app/main.py
@@ -1,71 +1,107 @@
-"""Android app: publishes the phone's GPS fixes as JSON to an MQTT broker."""
+"""Android app: publishes the phone's GPS fixes and sensor readings as JSON to an MQTT broker."""
 import json
 import os
 import time
-import uuid
 
 import certifi
 import paho.mqtt.client as mqtt
 from kivy.app import App
-from kivy.clock import mainthread
+from kivy.clock import Clock, mainthread
 from kivy.lang import Builder
 from kivy.properties import BooleanProperty, StringProperty
 from kivy.storage.jsonstore import JsonStore
+from kivy.uix.boxlayout import BoxLayout
 from kivy.utils import platform
-from plyer import gps
+from plyer import accelerometer, barometer, compass, gps, gravity, gyroscope, spatialorientation
 
 DEFAULTS = {
     'host': '',
     'port': '8883',
-    'topic': 'phone-gps',
     'user': '',
     'password': '',
 }
 
+SENSORS = {
+    'accelerometer': (accelerometer, 'acceleration', ['x', 'y', 'z']),
+    'gyroscope': (gyroscope, 'rotation', ['x', 'y', 'z']),
+    'compass': (compass, 'field', ['x', 'y', 'z']),
+    'barometer': (barometer, 'pressure', ['pressure']),
+    'gravity': (gravity, 'gravity', ['x', 'y', 'z']),
+    'orientation': (spatialorientation, 'orientation', ['yaw', 'pitch', 'roll']),
+}
+
+POLL_INTERVAL = 0.2
+
 KV = '''
 <FieldLabel@Label>:
     size_hint_x: None
-    width: dp(90)
+    width: dp(110)
+    text_size: self.size
+    valign: 'middle'
 
 <Field@TextInput>:
     multiline: False
 
+<SensorRow>:
+    size_hint_y: None
+    height: dp(44)
+    spacing: dp(8)
+
+    CheckBox:
+        id: enabled
+        size_hint_x: None
+        width: dp(32)
+    FieldLabel:
+        text: root.sensor
+    Field:
+        id: topic
+
 BoxLayout:
     orientation: 'vertical'
     padding: dp(16)
     spacing: dp(8)
 
-    GridLayout:
-        cols: 2
-        spacing: dp(8)
-        size_hint_y: None
-        height: self.minimum_height
-        row_default_height: dp(44)
-        row_force_default: True
-        disabled: app.running
-
-        FieldLabel:
-            text: 'Host'
-        Field:
-            id: host
-        FieldLabel:
-            text: 'Port'
-        Field:
-            id: port
-            input_filter: 'int'
-        FieldLabel:
-            text: 'Topic'
-        Field:
-            id: topic
-        FieldLabel:
-            text: 'User'
-        Field:
-            id: user
-        FieldLabel:
-            text: 'Password'
-        Field:
-            id: password
-            password: True
+    ScrollView:
+        BoxLayout:
+            orientation: 'vertical'
+            spacing: dp(8)
+            size_hint_y: None
+            height: self.minimum_height
+            disabled: app.running
+
+            GridLayout:
+                cols: 2
+                spacing: dp(8)
+                size_hint_y: None
+                height: self.minimum_height
+                row_default_height: dp(44)
+                row_force_default: True
+
+                FieldLabel:
+                    text: 'Host'
+                Field:
+                    id: host
+                FieldLabel:
+                    text: 'Port'
+                Field:
+                    id: port
+                    input_filter: 'int'
+                FieldLabel:
+                    text: 'User'
+                Field:
+                    id: user
+                FieldLabel:
+                    text: 'Password'
+                Field:
+                    id: password
+                    password: True
+
+            BoxLayout:
+                id: sensors
+                orientation: 'vertical'
+                spacing: dp(8)
+                size_hint_y: None
+                height: self.minimum_height
 
     Button:
         text: 'Stop' if app.running else 'Start'
@@ -79,17 +115,24 @@ BoxLayout:
         height: dp(56)
 
     Label:
-        text: app.last_fix
+        text: app.readings
+        font_size: sp(12)
         text_size: self.size
         valign: 'top'
+        size_hint_y: None
+        height: dp(120)
 '''
 
 
+class SensorRow(BoxLayout):
+    sensor = StringProperty()
+
+
 class GpsMqttApp(App):
     running = BooleanProperty(False)
     mqtt_status = StringProperty('MQTT: not connected')
     gps_status = StringProperty('GPS: stopped')
-    last_fix = StringProperty('')
+    readings = StringProperty('')
 
     def build(self):
         root = Builder.load_string(KV)
@@ -97,6 +140,13 @@ class GpsMqttApp(App):
         saved = self.store.get('settings') if self.store.exists('settings') else {}
         for key, default in DEFAULTS.items():
             root.ids[key].text = saved.get(key, default)
+        self.rows = {}
+        for name in ['gps', *SENSORS]:
+            row = SensorRow(sensor=name)
+            row.ids.topic.text = saved.get(name + '_topic', 'phone/' + name)
+            row.ids.enabled.active = saved.get(name + '_enabled', True)
+            root.ids.sensors.add_widget(row)
+            self.rows[name] = row
         return root
 
     def on_start(self):
@@ -105,18 +155,27 @@ class GpsMqttApp(App):
 
     def start_sending(self):
         settings = {key: self.root.ids[key].text.strip() for key in DEFAULTS}
+        for name, row in self.rows.items():
+            settings[name + '_topic'] = row.ids.topic.text.strip()
+            settings[name + '_enabled'] = row.ids.enabled.active
         if not settings['host'] or not settings['port']:
             self.mqtt_status = 'MQTT: enter host and port first'
             return
         self.store.put('settings', **settings)
-        self.topic = settings['topic']
+        self.topics = {name: settings[name + '_topic'] for name in self.rows if settings[name + '_enabled']}
+        self.polled = [name for name in self.topics if name in SENSORS and platform == 'android']
+        self.latest = {}
         self.connect_mqtt(settings)
         self.start_gps()
+        self.start_sensors()
+        self.poll_event = Clock.schedule_interval(self.poll_sensors, POLL_INTERVAL)
         self.running = True
 
     def stop_sending(self):
         if platform == 'android':
             gps.stop()
+        self.stop_sensors()
+        self.poll_event.cancel()
         self.client.disconnect()
         self.client.loop_stop()
         self.gps_status = 'GPS: stopped'
@@ -133,6 +192,9 @@ class GpsMqttApp(App):
         self.mqtt_status = 'MQTT: connecting...'
 
     def start_gps(self):
+        if 'gps' not in self.topics:
+            self.gps_status = 'GPS: off'
+            return
         if platform != 'android':
             self.gps_status = 'GPS: only available on Android'
             return
@@ -142,6 +204,40 @@ class GpsMqttApp(App):
             self.on_permissions,
         )
 
+    def start_sensors(self):
+        for name in self.polled:
+            sensor = SENSORS[name][0]
+            if name == 'orientation':
+                sensor.enable_listener()
+            else:
+                sensor.enable()
+
+    def stop_sensors(self):
+        for name in self.polled:
+            sensor = SENSORS[name][0]
+            if name == 'orientation':
+                sensor.disable_listener()
+            else:
+                sensor.disable()
+
+    def poll_sensors(self, dt):
+        for name in self.polled:
+            sensor, attribute, fields = SENSORS[name]
+            values = getattr(sensor, attribute)
+            if name == 'barometer':
+                values = [values]
+            if None not in values:
+                self.publish(name, dict(zip(fields, values)))
+        self.readings = '\n'.join(
+            f'{name}: ' + ', '.join(f'{value:.6g}' for value in reading.values())
+            for name, reading in self.latest.items()
+        )
+
+    def publish(self, name, reading):
+        message = {'sensor': name, 'time': time.time(), **reading}
+        self.client.publish(self.topics[name], json.dumps(message))
+        self.latest[name] = reading
+
     @mainthread
     def on_permissions(self, permissions, grants):
         if all(grants):
@@ -151,13 +247,7 @@ class GpsMqttApp(App):
             self.gps_status = 'GPS: permission denied (allow precise location)'
 
     def on_location(self, **location):
-        fix = {'time': time.time(), **location}
-        self.client.publish(self.topic, json.dumps(fix))
-        self.show_fix(fix)
-
-    @mainthread
-    def show_fix(self, fix):
-        self.last_fix = '\n'.join(f'{key}: {value}' for key, value in fix.items())
+        self.publish('gps', location)
 
     @mainthread
     def on_provider_status(self, stype, status):
diff --git a/pc/subscriber.py b/pc/subscriber.py
index f1ae62f..d151e55 100644
--- a/pc/subscriber.py
+++ b/pc/subscriber.py
@@ -1,42 +1,42 @@
-"""Receives the phone's GPS fixes from the MQTT broker, prints them and appends them to a CSV file."""
+"""Receives the phone's sensor readings from the MQTT broker, prints them and appends them to one CSV file per sensor."""
 import argparse
 import csv
 import getpass
 import json
+import os
 
 import paho.mqtt.client as mqtt
 
-COLUMNS = ['time', 'lat', 'lon', 'altitude', 'speed', 'bearing', 'accuracy']
-
 parser = argparse.ArgumentParser(description=__doc__)
-parser.add_argument('topic', help='topic shown in the app, e.g. phone-gps')
+parser.add_argument('topics', nargs='+', help="topics set in the app, e.g. phone/gps phone/gyroscope, or 'phone/#' for all")
 parser.add_argument('--host', required=True, help='broker address, e.g. abc123.ala.us-east-1.emqxsl.com')
 parser.add_argument('--port', type=int, default=8883)
 parser.add_argument('--user', required=True)
 parser.add_argument('--password', help='asked for if omitted')
-parser.add_argument('--csv', default='gps_log.csv', help='output file, new fixes are appended')
+parser.add_argument('--out', default='log', help='output folder, readings are appended to <sensor>.csv')
 args = parser.parse_args()
 password = args.password or getpass.getpass('MQTT password: ')
-
-csv_file = open(args.csv, 'a', newline='')
-csv_writer = csv.DictWriter(csv_file, fieldnames=COLUMNS, extrasaction='ignore')
-if csv_file.tell() == 0:
-    csv_writer.writeheader()
+os.makedirs(args.out, exist_ok=True)
 
 
 def on_connect(client, userdata, flags, reason_code, properties):
     if reason_code.is_failure:
         print(f'Connection refused: {reason_code}')
         return
-    print(f'Connected, listening on {args.topic}')
-    client.subscribe(args.topic)
+    print(f'Connected, listening on {", ".join(args.topics)}')
+    client.subscribe([(topic, 0) for topic in args.topics])
 
 
 def on_message(client, userdata, message):
-    fix = json.loads(message.payload)
-    print(fix)
-    csv_writer.writerow(fix)
-    csv_file.flush()
+    reading = json.loads(message.payload)
+    print(reading)
+    path = os.path.join(args.out, reading.pop('sensor') + '.csv')
+    is_new = not os.path.exists(path)
+    with open(path, 'a', newline='') as csv_file:
+        csv_writer = csv.DictWriter(csv_file, fieldnames=list(reading))
+        if is_new:
+            csv_writer.writeheader()
+        csv_writer.writerow(reading)
 
 
 client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
@@ -50,4 +50,3 @@ try:
     client.loop_forever()
 except KeyboardInterrupt:
     client.disconnect()
-    csv_file.close()
```
