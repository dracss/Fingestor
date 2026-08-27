[app]
title = FinGestor
package.name = fingestor
package.domain = br.com.fingestor
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf
version = 0.1
requirements = python3,kivy==2.3.0,kivymd==1.2.0,pillow
orientation = portrait
fullscreen = 0

# Android build configuration
android.api = 35
android.minapi = 21
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True

# AndroidX is required for the FileProvider used to share the receipt (PDF/PNG)
android.enable_androidx = True

# INTERNET is optional (reserved for future cloud sync). Saving/sharing files
# uses the app-private storage + FileProvider and needs no runtime permission.
android.permissions = INTERNET

[buildozer]
log_level = 2
warn_on_root = 0
