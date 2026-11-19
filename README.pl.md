# SnowRunner SaveSync

Osobny program hosta do tworzenia paczek: `dist\SnowRunner-HostPacker.exe`. Instrukcja: [HOST-PACKER-README.md](HOST-PACKER-README.md).

Lokalny program Windows: jeden zapis hosta i jeden zapis gracza. Każdy gość uruchamia go u siebie, korzystając z kopii aktualnego zapisu hosta.

## Użycie

1. Zamknij SnowRunnera i poczekaj na zakończenie synchronizacji chmurowej.
2. Uruchom `dist\SnowRunner-SaveSync.exe` (nie wymaga Pythona).
3. Program zaproponuje wczytanie najnowszego ZIP-a hosta z folderu EXE i spróbuje znaleźć Twój zapis. Możesz też ręcznie wybrać plik hosta i sprawdź wskazany własny plik `CompleteSave*.cfg` lub `CompleteSave*.dat`, następnie kliknij **Wczytaj zapisy**.
4. Dopiero po wczytaniu swojego zapisu zobaczysz obecne saldo oraz opcje **Dodaj kwotę** i **Ustaw saldo**. Program pokazuje także saldo po planowanej zmianie. Dla samej edycji pieniędzy możesz pominąć hosta i odznaczyć synchronizację.
5. Lista ulepszeń pokazuje region, mapę, część, pasujące pojazdy oraz stan u hosta i gracza. Użyj wyszukiwarki i filtra brakujących ulepszeń. Zaznacz wiersz, by zobaczyć cały opis. Przykład: **Michigan — Czarna Rzeka — Podwyższone zawieszenie — Chevrolet CK1500**.
6. Checkbox w kolumnie **Po zapisie** pozwala ręcznie odblokować lub usunąć odblokowanie części. Możesz też zaznaczyć wiersz i użyć spacji albo checkboxa pod listą. Host nie jest wymagany do ręcznej edycji. Przycisk **Cofnij ręczne zmiany** przywraca plan wynikający z wczytanego zapisu i opcji synchronizacji.
7. Kliknij **Podgląd zmian**, sprawdź raport i wybierz **Zapisz z kopią zapasową**.

Po zapisie saldo jest odczytywane ponownie, a tryb pieniędzy wraca do „Bez zmian”. Zmiana ścieżki wymaga ponownego wczytania; zmiana opcji unieważnia wcześniejszy podgląd.

## Paczka hosta ZIP

Połóż ZIP hosta **w tym samym folderze co `SnowRunner-SaveSync.exe`**. Paczka powinna zawierać bezpośrednio pliki, bez podfolderów, np.:

```text
SnowRunner-SaveSync.exe
host-2026-11-19.zip
  CompleteSave.cfg
  sts_level_us_01_01.cfg
  sts_level_us_01_02.cfg
```

Przy starcie program sprawdza ZIP-y w folderze EXE i wybiera najnowszy według **daty modyfikacji archiwum**. Nazwa ZIP-a i daty plików wewnątrz paczki nie decydują o wyborze. Następnie pokazuje pytanie **„Znaleziono plik zapisu hosta — Czy chcesz go wczytać?”**, z nazwą archiwum, plikiem i slotem, saldem, XP, rangą i liczbą posiadanych ciężarówek. Odpowiedź **Tak** wczytuje hosta, a **Nie** pozostawia wybór ręczny. Jeśli najnowsza paczka jest błędna, program zgłasza problem zamiast po cichu wybierać starszą.

Jeżeli ZIP zawiera kilka plików CompleteSave/slotów, program najpierw prosi o wskazanie właściwego zapisu. Dla wybranego slotu wykorzystuje wyłącznie pasujące pliki STS. Pliki `fog` i inne niepowiązane pliki nie są potrzebne do tego odczytu.

Po zaakceptowaniu ZIP-a nadal działa automatyczne szukanie zapisu gracza. Po wybraniu wykrytego pliku program wczytuje oba zapisy. Jeśli zapis gracza został już wybrany wcześniej, jest wczytywany od razu z zaakceptowanym hostem. Przy polu **Zapis hosta → Wybierz…** można ręcznie otworzyć zarówno ZIP, jak i zwykły `.cfg` / `.dat`.

