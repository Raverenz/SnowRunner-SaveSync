# Pierwsza publikacja — instrukcja dla autora

## Co jest przygotowane

Kod, MIT dla własnego kodu, angielski README, polska instrukcja, dokument pochodzenia danych, testy, przypięte zależności,
automatyczne budowanie paczek i workflow GitHuba tworzący szkic wydania `v1.0`.
Zmianę XP/rangi autor potwierdził w grze 19.11.2026. To pierwsze publiczne wydanie 1.0.

## Katalogi danych

Autor zdecydował o dołączeniu obecnych katalogów i tłumaczeń do darmowej aplikacji. Informacje o źródłach i statusie praw
pozostają w `THIRD_PARTY_NOTICES.md`. MIT obejmuje nasz kod; nie oznacza uzyskania zgody właścicieli danych.

## Repozytorium

1. Na GitHubie wybierz **New repository**, nazwa `SnowRunner-SaveSync`. Ustaw widoczność **Public**.
   Nie inicjuj README/licencji ani .gitignore na stronie — mamy własne pliki.
2. Prześlij link do pustego repozytorium. Następnie można podłączyć lokalny projekt, przejrzeć listę plików pierwszego commita i wysłać kod.
   Nie przesyłaj folderu przez „Upload files” razem z `dist`, `build`, środowiskiem Pythona lub zapisami.
3. Po wysłaniu kodu sprawdź zielony wynik **CI** w zakładce Actions. Nie wymaga klucza API ani tokena zapisanego w plikach.
4. Włącz zgłaszanie podatności prywatnie (Settings → Security / Code security, zależnie od aktualnego interfejsu).

## Szkic wydania

1. Po przeglądzie kodu i danych utwórz tag `v1.0` na wybranym commicie.
2. Actions → **Release** → Run workflow → wybierz ten tag jako ref.
3. Workflow testuje i buduje obie aplikacje, sumy SHA-256, kod źródłowy i poświadczenia pochodzenia.
4. Otwórz utworzony **draft release**, sprawdź logi, listę plików, sumy i poświadczenie, rozpakuj obie aplikacje i sprawdź start.
5. Opublikuj szkic ręcznie dopiero po akceptacji zestawu. Wydanie 1.0 nie jest oznaczone jako prerelease.

Paczki lokalne w `release/` są podglądem do kontroli. Nie mają poświadczeń GitHuba i nie zastępują pierwszego udanego buildu w Actions.
Nic nie zostało jeszcze wysłane ani opublikowane na GitHubie.
