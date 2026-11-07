"""Android app: publishes the phone's GPS fixes as JSON to an MQTT broker."""
import json
import os
import time
import uuid

import certifi
import paho.mqtt.client as mqtt
from kivy.app import App
from kivy.clock import mainthread
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.utils import platform
from plyer import gps

FIELDS = ['host', 'port', 'topic', 'user', 'password']
DEFAULTS = {
    'host': 'broker.hivemq.com',
    'port': '1883',
    'topic': f'phone-gps/{uuid.uuid4().hex[:8]}',  # random, so nobody else uses the same topic
    'user': '',
    'password': '',
}

KV = '''
<FieldLabel@Label>:
    size_hint_x: None
    width: dp(90)

<Field@TextInput>:
    multiline: False

BoxLayout:
    orientation: 'vertical'
    padding: dp(16)
    spacing: dp(8)

    GridLayout:
        cols: 2
        spacing: dp(8)
        size_hint_y: None
        height: self.minimum_height
        row_default_height: dp(44)
        row_force_default: True
        disabled: app.running

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
            text: 'Topic'
        Field:
            id: topic
        FieldLabel:
            text: 'User'
        Field:
            id: user
        FieldLabel:
            text: 'Password'
        Field:
            id: password
            password: True

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
        text: app.last_fix
        text_size: self.size
        valign: 'top'
'''


class GpsMqttApp(App):
    running = BooleanProperty(False)
    mqtt_status = StringProperty('MQTT: not connected')
    gps_status = StringProperty('GPS: stopped')
    last_fix = StringProperty('')

    def build(self):
        root = Builder.load_string(KV)
        # Restore the settings from the last run
        self.store = JsonStore(os.path.join(self.user_data_dir, 'settings.json'))
        settings = self.store.get('settings') if self.store.exists('settings') else DEFAULTS
        for key in FIELDS:
            root.ids[key].text = settings.get(key, DEFAULTS[key])
        return root

    def on_start(self):
        if platform == 'android':
            gps.configure(on_location=self.on_location, on_status=self.on_provider_status)

    # ---------- Start / Stop ----------

    def start_sending(self):
        settings = {key: self.root.ids[key].text.strip() for key in FIELDS}
        self.store.put('settings', **settings)
        self.topic = settings['topic']

        # MQTT: connect in the background, paho reconnects automatically
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        if settings['user']:
            self.client.username_pw_set(settings['user'], settings['password'])
        if settings['port'] == '8883':  # TLS port, e.g. HiveMQ Cloud
            self.client.tls_set(ca_certs=certifi.where())
        self.client.connect_async(settings['host'], int(settings['port']))
        self.client.loop_start()

        # GPS: ask for permission first, the GPS starts in on_permissions
        if platform == 'android':
            from android.permissions import Permission, request_permissions
            request_permissions(
                [Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION],
                self.on_permissions,
            )
        else:
            self.gps_status = 'GPS: only available on Android'

        self.running = True

    def stop_sending(self):
        if platform == 'android':
            gps.stop()
        self.client.disconnect()
        self.client.loop_stop()
        self.gps_status = 'GPS: stopped'
        self.running = False

    # ---------- Callbacks (called from Android / paho threads) ----------

    @mainthread
    def on_permissions(self, permissions, grants):
        if all(grants):
            gps.start(minTime=1000, minDistance=0)  # one fix per second at most
            self.gps_status = 'GPS: waiting for fix...'
        else:
            self.gps_status = 'GPS: permission denied (allow precise location)'

    def on_location(self, **kwargs):
        # kwargs: lat, lon, altitude, speed, bearing, accuracy
        fix = {'time': time.time(), **kwargs}
        self.client.publish(self.topic, json.dumps(fix))
        self.show_fix(fix)

    @mainthread
    def show_fix(self, fix):
        self.last_fix = '\n'.join(f'{key}: {value}' for key, value in fix.items())

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