Paczka służy wyłącznie do odczytu. Program rozpakowuje wybrany zapis i jego STS do osobnego katalogu tymczasowego, nie do folderu zapisów gracza. W polu hosta pozostaje ścieżka ZIP-a. Archiwum nie jest modyfikowane i nie trzeba go rozpakowywać ręcznie. Pliki tymczasowe są usuwane po zmianie hosta lub zamknięciu programu. Podmiana ZIP-a po wczytaniu unieważnia poprzedni podgląd — wczytaj zapisy ponownie.

Dla uruchomienia ze źródeł przez `Uruchom.cmd` przeszukiwany jest folder źródeł. W wersji EXE zawsze chodzi o folder właściwego pliku EXE, nie katalog roboczy ani folder skrótu. Obsługiwane są płaskie, niezaszyfrowane ZIP-y do 512 MB, do 256 MB łącznej zawartości i 32 MB na odczytywany plik.

## Automatyczne znajdowanie zapisu gracza

Po uruchomieniu EXE program szuka zapisów w tle, pozostawiając okno dostępne do obsługi. Przy polu **Twój zapis** jest również przycisk **Znajdź mój save**, który pozwala ponowić wyszukiwanie.

Wyszukiwanie obejmuje instalację Steam ustaloną z rejestru Windows (także poza domyślnym folderem), standardowe foldery Steam oraz katalog `My Games\SnowRunner\base\storage` w Dokumentach, przekierowanych Dokumentach i OneDrive. Sprawdzane są konta Steam i cztery standardowe sloty PC `.cfg` / `.dat`. Program sprawdza poprawność znalezionych zapisów i nie przeszukuje rekurencyjnie całych dysków. Kontenery Xbox/Microsoft Store pozostają nieobsługiwane.

- **Jeden wynik i puste pole gracza:** ścieżka zostanie uzupełniona automatycznie.
- **Kilka kont/slotów lub wcześniej wskazany plik:** pojawi się lista z kontem/profilem, slotem, czasem ostatniej zmiany, saldem, XP i pełną ścieżką. Wybierz wiersz i kliknij **Użyj wybranego zapisu** lub dwukrotnie kliknij wiersz. Najnowsze wyniki są na górze; program nie wybiera sam jednego z kilku slotów.
- **Brak wyników:** nadal można użyć **Wybierz…** i wskazać plik ręcznie.

Bez zaakceptowanej paczki hosta wykrycie jedynie ustawia ścieżkę. **Wczytaj zapisy** służy wtedy do wczytania danych. Z zaakceptowanym ZIP-em hosta wybór wykrytego zapisu gracza wczytuje oba pliki. Edycja pieniędzy pojawia się dopiero po wczytaniu danych gracza. Wyszukiwanie nie zmienia plików ani pola hosta. Nie zastępuje ścieżki wybranej ręcznie podczas trwającego skanowania ani zapisu wczytanego przed zakończeniem automatycznego wyszukiwania.

## Pliki i kopie

Steam: zwykle `<Steam>\userdata\<ID>\1465360\remote\CompleteSave.cfg`.
Epic: zwykle `Dokumenty\My Games\SnowRunner\base\storage\<ID>\CompleteSave.dat`.
Nazwy z numerami oznaczają kolejne sloty. Wybierz właściwy zapis gracza; host i gracz muszą być różnymi plikami.

Obok zmienianego zapisu powstaje dokładna kopia `CompleteSave.cfg.<data-czas>.bak`. Przywracanie: przy zamkniętej grze zachowaj bieżący zapis i skopiuj wybrany backup pod pierwotną nazwą. W razie konfliktu chmury wybierz świadomie właściwą wersję. Zapis jest atomowy, a zmiana pliku od podglądu przerywa operację.

## Zakładka Pojazdy

Po wczytaniu zapisu przejdź do **Pojazdy**. Wybierz **Gracz** lub **Host**. Każdy pojazd ma osobną gałąź drzewa — rozwiń ją wskaźnikiem po lewej stronie, aby zobaczyć silnik, skrzynię biegów, zawieszenie, wyciągarkę, opony i dodatki. Są też przyciski **Rozwiń wszystko**, **Zwiń wszystko** i wyszukiwarka obejmująca pojazdy, mapy i części.

