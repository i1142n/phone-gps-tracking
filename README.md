# Phone GPS → MQTT

Android app (Kivy + Plyer + paho-mqtt, built with Buildozer) that publishes the phone's GPS fixes to a private MQTT broker (EMQX Cloud Serverless, free). A PC script receives them and logs them to CSV, e.g. as input for a Kalman filter simulation.

```
app/   Android app (main.py, buildozer.spec)
pc/    subscriber.py: receive, print, log to CSV
```

## Message format

One JSON message per fix (at most 1 per second), QoS 0, on the topic set in the app (default `phone-gps/<random id>`):

```json
{"time": 1794049269.79, "lat": 52.0, "lon": 7.6, "altitude": 60.0, "speed": 1.2, "bearing": 90.0, "accuracy": 4.5}
```

| Field      | Unit                                                              |
|------------|-------------------------------------------------------------------|
| `time`     | Unix time in s (phone clock when the fix arrived)                 |
| `lat, lon` | degrees (WGS84)                                                   |
| `altitude` | m                                                                 |
| `speed`    | m/s                                                               |
| `bearing`  | degrees                                                           |
| `accuracy` | m, 68 % radius; usable as measurement noise in the Kalman filter  |

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

1. In the app, enter Host = address, User and Password (Port stays `8883`), press **Start** and allow *precise* location.
2. On the PC, subscribe with the same address, user and the topic shown in the app. The password is prompted, so it stays out of your shell history:

```bash
cd pc
pip install -r requirements.txt
python subscriber.py <topic> --host <address> --user <user>                   # appends to gps_log.csv
python subscriber.py <topic> --host <address> --user <user> --csv walk1.csv
```


## Notes

- Keep the app open in the foreground (the screen stays on). Android throttles location updates for apps in the background.
- Plyer listens to all location providers (GPS, network, ...), so some fixes can be coarse network positions. Filter them by `accuracy` or use `accuracy` as measurement noise.

