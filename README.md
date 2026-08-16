# shufflekit

> **Educational and personal use only.** This project is for people who still own an iPod shuffle and want to sync music from their own Apple Music library to their own device, for their own personal listening. It does not crack, remove, or circumvent DRM. Apple Music streams are recorded via the system's own audio output (BlackHole) - the same as holding a microphone to a speaker. Use only with content you have a legitimate right to access. Respect artists and labels.

> **Disclaimer:** This project is not affiliated with or endorsed by Apple Inc. iPod and Apple Music are trademarks of Apple Inc. This software is provided "as is" under the MIT license, with no warranty. You are responsible for complying with applicable laws and terms of service.

Flash music onto an **iPod shuffle 3rd or 4th generation** from a modern Mac or Linux box. No iTunes. No Music.app. The shuffle just looks like a FAT32 disk. We write the play database it actually reads.

Apple's Music app on recent macOS often mounts the thing as a USB stick and never shows it as a device. The player is fine. The computer-side app is what died.

## What it does

- Finds a mounted shuffle (`iPod_Control/iTunes/iTunesSD`)
- Lists the tracks that will actually play
- Copies MP3 / AAC onto the hashed `F00`... folders
- Rebuilds `iTunesSD` (bdhs v3)
- Speaks track names into `Speakable/Tracks` so 3rd gen VoiceOver still works
- Ships a local web UI for drag-and-drop
- Browse Apple Music playlists and import them
- Record DRM Apple Music streams to the shuffle via BlackHole (real-time)

It will not restore firmware. It will not talk to AirPods. 3rd gen still needs the old wired Apple earbuds with the inline remote.

## Install

```bash
python3 -m pip install -e .
```

Or run from the repo:

```bash
PYTHONPATH=. python3 -m shufflekit detect
```

## Use

Plug the shuffle in. Wait until you see a volume (often named `IPOD`).

```bash
shufflekit detect
shufflekit list
shufflekit add ~/Music/song.mp3 ~/Music/other.m4a
shufflekit rebuild --orphans --voiceover
shufflekit serve
```

`serve` opens `http://127.0.0.1:8765/`. Drop files there or browse your Apple Music playlists.

### Apple Music playlist import

The web UI lists all your Music.app playlists. Click one to see how many tracks are copyable (file-backed) vs DRM streams.

- **File-backed tracks** (purchased, CD rips) copy directly in seconds.
- **Apple Music streams** (`.m4p`, FairPlay DRM) are recorded in real-time via [BlackHole](https://existential.audio/blackhole/), a free virtual audio cable. Music.app plays the DRM track; BlackHole routes the audio to a file. A 3-minute song takes 3 minutes.

To enable recording, just click **Install BlackHole** in the web UI. It downloads the official pkg and opens the macOS installer for you (enter your Mac password, reboot after). Or install manually:

```bash
brew install --cask blackhole-2ch
# Reboot after install
```

After reboot, click **Open Audio MIDI Setup** in the web UI (or open it manually). Create a Multi-Output Device that includes both your speakers and BlackHole 2ch, so you can hear music while it records.

### Orphan files

If someone long ago dragged MP3s into a folder on the disk (classic `musique/` mistake), those files sit there and never play. `rebuild --orphans` puts them in the database.

Every write copies `iTunesSD` to `iTunesSD.bak` first.

## Battery

The Mac cannot read a numeric percent. USB exposes the disk, not the fuel gauge.

If VoiceOver said **low battery**, believe it. Leave it plugged in.

| LED | Charge |  
|---|---|  
| Green | 50-100% |  
| Orange | 25-49% |  
| Red | under 25% |  
| Blinking red | under 1% |  
| Blinking orange | talking to the computer |  

3rd gen charges over USB. Give it a couple of hours if it is red.

## How the database works

A shuffle ignores loose files. Playback is `iTunesSD` only:

- `bdhs` header
- `hths` offset table
- one `rths` record per track (path, duration, type, VoiceOver id)
- `hphs` / `lphs` master playlist

That layout was read off a live 3rd gen (USB `05ac:1302`) and written back the same way. Tests round-trip that file.

## Dev

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT. See `LICENSE`.