Dla garaży pokazywana jest lokalizacja np. **Michigan — Czarna Rzeka — Garaż**. Magazyn ciężarówek jest globalny, więc widnieje jako **Magazyn ciężarówek (globalny, bez przypisania do mapy)**. Pole `retainedMapId` nie jest traktowane jako aktualna lokalizacja magazynu. Uzupełnienia z katalogu są jawnie oznaczone jako **Domyślne wg katalogu**; nieznane nazwy pozostają identyfikatorami z pliku.

Przy otwieraniu oryginalnie nazwanego pliku program automatycznie szuka stanów map z tego samego folderu i slotu:

- `CompleteSave.cfg` / `.dat` → `sts_level_*.cfg` / `.dat`
- `CompleteSave1.cfg` / `.dat` → `1_sts_level_*.cfg` / `.dat`
- `CompleteSave2.cfg` / `.dat` → `2_sts_level_*.cfg` / `.dat`
- `CompleteSave3.cfg` / `.dat` → `3_sts_level_*.cfg` / `.dat`

Możesz również wybrać **Wczytaj pliki STS…** i wskazać pliki dla wybranego hosta/gracza. Mieszanie slotów jest odrzucane. Dla zapisów przemianowanych (np. `host.cfg`) wskaż właściwy zestaw ręcznie. Zmiana ścieżki lub ponowne wczytanie przywraca automatyczny wybór plików.

**Pojazdy na mapach:** program dekoduje segment wyposażenia w rekordach GUID STS: silnik, skrzynię, wyciągarkę, typ kół, obręcze, komplet opon, skalę kół, zawieszenie i pełną listę dodatków. Weryfikuje liczbę dodatków, układ pól, koła i znaczniki odblokowania. Obsługiwane są dwa warianty segmentu, z dodatkowym polem wody i bez niego. Nieobsługiwane lub niepełne rekordy nie są wyceniane na podstawie samych znalezionych nazw.

Automatyczne przypisanie pojazdu wymaga kompletnego odczytu, znacznika `isUnlocked` i liczby egzemplarzy zgodnej z brakującymi pojazdami z `ownedTrucks`. Nieodblokowane pojazdy świata gry pozostają poza wyceną. Zweryfikowane pojazdy pokazują rzeczywistą mapę i listę części w drzewku, np. **Michigan — Zapora Smithville — Na mapie**. Ich wyposażenie jest doliczane do majątku bez ponownego liczenia podwozi.

**Niejednoznaczność w co-opie:** STS może zawierać kilka odblokowanych egzemplarzy tego samego modelu. W takim przypadku program pokazuje **Możliwy rekord**, a użytkownik wybiera właściwy wiersz i klika **To mój pojazd — dolicz**. Przycisk jest dostępny wyłącznie dla kompletnego i odblokowanego rekordu. **Cofnij potwierdzenia** wycofuje wybory. Potwierdzenie jest używane tylko do wyceny i podglądu, nie przepisuje własności w grze. Wybory są zachowane podczas zapisu edytowanych pieniędzy/ulepszeń w bieżącej sesji; zmiana ścieżki, nowe pliki STS lub ręczne ponowne wczytanie je resetują.

Ten sam GUID nie jest liczony ponownie w garażu, magazynie ani kolejnych plikach STS. Sprzeczne aktywne kopie tego samego GUID są pomijane z komunikatem zamiast arbitralnego wybrania jednej wersji. Jeżeli pozostała tylko jedna odblokowana kopia, starszy nieodblokowany rekord nie zastępuje jej w wycenie.

STS są wyłącznie odczytywane — program ich nie edytuje. Wadliwe lub zbyt duże pliki są pomijane z komunikatem. Do wyceny używaj CompleteSave oraz STS z tego samego slotu i tego samego momentu zapisu, po zamknięciu gry.

Podsumowanie majątku zostało przeniesione do zakładki **Majątek i XP**, aby pozostawić więcej miejsca na listy pojazdów i ulepszeń.

## Wartość firmy i doświadczenie

