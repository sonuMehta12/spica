# Call recorder — Cortex's own ears for calls

> **Archived 2026-09-27 — not being built now.** Work sync
> (`spec/work-sync.md`) comes first. This is the scope and the research for a
> recorder the user intends to build themselves, kept so the build starts from
> what was already learned. Why it waits and what would bring it back:
> `spec/notes.md` § *Call recording — archived*.
>
> Where a claim was read rather than checked, it says so; the sources are at
> the end.

## The need

Most of the user's work decisions and tasks are made on **calls** — WhatsApp
calls and ordinary phone calls — not in scheduled meetings. Wispr Flow's
notetaker hears only what plays on the computer, and Linear holds only what
someone typed. A task agreed on a call reaches nothing unless someone writes it
down afterwards.

## What the user wants to build

Their own recorder, rather than a bought device:

- **Records calls, both sides** — the other person and themselves — the way
  Wispr Flow and Granola record a meeting: system audio for *them*, the
  microphone for *me*.
- **Starts manual.** A button to start and stop.
- **Becomes automatic.** Detect that a call has started — a two-way
  conversation has a recognisable pattern — and record; later, only for
  chosen contacts.
- **Ends in Cortex.** A transcript Cortex can read and pull tasks from.

## How the existing products work

### Desktop notetakers — Wispr Flow, Granola

- Both record **two streams on the computer**: the microphone and system
  audio. No bot joins the call.
- **Two streams give two speakers for free.** The microphone is *Me*,
  system audio is *Them*. Granola labels its transcripts exactly that way —
  two buckets, not one label per person.
- **Detection.** Wispr notices a call on Meet, Zoom, Teams, WhatsApp or
  FaceTime and asks whether to take notes. Granola decides a meeting has ended
  from audio activity, the call app, and the calendar's end time — and says
  detection fails when an app keeps the microphone open or meetings run back
  to back.
- **Audio is not kept.** Granola streams audio to a transcription provider and
  saves none of it.

### Plaud — hardware

- A recorder that clips to the back of the phone (MagSafe). Three
  microphones: two for the room, and a **vibration conduction sensor** that
  reads the phone body's vibration from its earpiece.
- A physical switch between *note* and *call* mode.
- Records **any** call — cellular, WhatsApp, Telegram, Signal — because it
  never asks the phone's operating system for audio.
- Syncs to its app, transcribes in the cloud, and exposes recordings through an
  official Claude connector.

**The lesson in it:** Plaud is hardware because the software path on a phone
is closed. It records from outside the phone, where the OS has no say.

## Why phones are closed

| On the phone | Cellular call | WhatsApp call |
|---|---|---|
| **Android, an ordinary app** | ✗ — the call's audio sources (`VOICE_CALL`, `VOICE_UPLINK`, `VOICE_DOWNLINK`) need `CAPTURE_AUDIO_OUTPUT`, granted only to privileged, pre-installed apps | ✗ — `AudioPlaybackCapture` (Android 10+) cannot capture call or VoIP audio; `VOICE_COMMUNICATION` is a privacy-sensitive source |
| **Android, the Accessibility workaround** | Banned from the Play Store in 2022, and prohibited for Cortex by `CLAUDE.md`. A sideloaded personal app is outside Play policy, but capture quality varies by device and often gets only one side | same |
| **Android, the built-in dialer** (Google Phone, some OEM dialers) | ✓ — and Google Phone can **always record selected numbers**, available in India. It announces the recording to both sides, and the files stay on the phone with no API | ✗ |
| **iPhone** | Apple's Phone app can record, announcing it to both sides; no API and no per-number setting *(read, not verified here)* | ✗ |

## Why the desktop is open

**macOS**

| API | What it gives | Permission |
|---|---|---|
| **Core Audio process taps** — `CATapDescription`, `AudioHardwareCreateProcessTap` (macOS 14.2+; sample code targets 14.4+) | Everything the Mac plays, **or only chosen apps** — e.g. only WhatsApp | *System Audio Recording Only* — narrower than screen recording |
| **ScreenCaptureKit** | System audio, as part of screen capture | *Screen & System Audio Recording* |
| **AVAudioEngine**, voice-processing mode on | The microphone, with echo cancellation — so *them* coming out of the speakers does not appear a second time in *my* track *(read, not verified here)* | Microphone |

**Windows** does the same with WASAPI loopback capture.

**Open source worth studying before writing a line:**

- **AudioCap** (`insidegui/AudioCap`) — sample code for recording system
  audio on macOS 14.4+ with process taps.
- **SystemAudioKit** (`pieralukasz/SystemAudioKit`) — records the microphone
  and system audio **as aligned tracks**: process taps with a ScreenCaptureKit
  fallback, **plus call detection**. The closest thing to the first version
  of this.

## The engineering, as far as it was thought through

### Where calls are captured

Everything above points one way: **the call happens on the laptop, and the
recorder is a Mac app.**

- **WhatsApp calls** — take them on WhatsApp Desktop. A process tap on
  WhatsApp alone captures them without touching anything else the Mac plays.
