# VoiceMitra Android app

The patient's phone app: rings like a normal call (FCM push -> full-screen call screen, even when locked) and
connects to the VoiceMitra voice agent over LiveKit. Spec and status: `SPEC.md`. Backend contract: `../API.md`.

- Kotlin + Jetpack Compose, Gradle (wrapper in this folder), minSdk 26, compile/target SDK 37.
- Application id `in.voicemitra.patient` (registered with Firebase); the Kotlin code is under
  `com.voicemitra.patient` because `in` is a Kotlin keyword.
- No Android Studio and **no emulator** needed: build from the command line, test on a real phone.

## One-time setup (Windows)

What this PC has (installed 2026-11-04, all user-local, outside the repo):

| What | Where |
|---|---|
| Android SDK: `cmdline-tools/latest`, `platform-tools` (adb), `platforms/android-37.0`, `build-tools/36.0.0` (AGP's default, installed by the build itself) | `C:\Users\apoor\Android\Sdk` |
| JDK | the existing `C:\Program Files\Java\jdk-25.0.3` (AGP 9.5 + Gradle 9.8 build fine on it) |
| Gradle 9.8.2 + dependency cache | `C:\Users\apoor\.gradle` (downloaded by `gradlew`) |

To set up another Windows PC:

1. Download Google's **command-line tools only** (developer.android.com/studio, "Command line tools only") and
   unzip so that `<sdk>\cmdline-tools\latest\bin\sdkmanager.bat` exists, e.g. `<sdk>` = `C:\Users\<you>\Android\Sdk`.
2. Install the packages (the new sdkmanager uses `/` in package names; `;` breaks in `cmd`). The first command
   asks you to accept Google's SDK licence:
   ```bash
   set JAVA_HOME=C:\Program Files\Java\jdk-25.0.3
   <sdk>\cmdline-tools\latest\bin\sdkmanager.bat --sdk_root=<sdk> platform-tools platforms/android-37.0
   ```
   No emulator or system images are needed.
3. Point the build at the SDK: create `mobile/android/local.properties` (gitignored) with
   `sdk.dir=C\:/Users/<you>/Android/Sdk` (forward slashes, the colon escaped).
4. Firebase (for push rings): put the project's `google-services.json` in `mobile/android/app/` (gitignored).
   Without it the app still builds and runs; it just can't be rung while closed.

## Build

From `mobile/android/` (Git Bash; in PowerShell use `$env:JAVA_HOME=...` and `.\gradlew.bat`):

```bash
JAVA_HOME="/c/Program Files/Java/jdk-25.0.3" ./gradlew.bat assembleDebug
```

The APK is `app/build/outputs/apk/debug/app-debug.apk`. `assembleRelease` gives
`app/build/outputs/apk/release/app-release.apk` (signed with the debug key, fine for sideloading).

## Install on a phone

- **USB:** on the phone, Settings -> About phone -> tap "Build number" 7 times -> Developer options -> USB
  debugging on. Plug in, accept the prompt on the phone, then:
  ```bash
  /c/Users/apoor/Android/Sdk/platform-tools/adb.exe install -r app/build/outputs/apk/debug/app-debug.apk
  ```
- **Without a cable:** send the APK file to the phone (WhatsApp/Drive/USB copy), open it, allow "Install unknown
  apps" for that app when asked, install.

## Server URL

The default is the tunnel hostname (`DEFAULT_SERVER_URL` in `app/build.gradle.kts`). It can be changed in the
app's settings, e.g. to `http://<pc-ip>:8000` on the same Wi-Fi (debug builds allow plain http).