Po wczytaniu zapisów program pokazuje osobno dla hosta i gracza **Wartość firmy**, łączne zdobyte **XP** oraz rangę. Można wczytać sam zapis hosta, aby sprawdzić jego majątek bez edycji. Szczegóły wyceny zawierają elementy, ilości, ceny jednostkowe i sumy.

Wartość firmy to **gotówka + podwozia wszystkich posiadanych ciężarówek + zamontowane wyposażenie + posiadane części i dodatki w zapasie**. Uwzględniane są również przyczepy wykazane w magazynie dodatków. Katalog cen obejmuje 185 definicji podwozi/przyczep, 5502 części i dodatki oraz 451 definicji kompletów opon. Ceny pochodzą z lokalnego `initial.pak` z 11.11.2026 i są wbudowane w EXE.

Wycena jest nominalna, według cen katalogowych: nie jest ceną sprzedaży ani sumą wydanych pieniędzy. Mnożniki ekonomii NG+, uszkodzenia, paliwo, ładunek i opłaty nie zmieniają tej wyceny. Odblokowane, ale nieposiadane części nie są liczone. XP i ranga mogą być edytowane i synchronizowane w osobnym panelu.

Licznik `ownedTrucks` zapewnia uwzględnienie także podwozi pojazdów na mapach. Wyposażenie jest odczytywane z opisów ciężarówek w `trucksInWarehouse` i garażach `garagesData`. Silnik, skrzynia, zawieszenie, wyciągarka, komplet opon i dodatki są doliczane oddzielnie do podwozia. Dla nieużytych jeszcze pojazdów DLC uzupełniane jest domyślne wyposażenie z definicji pojazdu. Części w `addons` są liczone według posiadanej liczby sztuk. Powtórzony opis pojazdu z tym samym niepustym `globalId` jest pomijany.

**Wyposażenie z STS:** samo CompleteSave nie zawiera wyposażenia ciężarówek pozostawionych na mapach. Wczytaj pasujące pliki STS z tego samego folderu albo przyciskiem w zakładce Pojazdy. Majątek jest wtedy automatycznie przeliczany osobno dla hosta i gracza; liczba **STS** przy podsumowaniu wskazuje, ile pojazdów mapowych uwzględniono. Szczegóły wyceny oznaczają takie pozycje źródłem **(STS)**. Podgląd zmian pieniężnych również uwzględnia ten majątek.

Jeżeli brakuje ceny części (np. modowej), danych, pewnego przypisania własności lub obsługi danego wariantu STS, panel nadal pokazuje **„co najmniej”** i **„Niepełna wycena”**, a szczegóły wymieniają pominięcia. Nieznane ceny nie są zgadywane. Oczekujące zwroty i oddzielne uszkadzalne dodatki nadal są oznaczane jako brakujące dane. Wartość pozostaje nominalną wyceną opisanych kategorii według katalogu, bez korekt NG+ i bez historii wydatków.

Po zapisaniu zmian pieniężnych wartość firmy jest odczytywana ponownie. Podgląd zmian pokazuje też wartość planowaną po zapisie. Samo dodanie/usunięcie unlocka nie zmienia posiadanego majątku.

Opis cen podwozi i wyposażenia w dokumentacji producenta:
https://expeditions-guides-staging.saber.games/map_modding/creating_a_map/other_map_settings/content_settings/custom_prices_for_trucks_and_upgrades/

## Ręczne odblokowania

Ręczny wybór ma pierwszeństwo przed synchronizacją hosta. Zaznaczenie dodaje dokładny identyfikator części do `unlockedItemNames` i ustawia powiązane punkty `upgradesGiverData` na 2. Odznaczenie usuwa wpis odblokowania i ustawia istniejące powiązane punkty na 0. Istniejące liczniki zebranych ulepszeń dla zmienionych map są aktualizowane. Część występująca w kilku miejscach jest edytowana wspólnie; wszystkie jej powiązane checkboxy wskazują ten sam stan.

Checkbox pokazuje planowany stan wpisu odblokowania garażu, z uwzględnieniem hosta, jeśli synchronizacja jest włączona. Kolumny Host i Gracz pokazują wczytane stany punktu na mapie. Zmiany filtrów nie usuwają ręcznych wyborów. Wczytanie pliku ponownie lub zmiana ścieżki usuwa niezapisany plan ręczny.

