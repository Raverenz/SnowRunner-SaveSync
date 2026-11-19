# Third-party notices and provenance

The MIT license applies to original project code and documentation. It does not transfer ownership of game content, trademarks,
third-party datasets or dependencies. Attribution is not a substitute for redistribution permission.

## Catalog data

| Files | Origin and contents | Redistribution status |
| --- | --- | --- |
| `catalog.py` | Names, map/upgrade relationships and identifiers collected from MapRunner on 2026-11-11 | No explicit redistribution license or permission has been confirmed in this preparation. |
| `unlock_ids.py` | Component identifiers checked against a locally installed `initial.pak` | Technical identifiers; no claim of ownership of game identifiers. |
| `prices.py` | Nominal numeric prices, identifiers, defaults and labels extracted from a local `initial.pak` on 2026-11-11 | Not relicensed as MIT; no specific redistribution permission has been confirmed. |
| `catalog_languages.py` | A subset of localized labels used by the existing catalog, extracted from local game string tables | Third-party translations; no specific redistribution permission has been confirmed. |
| `experience.py` | Independently implemented XP/rank conversion using published cumulative thresholds | Threshold source: MapRunner rank/XP chart. |

Full prose accidentally present as a part label has been removed from the generated catalogs.
No original game archives, XML files, full language tables, graphics, audio or real save files are intended for the source or release packages.
The generator scripts require the user’s own local `initial.pak`; they do not download the game.

## Distribution decision

The maintainer has chosen to include the existing catalog snapshots and localized labels in the free application.
No specific permission from the relevant rights holders has been obtained or asserted. This decision does not relicense
third-party data under MIT. The sources and rights status above remain documented for transparency.

Sources:
- https://www.maprunner.info/upgrades
- https://www.maprunner.info/pl/modyfikacje
- https://www.maprunner.info/pl/resources/rank-xp
- https://www.maprunner.info/legal/privacy-policy
- https://store.steampowered.com/eula/1465360_eula_0
- https://expeditions-guides-staging.saber.games/truck_modding/tags_and_attributes_of_trucks/enginevariants/engine/gamedata/

## Format research

The following public projects were consulted for save-format information. No source file from them is included as a dependency or vendored module:
- https://github.com/randombits-dev/snowrunner-save-editor
- https://github.com/AlexDeww/SnowrunnerSaveMerger

## Binary dependencies

The applications use Python and Tcl/Tk. Windows executables are produced with PyInstaller and contain its bootloader.
Python, Tcl/Tk and PyInstaller retain their own licenses. The packaging script includes available license texts in `THIRD_PARTY_LICENSES.txt`.
PyInstaller’s GPL license has a bootloader exception; that exception does not change the licenses of software/data bundled with an application.
Build-only dependencies are listed and pinned in `requirements-build.txt`.

- Python: https://docs.python.org/3/license.html
- Tcl/Tk: https://www.tcl-lang.org/software/tcltk/license.html
- Bundled Tcl 8.6.15 license fallback: https://github.com/tcltk/tcl/blob/core-8-6-15/license.terms
- PyInstaller: https://pyinstaller.org/en/stable/license.html
