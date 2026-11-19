# Security policy

This project is maintained on a best-effort basis. Use the latest reviewed release and retain backups.

For a security issue, use this repository’s **Security → Report a vulnerability** when private reporting has been enabled.
If unavailable, open an issue requesting a private reporting channel without exploit details or personal data.
Do not publicly attach real saves, account identifiers, access tokens or full private file paths.

For antivirus findings, include the SHA-256, release/version, engine/detection name and a public report link if available.
A report link can expose information already uploaded to that service; do not upload private saves for diagnosis.
No finding is automatically dismissed as a false positive. Do not disable protection to run the program.

The applications operate locally. They read registry locations for discovery, read selected saves/STS, store a shared language setting,
and write only user-requested save edits/backups or package exports. There is no application telemetry or automatic upload.
The Python/PyInstaller runtime extracts temporary files when a one-file EXE starts.