Usunięcie odblokowania nie demontuje części z pojazdów, nie usuwa posiadanych części z magazynu i nie zmienia pieniędzy. Dostępność części wynikająca z rangi lub ustawień gry może pozostać niezależna od tego wpisu.

Dokładne identyfikatory 165 pozycji sprawdzono w lokalnych definicjach `initial.pak`. Wpis opon MSH II i nieznane/modowe wpisy nie mają potwierdzonego mapowania i są wyłączone w ręcznym edytorze; program oznacza je „Brak mapowania części”. Katalog oraz mapowanie są wbudowane w EXE; znajomi nie potrzebują dodatkowych plików ani instalacji gry do otwarcia programu.

## Zakres synchronizacji i katalogu

Program dodaje brakujące wpisy `persistentProfileData.unlockedItemNames` i przenosi zebrane ulepszenia (status 2) z `upgradesGiverData`. Zachowuje istniejące postępy gracza. Lista odblokowań obejmuje także pojazdy; obecna wersja przenosi całą tę listę. Synchronizacja ulepszeń nie zmienia misji, magazynu ani odkrycia map. XP jest obsługiwane osobną opcją. Punkty ulepszeń przeniesione z hosta będą oznaczone jako zebrane również u gracza.

Katalog offline zawiera 166 lokalizacji ulepszeń na 56 mapach z MapRunner (stan pobrania 11.11.2026). Polskie nazwy map i opisy rodzajów części, modele pojazdów i nazwy silników pochodzą z katalogu. Część nazw specjalnych może pozostać po angielsku. Stan „Brak danych” oznacza brak wpisu w danym zapisie, a nie potwierdzony stan w grze. Nieznane ulepszenia/modowe mapy nadal są wyświetlane z identyfikatorem i oznaczeniem braku nazwy. Katalog służy do prezentacji; nie dodaje automatycznie wszystkich znajdujących się w nim ulepszeń.

Obsługa: zapisy PC JSON UTF-8, również z BOM i końcowymi NUL. Brak obsługi kontenerów Xbox/Microsoft Store i konsol. Program nie przesyła zapisów przez sieć. Synchronizacja odblokowań jest powtarzalna; ponowne wybranie „Dodaj kwotę” i zapis ponownie doda pieniądze.

## Testy i źródła

`py -3 -m unittest -v` — testy automatyczne: scalanie, zachowanie innych danych, pieniądze, kopie zapasowe, zmiana pliku, katalog, okno, przepływ wczytania/zapisu oraz ręczne checkboxy, priorytet zmian, wspólne części, liczniki i ochrona zamontowanych części, wycena majątku, brak podwójnego liczenia, wiele egzemplarzy, opony, niepełne dane i XP, drzewo pojazdów, lokalizacje garaży, magazyn globalny, dobór slotu STS, oba warianty segmentu wyposażenia, wycena kompletnych rekordów, pomijanie nieodblokowanych pojazdów świata gry, konflikty i duplikaty GUID oraz ręczne potwierdzenia własności, wyszukiwanie kont/slotów, przekierowane Dokumenty, OneDrive, sortowanie i wybór wyników oraz działanie wyszukiwania w tle, wybór najnowszego ZIP-a, potwierdzenie/odmowa wczytania, wiele slotów w paczce, STS hosta, izolacja plików tymczasowych i zachowanie archiwum bez zmian. Dodatkowe testy osobnego pakera obejmują dobór plików slotu, opisy map, zgodność gotowej paczki z managerem, wykrywanie zmiany źródeł i anulowanie eksportu bez uszkodzenia istniejącego ZIP-a. Testy automatyczne wykorzystują sztuczne zapisy. Dodatkowo dekoder sprawdzono odczytem 14 rzeczywistych rekordów STS w trzech lokalnych slotach; 9 pojazdów mapowych przypisano do liczników gracza, a 5 nieodblokowanych pojazdów świata gry pominięto. Autor potwierdził w grze prawidłowe działanie zmiany XP i poziomu (19.11.2026). Nie jest to potwierdzenie wszystkich funkcji na każdej wersji gry.

