# Phone GPS → MQTT

Android app (Kivy + Plyer + paho-mqtt, built with Buildozer) that publishes the phone's GPS fixes to an MQTT broker (default: the public HiveMQ broker). A PC script receives them and logs them to CSV, e.g. as input for a Kalman filter simulation.

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

You need a C toolchain, **Java 17** (newer Java versions do not work with the Android build tools), cmake, zip and unzip. On Manjaro/Arch:

```bash
sudo pacman -S --needed base-devel jdk17-openjdk cmake zip unzip
```

For other distros, see the [Buildozer installation docs](https://buildozer.readthedocs.io/en/latest/installation.html).

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

The first build downloads the Android SDK/NDK (~3.5 GB) and compiles Python, Kivy etc., so it takes 20–40 minutes and prints debug logs the whole time. It ends with `Android packaging done!`, and the APK is in `app/bin/`. Later builds take under a minute. Lines like `*** Error compiling ... badsyntax_....py` are harmless: they come from Python's own test files, which contain deliberately broken code.

### 4. Install on the phone

Enable USB debugging on the phone, plug it in, then run in `app/`:

```bash
buildozer android deploy run logcat
```

This installs the APK, starts the app and shows the phone's log until you press Ctrl+C. You can also copy the APK from `app/bin/` to the phone and install it by hand.

## Use

1. Open the app, check the settings and press **Start**. Allow *precise* location.
2. On the PC, subscribe with the topic shown in the app:

```bash
cd pc
pip install -r requirements.txt
python subscriber.py phone-gps/1a2b3c4d                 # appends to gps_log.csv
python subscriber.py phone-gps/1a2b3c4d --csv walk1.csv
```

To feed a Kalman filter live instead of from CSV, put the filter update into `on_message` in `subscriber.py`.

## Private broker (EMQX Cloud Serverless, free)

`broker.hivemq.com` is public: anyone who knows or guesses the topic can read your location. An EMQX Cloud *Serverless* deployment is private (username/password, TLS encrypted), and the app supports it without code changes. (HiveMQ discontinued its free Serverless plan.)

The free quota is 1 million session minutes and 1 GB of traffic per month. Phone + PC use 2 sessions and about 1.5 MB per hour at one fix per second, so that is several hundred hours of recording per month.

1. Sign up at <https://www.emqx.com/en/cloud/serverless-mqtt> and create a **Serverless** deployment. Set the **spend limit to 0**: then it simply stops when the free quota is used up, instead of charging you.
2. In the deployment's overview, copy the **address** (e.g. `abc123.ala.eu-central-1.emqxsl.com`). The port for MQTT over TLS is `8883`.
3. Under **Access Control → Authentication**, add a username and password.
4. In the app, set Host = address, Port = `8883`, plus User and Password. Port 8883 switches TLS on automatically.
5. On the PC, use the same address, user and topic. With `--user`, port 8883 is the default, and the password is prompted, so it stays out of your shell history:

```bash
python subscriber.py <topic> --host abc123.ala.eu-central-1.emqxsl.com --port 8883 --user <user>
```

## Notes

- Keep the app open in the foreground (the screen stays on). Android throttles location updates for apps in the background.
- Plyer listens to all location providers (GPS, network, ...), so some fixes can be coarse network positions. Filter them by `accuracy` or use `accuracy` as measurement noise.
- On a PC the app starts and connects to MQTT, but GPS only works on Android.
- `buildozer.spec` installs plyer from GitHub, not PyPI: plyer 2.1.0 from PyPI never receives GPS fixes on Android 12+ (the app stays at "waiting for fix", see [plyer #687](https://github.com/kivy/plyer/issues/687)).
