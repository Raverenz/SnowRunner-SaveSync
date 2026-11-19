# SnowRunner — Paker hosta

Osobny program dla hosta: `dist\SnowRunner-HostPacker.exe`. Działa samodzielnie na Windows, bez instalowania Pythona i bez plików źródłowych obok EXE. Gracze nadal korzystają z `SnowRunner-SaveSync.exe`.

## Jak przygotować paczkę

1. Zamknij SnowRunnera i poczekaj na zakończenie synchronizacji chmurowej.
2. Uruchom **SnowRunner-HostPacker.exe**. Program automatycznie wyszuka zapisy Steam, Dokumenty/Epic i OneDrive. Możesz ponowić wyszukiwanie lub wskazać oryginalny CompleteSave ręcznie.
3. Z listy wybierz **konto/profil i slot**. Program pokazuje saldo i XP, a po wczytaniu także rangę i pełną ścieżkę. Jeden znaleziony zapis jest podglądany automatycznie; przy kilku wynikach wybierasz właściwy wiersz.
4. Sprawdź automatyczną listę plików. Nie trzeba zaznaczać plików osobno.
5. Kliknij **Utwórz paczkę ZIP…** i wskaż miejsce zapisu. Proponowana nazwa zawiera numer slotu; istniejące nazwy są omijane przyrostkami `_2`, `_3` itd.
6. Po komunikacie **Gotowe** ZIP jest gotowy do ręcznego wysłania graczom. Każdy wiersz listy ma status **Spakowano**. Przycisk **Kopiuj listę plików** kopiuje nazwy i opisy; **Pokaż folder paczki** otwiera miejsce zapisu.

Gracze kładą otrzymany ZIP obok swojego pliku `SnowRunner-SaveSync.exe`. Manager wykryje najnowszą paczkę i zaproponuje wczytanie hosta. Nie muszą jej rozpakowywać.

## Co trafia do ZIP-a

- Wybrany `CompleteSave*.cfg` / `.dat`: profil, pieniądze, XP, odblokowania, magazyn i garaże.
- Wszystkie istniejące pliki `sts_level_*` / `1_sts_level_*` / `2_sts_level_*` / `3_sts_level_*` tego samego slotu, z folderu wybranego zapisu: stan map i znajdujące się na nich pojazdy oraz inne obiekty.

W ZIP-ie znajdują się bezpośrednio pliki, bez podfolderów. Pozostałe sloty, `fog`, `CommonSslSave` i pozostałe pliki nie są dodawane — paczka służy do funkcji SaveSync, nie jest kopią zapasową całej gry.

Przykłady opisów w programie:

- `CompleteSave.cfg` — Zapis główny, slot 1: profil, gotówka, XP, odblokowania, magazyn i garaże.
- `sts_level_us_01_01.cfg` — Stan mapy i pojazdy: Czarna Rzeka — Michigan.
- `sts_level_us_01_02.cfg` — Stan mapy i pojazdy: Zapora Smithville — Michigan.

Nazwy map są odczytywane z wbudowanego katalogu. Nieznana/modowa mapa jest nadal pakowana z jej identyfikatorem zamiast zgadywania nazwy. Gdy STS nie ma, można utworzyć paczkę z samym CompleteSave; lista jasno informuje, że nie dostarczy ona danych o pojazdach pozostawionych na mapach.

## Sprawdzanie paczki

Program nie modyfikuje źródłowych zapisów. Sprawdza ich rozmiary i skróty przed i po pakowaniu, wykrywa też zmianę listy STS. Jeśli gra lub chmura zmieni plik, eksport zostaje przerwany — zamknij grę, kliknij **Odśwież pliki** i spróbuj ponownie. Gotowy ZIP przechodzi kontrolę zawartości i CRC. Dopiero po pomyślnej weryfikacji pojawia się pod docelową nazwą.

Przerwanie pakowania usuwa plik roboczy i zachowuje wcześniejszy ZIP. Nadpisanie istniejącej paczki wymaga wyboru tej ścieżki i potwierdzenia w oknie zapisu. Limity są zgodne z managerem: 32 MB na plik, 256 MB łącznej zawartości. Rozmiar przy liście plików oznacza sumę źródeł przed kompresją.

## Źródła i testy

Uruchomienie ze źródeł: `Uruchom-Paker.cmd` (Python 3.10+ z Tkinter).

Budowanie osobnego EXE:
`python -m PyInstaller --onefile --windowed --name SnowRunner-HostPacker host_packer_app.py`

`py -3 -m unittest test_host_packer -v` — 7 testów pakera: wybór slotu, opisy, zgodność paczki z managerem, niezmienność źródeł, przerwanie eksportu, brak przypadkowego nadpisania i przepływ interfejsu. Cały projekt przechodzi 50 testów.

## Wybór języka

Packer domyślnie używa angielskiego. W prawym górnym rogu można wybrać English, Polski, Deutsch, Français, Español lub Português. Zmiana działa natychmiast, również podczas wyszukiwania lub tworzenia ZIP-a; zachowuje profil, zaznaczenie pliku i postęp operacji. Tłumaczenia obejmują opis zawartości plików, komunikaty oraz raport kopiowany do schowka. Same nazwy plików i zawartość paczki pozostają niezmienione.

Preferencja jest wspólna z SaveSync: `%APPDATA%\SnowRunnerSaveSync\settings.json`. Jeżeli wcześniej wybrano język w managerze, packer użyje tego ustawienia. Bez ustawienia uruchomi się po angielsku. Tłumaczenia są dołączone i nie wymagają internetu. Standardowe przyciski systemowych okien mogą być w języku Windows.
