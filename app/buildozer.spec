[app]
title = GPS MQTT
package.name = gpsmqtt
package.domain = org.example
source.dir = .
source.include_exts = py
version = 0.1

# plyer from GitHub (pinned commit): the PyPI release 2.1.0 never receives GPS fixes on Android 12+
requirements = python3,kivy,https://github.com/kivy/plyer/archive/4853b3a92a786237af966b86d07fa8242eee9aec.zip,paho-mqtt,certifi,openssl

orientation = portrait
fullscreen = 0

# INTERNET for MQTT, LOCATION for GPS, WAKE_LOCK keeps the screen on while the app is open
android.permissions = INTERNET, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, WAKE_LOCK
android.wakelock = True
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

# The p4a release (2026.05.09) corrupts its pip venv when it installs packages a second time
# (2nd arch or rebuild) -> "cannot import name 'capture_logging'". Fixed on develop.
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 1
