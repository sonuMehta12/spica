# Spica — Android

The web prototype, native: Kotlin + Jetpack Compose against the same API.
How it looks: `THEME.md` at the root.

## Layout

```
app/src/main/java/com/sonu/spica/
  data/      the wire (Wire.kt), the one HTTP client (Http.kt), the translator (Api.kt), app shapes
  logic/     pure ports of the prototype's arithmetic — tasks, chain, metrics, notes, profile edits, the door's film
  state/     AppState (one immutable value), SpicaViewModel (the usePersonaOS hook), derive()
  ui/        theme tokens, common primitives, and one package per screen
app/src/debug/     DevLogin — a laptop-minted session for the emulator
app/src/release/   DevLogin stub — the path does not exist in a release build
app/src/main/res/font/         Newsreader and Anek Latin, bundled (variable; OFL)
app/src/main/assets/licenses/  the fonts' and the icons' licences
tools/phosphor_kt.py           Phosphor SVGs → ui/common/Ph.kt
```

Rules that hold here as on the web: every colour and font through
`ui/theme/Tokens.kt` (the Jamun theme, `THEME.md`); a CSS px is
a dp; copy is English; writes are optimistic but never silent.

**Icons are Phosphor**, compiled in only as used. To add one, fetch its SVG into
a folder for its weight and regenerate — the script's docstring has the URL:

```bash
python3 tools/phosphor_kt.py <folder with regular/ fill/ bold/>
```

## Setup (once per machine)

`local.properties` (not committed):

```
sdk.dir=/Users/<you>/Library/Android/sdk
spica.apiBase=lan
spica.googleClientId=<the Web client id from frontend/.env>
```

`lan` (the default) bakes the laptop's current Wi-Fi address into a debug build,
so the same APK reaches the dev backend from a **phone on the same Wi-Fi** and
from the emulator. The address is read on every build; after the network hands
the laptop a new one, rebuild. Any other value — `http://10.0.2.2:8001`, a
tunnel URL — is used as written. Release builds read `spica.apiBaseRelease`
and speak HTTPS only.

For a phone to reach it, the backend must listen on all interfaces (the
`backend` launch config runs uvicorn with `--host 0.0.0.0`) and the Mac's
firewall must let Python accept incoming connections.

The build needs JDK 17:

```bash
JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home ./gradlew :app:assembleDebug
```

## Signing in on the emulator

Google sign-in needs an **Android** OAuth client in Google Cloud (package
`com.sonu.spica`, the debug key's SHA-1). Until that exists, a debug build
takes a session minted on the laptop:

```bash
cd backend && PYTHONPATH=. uv run python scripts/dev_session.py --user <user id> --out /tmp/cortex_token
```

```bash
adb shell "run-as com.sonu.spica sh -c 'mkdir -p files && cat > files/dev_token'" < /tmp/cortex_token
```

The app reads the file on its next start and deletes it. The token never
touches a command line or logcat; delete `/tmp/cortex_token` afterwards.

To get the SHA-1 for the OAuth client:

```bash
keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android -keypass android
```

## The card gallery (debug builds)

Every card the thread can draw, rendered by the same code, from real payloads
(copied from the dev chat history) and sample live rows — nothing is written:

```bash
adb shell am start -n com.sonu.spica/.CardGalleryActivity
```

Add `--es section <word>` to open at a card (`--es section To-do`). It lives in
`app/src/debug/` and never ships in a release build.

`--es section door` shows the door alone, without signing out. Add
`--el film_ms <ms>` to freeze its film at that millisecond of film time — the
web's door takes `?filmMs=<ms>` in a dev build — so the two films can be set
side by side at the same moment (`logic/FilmDots.kt` and
`frontend/src/door/filmDots.ts` are one table, written twice).