Źródła faktograficznego katalogu (same nazwy i identyfikatory, bez grafik):
- https://www.maprunner.info/upgrades
- https://www.maprunner.info/pl/modyfikacje

Źródła formatu:
- https://github.com/randombits-dev/snowrunner-save-editor/blob/main/src/components/Upgrades.tsx
- https://github.com/randombits-dev/snowrunner-save-editor/blob/main/src/definitions/ISaveGame.ts
- https://github.com/AlexDeww/SnowrunnerSaveMerger

Uruchomienie źródeł: `Uruchom.cmd` (Python 3.10+ z Tkinter).
Budowanie: `python -m PyInstaller --onefile --windowed --name SnowRunner-SaveSync savesync.py` (PyInstaller w środowisku).

## Edycja i synchronizacja XP

Po wczytaniu zapisu gracza panel „Doświadczenie i poziom gracza” pokazuje obecne XP i poziom oraz wynik planowanej zmiany. Tryby: Bez zmian, Synchronizuj z hostem, Dodaj XP, Ustaw XP, Ustaw poziom (1–30).

Po wczytaniu obu zapisów z prawidłowymi danymi XP domyślnie działa synchronizacja doświadczenia: bierze większą z obu wartości, bez obniżania postępu gracza. Jest niezależna od checkboxa synchronizacji ulepszeń. Do ręcznej edycji XP host nie jest potrzebny. Program zapisuje jednocześnie `experience` i odpowiadający mu `rank`; maksymalna ranga to 30, XP może rosnąć dalej. Ustawienie poziomu wybiera jego minimalne XP (np. poziom 7 = 6900 XP). Dodawanie XP jest liczone od wczytanego stanu; po zapisie tryb wraca do synchronizacji, jeśli dostępny jest host, albo do „Bez zmian”.

Wymaganie rangi (`UnlockByRank`) jest odrębne od eksploracji (`UnlockByExploration`) i zadań (`AddonUnlockByObjective`). Edycja XP nie dopisuje flag znalezionych części i nie dodaje części do ekwipunku. Do odkryć służy dotychczasowa synchronizacja lub checkboxy ulepszeń. Zmiany wymagają podglądu i są zapisywane z kopią zapasową przy wyłączonej grze. Zmiana XP i poziomu została sprawdzona przez autora w grze i działa prawidłowo (19.11.2026).

Źródła: [dokumentacja GameData firmy Saber](https://expeditions-guides-staging.saber.games/truck_modding/tags_and_attributes_of_trucks/enginevariants/engine/gamedata/), [progi XP MapRunner](https://www.maprunner.info/pl/resources/rank-xp).

## Język aplikacji dla graczy

Przy pierwszym uruchomieniu SnowRunner SaveSync używa angielskiego. W prawym górnym rogu znajduje się wybór: English, Polski, Deutsch, Français, Español i Português (wariant brazylijski dla nazw z gry). Przełącznik działa od razu, bez ponownego uruchamiania, przeładowywania zapisów ani kasowania przygotowanych zmian. Obejmuje zakładki, opcje, komunikaty, raporty, nazwy map, ulepszeń i wyposażenia. Identyfikatory techniczne, nazwy plików i nazwy modeli pozostają danymi zapisu. Wyszukiwanie obsługuje nazwy wyświetlane w wybranym języku oraz dotychczasowe polskie nazwy.

Preferencja jest przechowywana w `%APPDATA%\SnowRunnerSaveSync\settings.json`; brak lub uszkodzenie pliku powoduje użycie angielskiego. Same pliki gry nie są zmieniane przez wybór języka. Systemowe przyciski okien wyboru pliku i standardowych komunikatów mogą pozostać w języku Windows. HostPacker obsługuje te same języki i współdzieli tę preferencję z SaveSync.

Tłumaczenia są dołączone do programu i działają offline. `translations.py` zawiera teksty interfejsu; `catalog_languages.py` — nazwy dla istniejącego katalogu. Opcjonalny `build_catalog_languages.py` aktualizuje ten podzbiór z lokalnego `initial.pak`; użytkownik gotowego EXE nie potrzebuje tego pliku gry.
