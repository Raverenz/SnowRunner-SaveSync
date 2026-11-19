# SnowRunner SaveSync

Offline Windows tools for sharing co-op discoveries and inspecting SnowRunner PC saves.

**SaveSync** is the player’s manager. **Host Packer** prepares the host’s save package.
English is the default interface language; Polish, German, French, Spanish and Portuguese are included.

[Polska instrukcja](README.pl.md) · [Build and verify](docs/BUILD.md) · [Host Packer](HOST-PACKER-README.md) · [Data sources and rights](THIRD_PARTY_NOTICES.md)

## Features

- Find local Steam and Documents/Epic saves; choose an account and slot when several are found.
- Load the host’s main save or a flat ZIP package. Offer the newest ZIP beside the manager at startup.
- Merge missing host unlocks and collected map upgrades; manually enable or remove supported upgrade unlocks.
- Edit money, add/set XP, set a level, or sync XP upwards to the host. XP and rank are saved together.
- Expand vehicles into their installed parts; show garage, storage and supported STS map locations.
- Estimate company value from cash, owned chassis, installed equipment and spare parts.
- Host Packer automatically selects the main save and matching slot’s STS files, explains each file and creates a verified flat ZIP.
- All operations are local. No application telemetry, uploads, online account or administrator access is required.
- Optional offline cats with rarity rolls and fireworks.

## Download and run

When a public release is available, download the appropriate Windows x64 ZIP from this repository’s **Releases** page.
Extract it into its own folder and run `SnowRunner-SaveSync.exe` or `SnowRunner-HostPacker.exe`.
The executable does not require a separate Python installation. Keep downloaded distribution ZIPs outside the extracted application folder;
only put the host’s actual save ZIP beside SaveSync.

Until a release has been published, run from source using the instructions below. Local preview builds are not GitHub-attested releases.

## Player workflow

1. Close SnowRunner and let cloud synchronization finish. Keep a separate backup of your save folder.
2. Start SaveSync, select the host package and your player save, then load them.
3. Review upgrade synchronization and XP. XP sync is enabled when both saves contain valid XP; it only increases the player’s XP.
   Money changes and manual XP/level editing are optional. They also work without a host.
4. Click **Preview changes**, inspect the report, then **Save with backup**.

A timestamped `.bak` containing the exact original bytes is created beside the player save.
SaveSync refuses to overwrite a save that changed after loading/preview. The host package and STS files are read-only.

**Restore:** close the game, preserve the current file separately, then copy the chosen `.bak` back to the original CompleteSave filename.
Resolve cloud conflicts using the version you intend to keep.

## Host workflow

1. Close the game and open Host Packer.
2. Search for saves or browse to a `CompleteSave*.cfg` / `.dat`, then choose the correct profile and slot.
3. Inspect the selected files and click **Create ZIP package**.
4. Send the ZIP to the players. They use it as the host input; they do not replace their save folder with it.

The package contains the selected main save and matching STS files directly, without subfolders.
Source saves are never modified. Files from other slots and fog files are excluded.

## Compatibility and limits

- Windows x64 is the executable target. UTF-8 JSON PC saves (`.cfg` / `.dat`, including BOM and trailing NUL) are supported.
- Xbox/Microsoft Store containers and console saves are not supported.
- Upgrade sync copies missing `unlockedItemNames` entries, which may include vehicle unlocks, plus collected `upgradesGiverData` entries.
  It does not copy missions or replace the player’s fleet.
- Rank-based shop requirements are separate from exploration/objective requirements. Setting level 7 sets 6900 XP and rank 7;
  it does not mark every map pickup as found. The author reports that XP/rank editing works in-game (2026-11-19).
  This is not a claim of testing every feature against every game version.
- Valuation uses nominal catalog prices, not sale prices or historical spending. NG+ multipliers, damage and fuel are not included.
  Missing prices, unsupported STS layouts or ambiguous ownership produce an incomplete estimate, never invented prices.
- STS can include mission and guest vehicles. Ambiguous records require explicit ownership confirmation for valuation.
- Catalogs are snapshots and may lag game updates, DLC or mods. Unsupported entries retain technical identifiers.
- Both apps share `%APPDATA%\SnowRunnerSaveSync\settings.json`. Language switching preserves loaded data and pending operations.
  Windows-native dialog buttons may follow the Windows language.

## Run from source

Use Python 3.12 with Tkinter; the tested build version is **3.12.10 x64**.
The applications use only the Python standard library at runtime.

```powershell
python savesync.py
python host_packer_app.py
python -m unittest discover -v
```

See [BUILD.md](docs/BUILD.md) for pinned build dependencies, release packaging, checksums and provenance verification.

## Trust and antivirus reports

Public source makes review and independent builds possible. It does not by itself establish the origin or safety of a downloaded EXE.
GitHub-built release artifacts are intended to include SHA-256 checksums and build provenance attestations.
These identify a build and its source; they are not a malware-free certification or a Windows Authenticode signature.

A previous local one-file build was flagged by 6/70 VirusTotal engines. The exact cause has not been established by a full binary audit.
PyInstaller packaging can trigger false positives. Do not disable antivirus protection just because this project is open source.
See [SECURITY.md](SECURITY.md) for reporting guidance.

## License and credits

Original project code is licensed under [MIT](LICENSE). Third-party names, identifiers, price/catalog data and extracted game translations
are documented separately in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); the project does not claim to relicense them under MIT.
SnowRunner and vehicle names belong to their respective owners. This is an unofficial project, not affiliated with or endorsed by Saber or Focus.
