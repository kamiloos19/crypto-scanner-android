[app]
title = Crypto Scanner
package.name = cryptoscanner
package.domain = org.cryptoscanner
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0

requirements = python3==3.11.0,kivy==2.2.1,kivymd==1.2.0,requests,urllib3,certifi,charset-normalizer,idna,beautifulsoup4,soupsieve

orientation = portrait
fullscreen = 0

android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 26
android.sdk = 33
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
android.gradle_dependencies = androidx.core:core:1.9.0
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1
