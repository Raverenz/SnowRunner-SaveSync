# SnowRunner SaveSync 1.0

Version 1.0: SaveSync for players and Host Packer for the co-op host.

Download the Windows x64 ZIP for the tool you need, extract it into its own folder and run the EXE.
The source ZIP is for review and independent builds. SHA256SUMS.txt lists release artifact hashes;
GitHub-built ZIPs also have provenance attestations (see docs/BUILD.md).

Supported: SnowRunner PC JSON CompleteSave cfg/dat, with same-slot STS for map vehicles.
Not supported: console saves or Xbox/Microsoft Store save containers.

Close the game before editing or packing. SaveSync creates a timestamped backup beside the player’s main save.
XP/rank editing was confirmed in-game by the author; other combinations may still contain bugs.
Valuation is nominal and may be incomplete for mods, unknown parts and unsupported STS records.

Both tools are offline and default to English; five additional languages are included.
Executables are not Authenticode-signed. An antivirus detection must be investigated; open source and attestations are not proof of safety.

Catalog snapshots and localized labels are included by the maintainer’s decision; see THIRD_PARTY_NOTICES.md for their origins and rights status.
