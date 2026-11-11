# phone-gps-tracking
Android app (Kivy + plyer + paho-mqtt, built with buildozer) that publishes the phone's GPS fixes and sensor readings (accelerometer, gyroscope, compass, barometer, gravity, orientation) as JSON over MQTT/TLS to an EMQX Cloud Serverless broker, one configurable topic per sensor; `pc/subscriber.py` receives them and logs one CSV per sensor for a Kalman filter simulation.

## Commands
- Build (in `app/`): `PATH=$HOME/miniconda3/envs/buildozer/bin:$PATH JAVA_HOME=/usr/lib/jvm/java-17-openjdk buildozer android debug` (incremental ~1 min, from scratch 20–40 min; APK in `app/bin/`)
- Install + start on phone (in `app/`): `PATH=$HOME/miniconda3/envs/buildozer/bin:$PATH buildozer android deploy run`, then tap "Install" on the phone
- Phone log: `~/.buildozer/android/platform/android-sdk/platform-tools/adb logcat -d | grep python`
- PC: `python pc/subscriber.py <topic> [<topic> ...] --host <emqx address> --user <user> [--out <folder>]` (password prompted, port 8883; `'phone/#'` for all sensors)
- Test without phone: venv with kivy, plyer, paho-mqtt, certifi; import `app/main.py` with `KIVY_NO_ARGS=1`, set `app.root = SimpleNamespace(ids={key: SimpleNamespace(text=...)})` for the `DEFAULTS` keys, `app.rows = {name: SimpleNamespace(ids=SimpleNamespace(topic=SimpleNamespace(text=...), enabled=SimpleNamespace(active=True)))}` for `'gps'` and each name in `SENSORS`, and `app.store`; call `start_sending()`, `on_location(lat=..., ...)`, tick `kivy.clock.Clock`. To fake the polled sensors, replace the plyer objects in `main.SENSORS` with `SimpleNamespace(enable=..., disable=..., <attribute>=values)`, set `main.platform = 'android'` and stub `main.gps` and `GpsMqttApp.start_gps`. Public TLS test broker: `broker.emqx.io:8883` (any login; delivers only ~10 messages/s, raise `main.POLL_INTERVAL` to 1).
- Build the real widget tree headless: `SDL_VIDEODRIVER=offscreen`, `app.root = app.build()`, `Window.add_widget(app.root)`; sizes and ids work, screenshots come out blank.

## Structure
- `app/.buildozer/`: ~4 GB build cache (gitignored); SDK/NDK live in `~/.buildozer/`

## Conventions
- Code as simple and readable as possible, no added comments.
- The user commits; don't commit unless asked.
- Payload: `sensor`, `time` and the sensor's fields from `SENSORS` in `main.py` (GPS: plyer's location fields). The subscriber takes the CSV columns from the message, nothing to keep in sync.
- Log changes in `CHANGES.md`.

## Notes for Claude
- `!` shell has no conda env: plain `buildozer` and `conda activate` fail there; prefix `PATH=$HOME/miniconda3/envs/buildozer/bin:$PATH`. `logcat` without `-d` blocks the session.
- Phone (Xiaomi, HyperOS 3, Android 15) is often unplugged: adb commands then hang, wrap them in `timeout`. Installs need "Install via USB" in developer options and a tap on the phone.
- `buildozer.spec`: no version pins in `requirements` (p4a adds the newest version too → pip conflict). Keep `p4a.branch = develop` (release 2026.05.09 corrupts its pip venv → `cannot import name 'capture_logging'`; if it reappears: `rm -rf app/.buildozer/android/platform/build-*/build/venv`). Keep plyer from GitHub: PyPI 2.1.0 lacks `onLocationChanged(List)`, so no fixes on Android 12+.
- Kivy: never name a method `on_<property>`; Kivy calls it on every change (caused an endless loop with `on_gps_status`).
- plyer's sensors (accelerometer etc.) update at a fixed ~5 Hz (`SENSOR_DELAY_NORMAL`), hence `POLL_INTERVAL = 0.2`. The user decided on 11.11.2026 that this is fine and wants no rate setting and no own pyjnius listener.
- EMQX Serverless only accepts 8883 (TLS); 1883 times out. Its dashboard "Topics" counts only subscribed topics, so publishing alone shows 0.

## Current state (11.11.2026)
- Done: multi-sensor app (plyer sensors, polled) and multi-topic subscriber, stub-tested end to end against `broker.emqx.io` (see `CHANGES.md`). The user reports the previous GPS-only build worked on the phone.
- Installed on the phone on 11.11.2026 11:10; it starts without a Python error. Not checked yet: how the new UI looks, pressing Start, plyer's sensor classes, receiving on the PC.
- `app/bin/` APK: see `CHANGES.md` for whether it matches the code. Tell the user before deploying to the phone.
- Seen on the phone 11.11.2026 (user's runs, `pc/walk1/`): all sensors except the barometer deliver at ~5 Hz, multi-topic and `phone/#` subscriptions work. Open: GPS only sent one burst of 4 identical fixes at the moment Start was pressed and nothing in the seconds after (9 s in one run, 3 s in another); the old GPS-only build sent a burst every second (`pc/walk1.csv`). Not yet clear whether that is being indoors or a regression; test with a longer run outdoors and `adb shell dumpsys location`. No `barometer.csv` either (phone may have none).
- Next: settle the GPS question, check on the phone that all sensor rows show readings, record a walk with the subscriber; then build the Kalman filter simulation on the CSVs.
- Example run:
  ```bash
  cd ~/phone-gps-tracking/app
  PATH=$HOME/miniconda3/envs/buildozer/bin:$PATH JAVA_HOME=/usr/lib/jvm/java-17-openjdk buildozer android debug
  PATH=$HOME/miniconda3/envs/buildozer/bin:$PATH buildozer android deploy run
  cd ../pc && python subscriber.py 'phone/#' --host zf6c0cf0.ala.us-east-1.emqxsl.com --user <user> --out walk1
  ```
- Placeholders: `app/buildozer.spec:4` `package.domain = org.example` (replace before publishing anywhere); host/user/password are entered in the app, not in code.
