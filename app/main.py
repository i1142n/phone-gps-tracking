"""Android app: publishes the phone's GPS fixes and sensor readings as JSON to an MQTT broker."""
import json
import os
import time

import certifi
import paho.mqtt.client as mqtt
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import platform
from plyer import accelerometer, barometer, compass, gps, gravity, gyroscope, spatialorientation

DEFAULTS = {
    'host': '',
    'port': '8883',
    'user': '',
    'password': '',
}

SENSORS = {
    'accelerometer': (accelerometer, 'acceleration', ['x', 'y', 'z']),
    'gyroscope': (gyroscope, 'rotation', ['x', 'y', 'z']),
    'compass': (compass, 'field', ['x', 'y', 'z']),
    'barometer': (barometer, 'pressure', ['pressure']),
    'gravity': (gravity, 'gravity', ['x', 'y', 'z']),
    'orientation': (spatialorientation, 'orientation', ['yaw', 'pitch', 'roll']),
}

POLL_INTERVAL = 0.2

KV = '''
<FieldLabel@Label>:
    size_hint_x: None
    width: dp(110)
    text_size: self.size
    valign: 'middle'

<Field@TextInput>:
    multiline: False

<SensorRow>:
    size_hint_y: None
    height: dp(44)
    spacing: dp(8)

    CheckBox:
        id: enabled
        size_hint_x: None
        width: dp(32)
    FieldLabel:
        text: root.sensor
    Field:
        id: topic

BoxLayout:
    orientation: 'vertical'
    padding: dp(16)
    spacing: dp(8)

    ScrollView:
        BoxLayout:
            orientation: 'vertical'
            spacing: dp(8)
            size_hint_y: None
            height: self.minimum_height
            disabled: app.running

            GridLayout:
                cols: 2
                spacing: dp(8)
                size_hint_y: None
                height: self.minimum_height
                row_default_height: dp(44)
                row_force_default: True

                FieldLabel:
                    text: 'Host'
                Field:
                    id: host
                FieldLabel:
                    text: 'Port'
                Field:
                    id: port
                    input_filter: 'int'
                FieldLabel:
                    text: 'User'
                Field:
                    id: user
                FieldLabel:
                    text: 'Password'
                Field:
                    id: password
                    password: True

            BoxLayout:
                id: sensors
                orientation: 'vertical'
                spacing: dp(8)
                size_hint_y: None
                height: self.minimum_height

    Button:
        text: 'Stop' if app.running else 'Start'
        size_hint_y: None
        height: dp(56)
        on_release: app.stop_sending() if app.running else app.start_sending()

    Label:
        text: app.mqtt_status + '\\n' + app.gps_status
        size_hint_y: None
        height: dp(56)

    Label:
        text: app.readings
        font_size: sp(12)
        text_size: self.size
        valign: 'top'
        size_hint_y: None
        height: dp(120)
'''


class SensorRow(BoxLayout):
    sensor = StringProperty()


class GpsMqttApp(App):
    running = BooleanProperty(False)
    mqtt_status = StringProperty('MQTT: not connected')
    gps_status = StringProperty('GPS: stopped')
    readings = StringProperty('')

    def build(self):
        root = Builder.load_string(KV)
        self.store = JsonStore(os.path.join(self.user_data_dir, 'settings.json'))
        saved = self.store.get('settings') if self.store.exists('settings') else {}
        for key, default in DEFAULTS.items():
            root.ids[key].text = saved.get(key, default)
        self.rows = {}
        for name in ['gps', *SENSORS]:
            row = SensorRow(sensor=name)
            row.ids.topic.text = saved.get(name + '_topic', 'phone/' + name)
            row.ids.enabled.active = saved.get(name + '_enabled', True)
            root.ids.sensors.add_widget(row)
            self.rows[name] = row
        return root

    def on_start(self):
        if platform == 'android':
            gps.configure(on_location=self.on_location, on_status=self.on_provider_status)

    def start_sending(self):
        settings = {key: self.root.ids[key].text.strip() for key in DEFAULTS}
        for name, row in self.rows.items():
            settings[name + '_topic'] = row.ids.topic.text.strip()
            settings[name + '_enabled'] = row.ids.enabled.active
        if not settings['host'] or not settings['port']:
            self.mqtt_status = 'MQTT: enter host and port first'
            return
        self.store.put('settings', **settings)
        self.topics = {name: settings[name + '_topic'] for name in self.rows if settings[name + '_enabled']}
        self.polled = [name for name in self.topics if name in SENSORS and platform == 'android']
        self.latest = {}
        self.connect_mqtt(settings)
        self.start_gps()
        self.start_sensors()
        self.poll_event = Clock.schedule_interval(self.poll_sensors, POLL_INTERVAL)
        self.running = True

    def stop_sending(self):
        if platform == 'android':
            gps.stop()
        self.stop_sensors()
        self.poll_event.cancel()
        self.client.disconnect()
        self.client.loop_stop()
        self.gps_status = 'GPS: stopped'
        self.running = False

    def connect_mqtt(self, settings):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.username_pw_set(settings['user'], settings['password'])
        self.client.tls_set(ca_certs=certifi.where())
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.connect_async(settings['host'], int(settings['port']))
        self.client.loop_start()
        self.mqtt_status = 'MQTT: connecting...'

    def start_gps(self):
        if 'gps' not in self.topics:
            self.gps_status = 'GPS: off'
            return
        if platform != 'android':
            self.gps_status = 'GPS: only available on Android'
            return
        from android.permissions import Permission, request_permissions
        request_permissions(
            [Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION],
            self.on_permissions,
        )

    def start_sensors(self):
        for name in self.polled:
            sensor = SENSORS[name][0]
            if name == 'orientation':
                sensor.enable_listener()
            else:
                sensor.enable()

    def stop_sensors(self):
        for name in self.polled:
            sensor = SENSORS[name][0]
            if name == 'orientation':
                sensor.disable_listener()
            else:
                sensor.disable()

    def poll_sensors(self, dt):
        for name in self.polled:
            sensor, attribute, fields = SENSORS[name]
            values = getattr(sensor, attribute)
            if name == 'barometer':
                values = [values]
            if None not in values:
                self.publish(name, dict(zip(fields, values)))
        self.readings = '\n'.join(
            f'{name}: ' + ', '.join(f'{value:.6g}' for value in reading.values())
            for name, reading in self.latest.items()
        )

    def publish(self, name, reading):
        message = {'sensor': name, 'time': time.time(), **reading}
        self.client.publish(self.topics[name], json.dumps(message))
        self.latest[name] = reading

    @mainthread
    def on_permissions(self, permissions, grants):
        if all(grants):
            gps.start(minTime=1000, minDistance=0)
            self.gps_status = 'GPS: waiting for fix...'
        else:
            self.gps_status = 'GPS: permission denied (allow precise location)'

    def on_location(self, **location):
        self.publish('gps', location)

    @mainthread
    def on_provider_status(self, stype, status):
        self.gps_status = f'GPS: {stype} {status}'

    @mainthread
    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.mqtt_status = f'MQTT: {reason_code}'

    @mainthread
    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.mqtt_status = f'MQTT: disconnected ({reason_code})'


if __name__ == '__main__':
    GpsMqttApp().run()
