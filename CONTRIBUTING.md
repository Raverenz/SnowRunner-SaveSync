# Contributing

Use Python 3.12 with Tkinter. Run `python -m unittest discover -v` before proposing changes.
Follow the existing standard-library approach; discuss new runtime dependencies first.

Use synthetic saves in tests. Never commit real saves, host packages, account IDs or local credentials.
Keep save keys, canonical mode values and filenames independent of UI translations.
Changes to merge/write logic must preserve unrelated data, backups and changed-source detection.
Unknown STS layouts and unknown prices must remain explicitly unsupported rather than guessed.

Include the concrete behavior change, relevant tests and known limitations in pull requests.
For catalog changes, document origin and applicable redistribution terms; do not upload original game files.
See THIRD_PARTY_NOTICES.md for catalog provenance, rights status and the maintainer’s distribution decision.
