# shufflekit

Flash music onto an **iPod shuffle 3rd or 4th generation** from a modern Mac or Linux box. No iTunes. No Music.app. The shuffle just looks like a FAT32 disk. We write the play database it actually reads.

Apple's Music app on recent macOS often mounts the thing as a USB stick and never shows it as a device. The player is fine. The computer-side app is what died.

## What it does

- Finds a mounted shuffle (`iPod_Control/iTunes/iTunesSD`)
- Lists the tracks that will actually play
- Copies MP3 / AAC onto the hashed `F00`… folders
- Rebuilds `iTunesSD` (bdhs v3)
- Speaks track names into `Speakable/Tracks` so 3rd gen VoiceOver still works
- Ships a local web UI for drag-and-drop

It will not restore firmware. It will not talk to AirPods. 3rd gen still needs the old wired Apple earbuds with the inline remote.

## Install

```bash
python3 -m pip install -e .
```

Or just run from the repo:

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

`serve` opens `http://127.0.0.1:8765/`. Drop files there.

If someone long ago dragged MP3s into a folder on the disk (classic `musique/` mistake), those files sit there and never play. `rebuild --orphans` puts them in the database.

Every write copies `iTunesSD` to `iTunesSD.bak` first.

## Battery

The Mac cannot read a numeric percent. USB exposes the disk, not the fuel gauge.

If VoiceOver said **low battery**, believe it. Leave it plugged in.

| LED | Charge |
|---|---|
| Green | 50–100% |
| Orange | 25–49% |
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
