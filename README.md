# Phone sensors → MQTT

Android app (Kivy + Plyer + paho-mqtt, built with Buildozer) that publishes the phone's GPS fixes and sensor readings to a private MQTT broker (EMQX Cloud Serverless, free). A PC script receives them and logs them to CSV, e.g. as input for a Kalman filter simulation.

```
app/   Android app (main.py, buildozer.spec)
pc/    subscriber.py: receive, print, log to one CSV per sensor
```

## Sensors and messages

The app has one row per sensor: a checkbox to publish it and the topic it is published on (default `phone/<sensor>`). Sensors with the same topic share that topic.

| Sensor          | Fields                                         | Unit                                |
|-----------------|------------------------------------------------|-------------------------------------|
| `gps`           | `lat, lon, altitude, speed, bearing, accuracy` | degrees (WGS84), m, m/s, degrees, m |
| `accelerometer` | `x, y, z`                                      | m/s², includes gravity              |
| `gyroscope`     | `x, y, z`                                      | rad/s                               |
| `compass`       | `x, y, z`                                      | µT (magnetic field)                 |
| `barometer`     | `pressure`                                     | hPa                                 |
| `gravity`       | `x, y, z`                                      | m/s²                                |
| `orientation`   | `yaw, pitch, roll`                             | rad                                 |

Each reading is one JSON message (QoS 0) with the sensor's name, the phone's clock in Unix seconds and the fields above:

```json
{"sensor": "gps", "time": 1794049269.79, "lat": 52.0, "lon": 7.6, "altitude": 60.0, "speed": 1.2, "bearing": 90.0, "accuracy": 4.5}
{"sensor": "accelerometer", "time": 1794049269.81, "x": 0.1, "y": 0.2, "z": 9.8}
```

- GPS fixes arrive at most once per second, all other sensors 5 times per second (the rate Plyer reads them at).
- All GPS fields come from the location fix: `speed` and `bearing` are computed by the GNSS chip, not by a separate sensor. `accuracy` is the 68 % radius, usable as measurement noise in the Kalman filter.
- `x, y, z` are in the phone's frame: x to the right, y up, z out of the screen.
- `gravity` and `orientation` are not sensors of their own: Android computes them from the accelerometer, gyroscope and compass.

## Build and install the app

### 1. System packages

You need a C toolchain, **Java 17** (newer Java versions do not work with the Android build tools), cmake, zip and unzip. 

### 2. Python environment

Buildozer needs its own Python 3.11 environment (conda, or a venv if you don't use conda):

```bash
conda create -n buildozer python=3.11
conda activate buildozer
pip install buildozer cython
```

### 3. Build

Run in `app/` (where `buildozer.spec` is), with the `buildozer` environment active:

```bash
cd app
JAVA_HOME=/usr/lib/jvm/java-17-openjdk buildozer android debug
```

`JAVA_HOME` makes the build use Java 17 even if another version is your default.

The first build takes a long time, that's normal!

### 4. Install on the phone

Enable USB debugging on the phone, plug it in, then run in `app/`:

```bash
buildozer android deploy run logcat
```

This installs the APK, starts the app and shows the phone's log until you press Ctrl+C. You can also copy the APK from `app/bin/` to the phone and install it by hand.

## Broker setup (EMQX Cloud Serverless, free)

App and PC talk through a private MQTT broker. EMQX gives 1GB free data-transfer each month, should be enough for a prototype.

1. Sign up at <https://www.emqx.com/en/cloud/serverless-mqtt> and create a **Serverless** deployment. 
2. In the deployment's overview, copy the **address** (e.g. `abc123.ala.eu-central-1.emqxsl.com`).
3. Under **Access Control → Authentication**, add a username and password.

## Use

1. In the app, enter Host = address, User and Password (Port stays `8883`), tick the sensors you want, press **Start** and allow *precise* location.
2. On the PC, subscribe with the same address and user to one or more topics. The password is prompted, so it stays out of your shell history:

```bash
cd pc
pip install -r requirements.txt
python subscriber.py phone/gps --host <address> --user <user>                      # one sensor
python subscriber.py phone/gps phone/gyroscope --host <address> --user <user>      # a combination
python subscriber.py 'phone/#' --host <address> --user <user> --out walk1          # all, into walk1/
```

Readings are appended to `<sensor>.csv` in the output folder (default `log/`). Every file has a `time` column to align the sensors.

## Notes

- Keep the app open in the foreground (the screen stays on). Android throttles location updates for apps in the background.
- Plyer listens to all location providers (GPS, network, ...), so some fixes can be coarse network positions. Filter them by `accuracy` or use `accuracy` as measurement noise.
- A sensor the phone doesn't have (often the barometer) simply publishes nothing.
- With all sensors ticked the app sends about 30 messages per second, roughly 10 MB per hour of the free 1 GB.
