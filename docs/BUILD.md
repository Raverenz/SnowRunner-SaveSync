# Build, test and verify

## Build environment

Windows x64, Python **3.12.10** with Tkinter. Use a new virtual environment:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe -m unittest discover -v
.venv\Scripts\python.exe tools/build_release.py
```

The build produces two versioned ZIPs, a source ZIP, `build-info.json` and `SHA256SUMS.txt` in `release/`.
The source ZIP is generated from an explicit allowlist; it never recursively copies the working directory.
The private host ZIP and existing EXEs in `dist/` are not inputs to the release builder.
PyInstaller is invoked with `--noupx`. This is a transparent packaging choice, not a promise to eliminate antivirus detections.

`VERSION` is the release version. For `1.0`, use the tag `v1.0`.
The script refuses a mismatched tag version and records the source commit (or `uncommitted` for a local preview).
A published build should come from a clean, reviewed commit and a successful GitHub workflow.

## GitHub workflows

- `ci.yml`: test on Windows with Python 3.12.10 on pushes, pull requests and manual runs; read-only repository permissions.
- `release.yml`: run manually on a version tag. Run tests, build fresh packages, attest artifacts and create a **draft release**.
  It never publishes a release automatically. Review the included notices and assets before manually publishing the draft.
  The workflow uses the repository’s short-lived `GITHUB_TOKEN`; do not add a personal access token to source files.

Actions are pinned to full commit hashes. Dependabot proposes updates. The first GitHub run must still be verified;
local tests cannot prove a hosted Windows job or attestation service will succeed.

## Verify a download

In PowerShell:

```powershell
Get-FileHash .\SnowRunner-SaveSync-1.0-windows-x64.zip -Algorithm SHA256
```

Compare the result against `SHA256SUMS.txt` from the same release.
To verify a GitHub build’s provenance with GitHub CLI:

```powershell
gh attestation verify .\SnowRunner-SaveSync-1.0-windows-x64.zip --repo Raverenz/SnowRunner-SaveSync
```

Attestations require a successful GitHub release workflow and are not present on local preview builds.
Checksums detect changed bytes; a checksum next to a malicious file is not an independent safety guarantee.
The build currently is **not claimed to be bit-for-bit reproducible** across machines. Dependency versions are pinned,
but Windows, tools and build metadata can still affect the EXE. Build provenance is separate from Authenticode signing.

## Catalog generators

Optional local maintenance commands (not required for building the current catalog snapshot):

```powershell
python build_prices.py 'C:\Path\To\SnowRunner\preload\paks\client\initial.pak'
python build_catalog_languages.py 'C:\Path\To\SnowRunner\preload\paks\client\initial.pak'
```

Never upload `initial.pak` or private saves. See `THIRD_PARTY_NOTICES.md` before distributing generated data.