- **Cellular calls** — an iPhone can route them through a Mac (*Calls from
  iPhone*); whether a process tap hears that audio is **unverified**. For an
  Android phone no equivalent route is known.
- **Calls taken on the phone itself** stay out of reach of software: that is
  Plaud's hardware route, or a rooted personal phone — both out of scope for a
  first version.

This makes the recorder **a new surface**: a native macOS app, beside the web
prototype, the backend and the future Android app.

### Manual first

A menu-bar button. Record the microphone and system audio — or only
WhatsApp's audio — as **two aligned tracks**. Stop, transcribe, send to Cortex.

### Automatic later — knowing a call has started

Three signals, strongest first:

1. **The OS says so.** A call app is holding the microphone. Core Audio can
   report which process is using input — SystemAudioKit's call detection is
   built on signals of this kind *(the exact property to verify)*. Paired with
   *which* app — WhatsApp, FaceTime — this is close to certain.
2. **The conversation pattern — the user's idea.** Voice activity on **both**
   tracks, taking turns. Run voice-activity detection per track; speech on
   both, alternating within a minute, is a call. One track alone is a video
   playing or someone dictating. The call ends after a stretch of silence on
   both tracks, or when the app lets go of the microphone.
3. **Who is on it** — needed to record only chosen contacts. WhatsApp
   Desktop's window carries the contact's name, readable through macOS
   Accessibility permission. That is the desktop permission, not the Android
   Accessibility Service the Play Store bans.

### Transcription

- **Two tracks mean *Me* and *Them* without speaker diarization.**
- **Local** (Whisper, through whisper.cpp or MLX) keeps audio on the laptop.
  **Cloud** (OpenAI's transcription models — Cortex already pays OpenAI) is
  simpler. **Hinglish accuracy on a real call is the deciding test**, and
  neither has been measured.
- **Keep the transcript, drop the audio by default.** A personal-data app
  should hold the least it needs; Granola keeps no audio at all.

### How it reaches Cortex — undecided

- **As a document source in work sync.** The recorder writes transcripts
  somewhere a connector can read, and the routine treats each call like a
  meeting: read once, id recorded.
- **Straight into Cortex.** The recorder is Cortex's *own* client, like the
  phone app, so it posts the transcript to the API and tasks are extracted
  server-side. This is not an outside integration in work sync's sense —
  Cortex owns the recorder.

### Consent

The Google dialer announces a recording to both sides; a Mac recorder
announces nothing. Recording the other person is a legal and a trust question,
and Indian law on it was **not researched**. For the regular work contacts
this is for, telling them once is the simple answer. The product decision — an
audible or visible notice, or none — is made when the recorder is built.

## Decided against, for now

| Option | Why not |
|---|---|
| Buying Plaud | The user prefers to build it and learn the engineering; the device still needs a button pressed on every call |
| Google Phone's *always record selected numbers* as the path | No WhatsApp calls, and the recordings never leave the phone — no API, so nothing reaches Cortex |
| A recorder inside a phone app | Android and iOS close call audio to ordinary apps; the Accessibility workaround is banned by the Play Store and by `CLAUDE.md` |

## If it restarts

1. Read AudioCap and SystemAudioKit.
2. Build the **manual** Mac recorder: one WhatsApp Desktop call, two aligned
   tracks.
3. Measure **Hinglish transcription** on that call — local Whisper against
   cloud.
4. Decide how it reaches Cortex.
5. Then detection: the OS signal first, the conversation pattern second,
   contacts last.

---

### Sources

Read, not verified first-hand:
[Wispr Flow Notetaker](https://wisprflow.ai/notetaker) ·
[Wispr Flow's note-taker works without joining calls](https://www.digitaltrends.com/computing/wispr-flow-launches-an-ai-note-taker-that-works-without-joining-calls/) ·
[Granola — how transcription works](https://docs.granola.ai/help-center/taking-notes/transcription) ·
[Granola labels speakers Me and Them](https://luci.memories.ai/blog/fix-granola-no-speaker-labels) ·
[Plaud Note](https://www.plaud.ai/products/plaud-note-ai-voice-recorder) ·
[Plaud — note vs phone call recording](https://support.plaud.ai/hc/en-us/articles/50837232018585-What-is-the-difference-between-Note-Recording-and-Phone-Call-Recording) ·
[Plaud connector for Claude](https://www.plaud.ai/blogs/news/plaud-mcp-for-chatgpt-and-claude) ·
[Android — sharing audio input](https://developer.android.com/media/platform/sharing-audio-input) ·
[Android — capturing audio in Android Q](https://android-developers.googleblog.com/2019/07/capturing-audio-in-android-q.html) ·
[Google Phone — record calls](https://support.google.com/phoneapp/answer/9803950?hl=en) ·
[AudioCap](https://github.com/insidegui/AudioCap) ·
[SystemAudioKit](https://github.com/pieralukasz/SystemAudioKit) ·
[Recall.ai — system audio on macOS](https://www.recall.ai/blog/how-to-get-access-to-system-audio) ·
[Capturing system audio on macOS in 2026](https://dgrlabs.co/blog/2026-04-25-capturing-system-audio-on-macos-in-2026.html)
