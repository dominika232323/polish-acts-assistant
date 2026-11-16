# Raport Ewaluacji RAG — Polish Acts Assistant

## 1. Konfiguracja Eksperymentu
- **Data uruchomienia:** `2026-11-16 16:20:22`
- **Liczba pytań (`golden.jsonl`):** `20`
- **Parametry generacji:** `temperature = 0` (wymuszone dla powtarzalności)
- **Model embeddingów do metryki semantycznej:** `qwen3-embedding:0.6b`

## 2. Średnie wyniki zbiorcze
| Metryka | Wynik | Opis |
| :--- | :---: | :--- |
| **Human Accuracy (Ocena ręczna)** | **89.5%** (17/19) | Ostateczna poprawność merytoryczna / poprawna odmowa |
| **Citation / Refusal Recall** | **60.0%** | Trafność cytowanych ustaw i artykułów (lub poprawna odmowa dla `oos`) |
| **Embedding Cosine Similarity** | **0.793** | Podobieństwo semantyczne odpowiedzi do `expected_answer` |
| **ROUGE-L (F1)** | **0.280** | Leksykalne pokrywanie się słów z odpowiedzią wzorcową |
| **Średni czas odpowiedzi** | **23.93 s** | Średni czas generacji odpowiedzi na pytanie |

## 3. Wyniki w podziale na trudność (`type`)
| Typ pytania | Liczba | Cit./Refusal Recall | Emb. Sim | ROUGE-L | Czas (s) | Human Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `easy` | 11 | 81.8% | 0.868 | 0.268 | 24.12s | 9/10 |
| `multi` | 6 | 50.0% | 0.773 | 0.273 | 26.54s | 5/6 |
| `oos` | 3 | 0.0% | 0.557 | 0.340 | 18.02s | 3/3 |

## 4. Tabela przeglądowa wyników i miejsce na ocenę ręczną
> **Instrukcja oceny ręcznej:** Uruchom `make eval-grade` w terminalu, aby ocenić każde pytanie interaktywnie (`1` = poprawna / poprawna odmowa, `0` = błędna / halucynacja), albo uzupełnij kolumnę **Ocena Human** ręcznie.

| ID | Typ | Cit. Recall | Emb. Sim | ROUGE-L | Czas | Ocena Human (0/1) | Notatka |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `easy-01` | `easy` | 1.00 | 0.780 | 0.119 | 55.6s | **1** |  |
| `easy-02` | `easy` | 1.00 | 0.889 | 0.286 | 18.6s | **1** |  |
| `easy-03` | `easy` | 1.00 | 0.800 | 0.111 | 18.4s | **1** | brak domknięcia cudzysłowu w odpowiedzi |
| `easy-04` | `easy` | 1.00 | 0.870 | 0.209 | 23.3s | **1** | niepotrzebnie dodane zwana dalej "Agencją, niedokmnięcie cudzysłowu |
| `easy-05` | `easy` | 1.00 | 0.840 | 0.000 | 18.1s | **1** |  |
| `easy-06` | `easy` | 1.00 | 0.861 | 0.286 | 21.8s | **1** | poprawna odpowiedź, ale dodano niepotrzebny szczegół |
| `easy-07` | `easy` | 0.00 | 0.906 | 0.367 | 20.1s | **1** |  |
| `easy-08` | `easy` | 1.00 | 0.809 | 0.311 | 26.6s | **0** | agent nie wyminienił organów z nazwy tylko wskazał miejsce w ustawie gdzie są wymienione |
| `easy-09` | `easy` | 1.00 | 0.945 | 0.538 | 20.1s | `[ ]` |  |
| `easy-10` | `easy` | 1.00 | 0.915 | 0.517 | 21.7s | **1** |  |
| `easy-11` | `easy` | 0.00 | 0.936 | 0.203 | 21.0s | **1** |  |
| `multi-1act-01` | `multi` | 1.00 | 0.786 | 0.400 | 26.2s | **1** |  |
| `multi-1act-02` | `multi` | 0.00 | 0.881 | 0.472 | 38.0s | **1** |  |
| `multi-1act-03` | `multi` | 1.00 | 0.862 | 0.319 | 23.6s | **1** |  |
| `multi-src-01` | `multi` | 0.00 | 0.372 | 0.000 | 19.2s | **1** |  |
| `multi-src-02` | `multi` | 0.50 | 0.864 | 0.255 | 28.1s | **1** |  |
| `multi-src-03` | `multi` | 0.50 | 0.873 | 0.191 | 24.1s | **0** | pierwsza część odpowiedzi dobra poza błędem językowym, model nie znalazł informacji z innego pliku potrzebnych do odpowiedzi na drugą częś,ć pytania |
| `oos-01` | `oos` | 0.00 | 0.610 | 0.467 | 17.7s | **1** |  |
| `oos-02` | `oos` | 0.00 | 0.499 | 0.250 | 17.8s | **1** |  |
| `oos-03` | `oos` | 0.00 | 0.564 | 0.304 | 18.5s | **1** |  |

---

## 5. Szczegółowe porównanie odpowiedzi (Golden vs Agent)

### `easy-01` (`easy`) — Cit. Recall: `1.00` | Emb. Sim: `0.780` | Czas: `55.6s`
- **Pytanie:** Ile Komisja ma czasu na wydanie opinii w sprawie naszego systemu AI?
- **Oczekiwane źródła:** `DU/2026/1003 art. 12 ust. 1`
- **Oczekiwana odpowiedź (Golden):** Komisja wydaje i doręcza opinię indywidualną niezwłocznie, najpóźniej w ciągu 30 dni od złożenia wniosku, a w sprawach szczególnie skomplikowanych – najpóźniej w ciągu 60 dni.
- **Odpowiedź agenta:**
> Czas na wydanie opinii zależy od rodzaju sprawy i statusu podmiotu:
> 
> 1. W sprawach ogólnych (art. 12 ust. 1): termin wynosi **30 dni** od złożenia wniosku; w przypadkach szczególnie skomplikowanych – **60 dni** [1].
> 2. Dla podmiotów uczestniczących w piaskownicy regulacyjnej (art. 101 ust. 1 i 2): termin wynosi **14 dni** od złożenia wniosku o wydanie opinii, jeśli wniosek spełnia wymogi prawne [2].
> 3. Jeśli wniosek nie spełnia wymogów formalnych (np. brak uzupełnienia w terminie 7 dni), Komisja pozostawia go bez rozpoznania [2].
> 4. W przypadku niezachowania terminu między nowymi wnioskami (art. 9 ust. 5): nowy wniosek pozostawia się bez rozpoznania, jeśli złożony został wcześniej niż **30 dni** po ostatnim wniosku [3].
> 
> Warto również pamiętać, że niewydanie opinii w ustalonym terminie uznaje się za wydanie opinii zgodnej ze stanowiskiem podmiotu [1].
> 
> Źródła:
>   [1] art. 12 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)
>   [2] art. 101 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)
>   [3] art. 9 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)
> 
> (retrieval 5.8s, generation 42.8s)

### `easy-02` (`easy`) — Cit. Recall: `1.00` | Emb. Sim: `0.889` | Czas: `18.6s`
- **Pytanie:** Kiedy obchodzimy w Polsce Dzień Inwalidy Wojennego?
- **Oczekiwane źródła:** `DU/2026/179 art. 1 ust. 1`
- **Oczekiwana odpowiedź (Golden):** Dzień Inwalidy Wojennego obchodzony jest 12 kwietnia
- **Odpowiedź agenta:**
> Dzień Inwalidy Wojennego obchodzimy 12 kwietnia [1].
> 
> Źródła:
>   [1] art. 1 ustawy o ustanowieniu Dnia Inwalidy Wojennego (Dz.U. 2026 poz. 179)
> 
> (retrieval 1.22s, generation 10.62s)

### `easy-03` (`easy`) — Cit. Recall: `1.00` | Emb. Sim: `0.800` | Czas: `18.4s`
- **Pytanie:** Czy mogę używać tytułu zawodowego 'psycholog' po samych studiach, jeśli nie mam prawa wykonywania zawodu?
- **Oczekiwane źródła:** `DU/2026/187 art. 3 ust. 2, DU/2026/187 art. 3 ust. 3`
- **Oczekiwana odpowiedź (Golden):** Nie. Tytuł zawodowy 'psycholog' podlega ochronie prawnej i może się nim posługiwać wyłącznie osoba, która posiada prawo wykonywania zawodu psychologa.
- **Odpowiedź agenta:**
> Nie, zgodnie z ustawą nie można posługiwać się tytułem zawodowym „psycholog
> 
> Źródła:
>   [1] art. 3 ustawy o zawodzie psychologa oraz samorządzie zawodowym psychologów (Dz.U. 2026 poz. 187)
> 
> (retrieval 1.21s, generation 10.62s)

### `easy-04` (`easy`) — Cit. Recall: `1.00` | Emb. Sim: `0.870` | Czas: `23.3s`
- **Pytanie:** Jaki organ prowadzi Krajowy Rejestr Oznakowanych Psów i Kotów?
- **Oczekiwane źródła:** `DU/2026/755 art. 2 ust. 1`
- **Oczekiwana odpowiedź (Golden):** Krajowy Rejestr Oznakowanych Psów i Kotów prowadzi Agencja Restrukturyzacji i Modernizacji Rolnictwa.
- **Odpowiedź agenta:**
> Krajowy Rejestr Oznakowanych Psów i Kotów (KROPiK) prowadzi Agencja Restrukturyzacji i Modernizacji Rolnictwa, zwana dalej „Agencją
> 
> Źródła:
>   [1] art. 1 ustawy o Krajowym Rejestrze Oznakowanych Psów i Kotów (Dz.U. 2026 poz. 755)
>   [2] art. 3 ustawy o Krajowym Rejestrze Oznakowanych Psów i Kotów (Dz.U. 2026 poz. 755)
>   [3] art. 17 ustawy o Krajowym Rejestrze Oznakowanych Psów i Kotów (Dz.U. 2026 poz. 755)
>   [4] art. 2 ustawy o Krajowym Rejestrze Oznakowanych Psów i Kotów (Dz.U. 2026 poz. 755)
>   [5] art. 7 ustawy o Krajowym Rejestrze Oznakowanych Psów i Kotów (Dz.U. 2026 poz. 755)
> 
> (retrieval 1.18s, generation 15.67s)

### `easy-05` (`easy`) — Cit. Recall: `1.00` | Emb. Sim: `0.840` | Czas: `18.1s`
- **Pytanie:** Gdzie znajduje się siedziba Wojskowej Akademii Medycznej?
- **Oczekiwane źródła:** `DU/2026/821 art. 1 ust. 2`
- **Oczekiwana odpowiedź (Golden):** Wojskowa Akademia Medyczna ma siedzibę w Łodzi.
- **Odpowiedź agenta:**
> Siedzibą Wojskowej Akademii Medycznej jest Łódź [1].
> 
> Źródła:
>   [1] art. 1 ustawy o utworzeniu Wojskowej Akademii Medycznej (Dz.U. 2026 poz. 821)
> 
> (retrieval 1.17s, generation 10.39s)

### `easy-06` (`easy`) — Cit. Recall: `1.00` | Emb. Sim: `0.861` | Czas: `21.8s`
- **Pytanie:** Na bazie jakiej uczelni powstaje Uniwersytet Mazowiecki w Płocku?
- **Oczekiwane źródła:** `DU/2026/1308 art. 1 ust. 1`
- **Oczekiwana odpowiedź (Golden):** Uniwersytet Mazowiecki w Płocku tworzy się z dotychczasowej Akademii Mazowieckiej w Płocku.
- **Odpowiedź agenta:**
> Uniwersytet Mazowiecki w Płocku powstaje na podstawie Akademii Mazowieckiej w Płocku, która z dniem 15 października 2026 r. nadaje się tę nazwę [1].
> 
> Źródła:
>   [1] art. 1 ustawy o Uniwersytecie Mazowieckim w Płocku (Dz.U. 2026 poz. 1308)
> 
> (retrieval 1.18s, generation 14.0s)

### `easy-07` (`easy`) — Cit. Recall: `0.00` | Emb. Sim: `0.906` | Czas: `20.1s`
- **Pytanie:** Jakie miasta wchodzą w skład związku metropolitalnego utworzonego w województwie pomorskim?
- **Oczekiwane źródła:** `DU/2026/912 art. 2 ust. 5`
- **Oczekiwana odpowiedź (Golden):** W skład związku metropolitalnego utworzonego w województwie pomorskim wchodzą Gdańsk, Gdynia i Sopot.
- **Odpowiedź agenta:**
> W skład związku metropolitalnego wchodzą miasta na prawach powiatu: Gdańsk, Gdynia i Sopot [1].
> 
> Źródła:
>   [1] art. 1 ustawy o związku metropolitalnym w województwie pomorskim (Dz.U. 2026 poz. 912)
> 
> (retrieval 1.18s, generation 12.28s)

### `easy-08` (`easy`) — Cit. Recall: `1.00` | Emb. Sim: `0.809` | Czas: `26.6s`
- **Pytanie:** Jakie organy mogą wnioskować o porównanie danych biometrycznych lub alfanumerycznych z danymi Eurodac?
- **Oczekiwane źródła:** `DU/2026/760 art. 5 ust. 1`
- **Oczekiwana odpowiedź (Golden):** Organami którym przysługuje uprawnienie do występowania z wnioskiem o porównanie danych biometrycznych lub alfanumerycznych z danymi Eurodac są Policja, Straż Graniczna, Centralne Biuro Antykorupcyjne, Agencja Bezpieczeństwa Wewnętrznego, Agencja Wywiadu, Żandarmeria Wojskowa, Służba Ochrony Państwa, Krajowa Administracja Skarbowa i Służba Kontrwywiadu Wojskowego.
- **Odpowiedź agenta:**
> Uprawnienie do występowania z wnioskiem o porównanie danych biometrycznych lub alfanumerycznych z danymi Eurodac na potrzeby ochrony porządku publicznego przysługuje organom, o których mowa w art. 5 ust. 1 pkt 1–3 i 5–8 rozporządzenia 2024/1358 [3].
> 
> Źródła:
>   [3] art. 5 ustawy o udziale Rzeczypospolitej Polskiej w systemie Eurodac (Dz.U. 2026 poz. 760)
> 
> (retrieval 1.26s, generation 18.92s)

### `easy-09` (`easy`) — Cit. Recall: `1.00` | Emb. Sim: `0.945` | Czas: `20.1s`
- **Pytanie:** Ile wynosi najwyższa możliwa kara za naruszenia warunków świadczenia usług pośrednictwa danych?
- **Oczekiwane źródła:** `DU/2026/548 art. 29 ust. 1`
- **Oczekiwana odpowiedź (Golden):** Najwyższa kara pieniężna za naruszenia warunków świadczenia usług pośrednictwa danych wynosi 2 000 000 zł.
- **Odpowiedź agenta:**
> Najwyższa możliwa kara pieniężna za naruszenie warunków świadczenia usług pośrednictwa danych wynosi do 2 000 000 zł [2].
> 
> Źródła:
>   [2] art. 29 ustawy o zarządzaniu danymi (Dz.U. 2026 poz. 548)
> 
> (retrieval 1.19s, generation 12.47s)

### `easy-10` (`easy`) — Cit. Recall: `1.00` | Emb. Sim: `0.915` | Czas: `21.7s`
- **Pytanie:** Który organ jest właściwym w sprawach działalności kosmicznej wykonywanej przez jednostki podległe Ministrowi Obrony Narodowej?
- **Oczekiwane źródła:** `DU/2026/465 art. 7 ust. 1`
- **Oczekiwana odpowiedź (Golden):** Organem właściwym w sprawach działalności kosmicznej wykonywanej przez jednostki podległe Ministrowi Obrony Narodowej jest Minister Obrony Narodowej.
- **Odpowiedź agenta:**
> W sprawach działalności kosmicznej wykonywanej przez jednostki podległe Ministrowi Obrony Narodowej lub przez niego nadzorowane, organem właściwym jest Minister Obrony Narodowej [1].
> 
> Źródła:
>   [1] art. 7 ustawy o działalności kosmicznej (Dz.U. 2026 poz. 465)
> 
> (retrieval 1.2s, generation 13.99s)

### `easy-11` (`easy`) — Cit. Recall: `0.00` | Emb. Sim: `0.936` | Czas: `21.0s`
- **Pytanie:** Kto i na ile czasu przed rozpoczęciem Światowego Jamboree Skautowego opracowuje plan zabezpieczenia medycznego tego wydarzenia?
- **Oczekiwane źródła:** `DU/2026/1343 art. 4 ust. 1`
- **Oczekiwana odpowiedź (Golden):** Wojewoda pomorski opracowuje plan zabezpieczenia medycznego Światowego Jamboree Skautowego na niepóźniej niż 60 dni przed rozpoczęciem się wydarzenia.
- **Odpowiedź agenta:**
> Plan zabezpieczenia medycznego opracowuje Wojewoda Pomorski nie później niż na 60 dni przed dniem rozpoczęcia Światowego Jamboree Skautowego [1].
> 
> Źródła:
>   [1] art. 4 ustawy o szczególnych rozwiązaniach związanych z organizacją XXVI Światowego Jamboree Skautowego w Rzeczypospolitej Polskiej w 2027 r. (Dz.U. 2026 poz. 1343)
> 
> (retrieval 1.18s, generation 13.35s)

### `multi-1act-01` (`multi`) — Cit. Recall: `1.00` | Emb. Sim: `0.786` | Czas: `26.2s`
- **Pytanie:** Firma zapłaciła za wniosek o opinię, a Komisja nie odpowiedziała w terminie. Co dalej z opinią i z opłatą?
- **Oczekiwane źródła:** `DU/2026/1003 art. 12 ust. 3, DU/2026/1003 art. 11 ust. 4, DU/2026/1003 art. 11 ust. 5`
- **Oczekiwana odpowiedź (Golden):** Niewydanie opinii w terminie oznacza, że uznaje się ją za wydaną zgodnie ze stanowiskiem przedstawionym we wniosku. Opłata podlega wtedy zwrotowi w całości, w terminie 30 dni od upływu terminu na wydanie opinii.
- **Odpowiedź agenta:**
> Jeśli Komisja nie wyda opinii w ustalonym terminie, uznaje się to za wydanie opinii zgodnej ze stanowiskiem podmiotowym [2]. Opłata zapłacona przez firmę podlega całkowitemu zwrotowi w tym przypadku [1]. Zwrot następuje w terminie 30 dni od dnia upływu terminu na wydanie opinii [1].
> 
> Źródła:
>   [1] art. 11 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)
>   [2] art. 12 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)
> 
> (retrieval 1.25s, generation 18.29s)

### `multi-1act-02` (`multi`) — Cit. Recall: `0.00` | Emb. Sim: `0.881` | Czas: `38.0s`
- **Pytanie:** Uczelnia otrzymała w drugiej ewaluacji kategorię naukową B w danej dyscyplinie. Co dzieje się z już rozpoczętymi przewodami doktorskimi i czy można wszczynać nowe?
- **Oczekiwane źródła:** `DU/2026/971 art. 2 ust. 1, DU/2026/971 art. 2 ust. 3`
- **Oczekiwana odpowiedź (Golden):** Postępowania w sprawie nadania stopnia doktora wszczęte przed dniem przyznania kategorii B mogą być kontynuowane przez uczelnię, ale nie dłużej niż do dnia uzyskania kategorii naukowej w wyniku trzeciej ewaluacji. Nowych postępowań w sprawie nadania stopnia doktora w tej dyscyplinie nie wszczyna się.
- **Odpowiedź agenta:**
> W przypadku uczelni, która otrzymała w drugiej ewaluacji kategorię naukową B w danej dyscyplinie, postępowania w sprawie nadania stopnia doktora (przewody doktorskie) wszczęte przed dniem przyznania tej kategorii mogą być kontynuowane przez ten podmiot, jednak nie dłużej niż do dnia uzyskania przez niego kategorii naukowej w wyniku trzeciej ewaluacji [3]. W tym samym czasie, w podmiocie, który otrzymał kategorię B, nie wszczyna się nowych postępowań w sprawie nadania stopnia doktora [3].
> 
> Źródła:
>   [3] art. 2 ustawy o szczególnych rozwiązaniach związanych z wynikami ewaluacji jakości działalności naukowej za lata 2022-2025 (Dz.U. 2026 poz. 971)
> 
> (retrieval 1.27s, generation 30.06s)

### `multi-1act-03` (`multi`) — Cit. Recall: `1.00` | Emb. Sim: `0.862` | Czas: `23.6s`
- **Pytanie:** Czy oprócz samych zaległych składek sprzed 1999 r. ZUS umarza też odsetki i koszty egzekucyjne oraz czy wydaje w tej sprawie decyzję?
- **Oczekiwane źródła:** `DU/2026/1476 art. 1 ust. 2, DU/2026/1476 art. 2 ust. 1, DU/2026/1476 art. 2 ust. 2`
- **Oczekiwana odpowiedź (Golden):** Tak, oprócz samych składek z mocy prawa umarza się także odsetki za zwłokę, dodatkowe opłaty, opłaty prolongacyjne, koszty upomnienia oraz koszty egzekucyjne. W sprawie umorzenia ZUS nie wydaje decyzji.
- **Odpowiedź agenta:**
> Tak, oprócz samych zaległych składek umarzają się również odsetki za zwłokę, dodatkowe opłaty, opłaty prolongacyjne, koszty upomnienia oraz koszty egzekucyjne [5]. W przypadku takiego umorzenia nie wydaje się decyzji [4].
> 
> Źródła:
>   [3] art. 4 ustawy o umorzeniu należności dochodzonych przez Zakład Ubezpieczeń Społecznych powstałych przed dniem 1 stycznia 1999 r. (Dz.U. 2026 poz. 1476)
>   [4] art. 2 ustawy o umorzeniu należności dochodzonych przez Zakład Ubezpieczeń Społecznych powstałych przed dniem 1 stycznia 1999 r. (Dz.U. 2026 poz. 1476)
>   [5] art. 1 ustawy o umorzeniu należności dochodzonych przez Zakład Ubezpieczeń Społecznych powstałych przed dniem 1 stycznia 1999 r. (Dz.U. 2026 poz. 1476)
> 
> (retrieval 1.17s, generation 15.92s)

### `multi-src-01` (`multi`) — Cit. Recall: `0.00` | Emb. Sim: `0.372` | Czas: `19.2s`
- **Pytanie:** Czym różni się przedmiot koordynacji oraz organ właściwy w ustawie o wojewódzkich zespołach koordynacji od regulacji zawartych w ustawie o osobach starszych i koordynacji opieki?
- **Oczekiwane źródła:** `DU/2026/451 art. 2 ust. 1, DU/2026/451 art. 2 ust. 2, DU/2026/986 art. 3, DU/2026/986 art. 5 ust. 1, DU/2026/986 art. 5 ust. 2`
- **Oczekiwana odpowiedź (Golden):** Ustawa o wojewódzkich zespołach koordynacji (poz. 451) dotyczy polityki umiejętności (rozwoju umiejętności dzieci, młodzieży i dorosłych), a wojewódzki zespół koordynacji jest organem opiniodawczo-doradczym zarządu województwa. Ustawa o osobach starszych (poz. 986) reguluje koordynację opieki długoterminowej (usług zdrowotnych, pomocy społecznej i zabezpieczenia społecznego realizowanych w środowisku zamieszkania), a organem do spraw polityki senioralnej jest minister właściwy do spraw zabezpieczenia społecznego albo Pełnomocnik Rządu do spraw Polityki Senioralnej.
- **Odpowiedź agenta:**
> Wybrane ustawy z 2026 r. nie zawierają odpowiedzi na to pytanie.
> 
> (retrieval 1.17s, generation 11.47s)

### `multi-src-02` (`multi`) — Cit. Recall: `0.50` | Emb. Sim: `0.864` | Czas: `28.1s`
- **Pytanie:** Kto pełni funkcję pojedynczego punktu informacyjnego w ustawie o zarządzaniu danymi, a kto pełni funkcję pojedynczego punktu kontaktowego w ustawie o systemach sztucznej inteligencji?
- **Oczekiwane źródła:** `DU/2026/548 art. 3, DU/2026/1003 art. 5 ust. 1, DU/2026/1003 art. 5 ust. 2`
- **Oczekiwana odpowiedź (Golden):** W ustawie o zarządzaniu danymi (poz. 548) pojedynczy punkt informacyjny prowadzi minister właściwy do spraw informatyzacji w portalu danych. W ustawie o systemach sztucznej inteligencji (poz. 1003) jako pojedynczy punkt kontaktowy oraz organ nadzoru rynku działa Komisja Rozwoju i Bezpieczeństwa Sztucznej Inteligencji.
- **Odpowiedź agenta:**
> W ustawie o zarządzaniu danymi funkcję pojedynczego punktu informacyjnego pełni Minister właściwy do spraw informatyzacji [1]. W ustawie o systemach sztucznej inteligencji nie jest określona żadna osoba pełniąca funkcję pojedynczego punktu kontaktowego; fragmenty ustawy nie zawierają informacji na ten temat [2], [3], [4], [5].
> 
> Źródła:
>   [1] art. 3 ustawy o zarządzaniu danymi (Dz.U. 2026 poz. 548)
>   [2] art. 123 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)
>   [3] art. 40 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)
>   [4] art. 39 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)
>   [5] art. 43 ustawy o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003)
> 
> (retrieval 1.24s, generation 20.16s)

### `multi-src-03` (`multi`) — Cit. Recall: `0.50` | Emb. Sim: `0.873` | Czas: `24.1s`
- **Pytanie:** Kto może oszczędzać lub inwestować za pośrednictwem osobistego konta inwestycyjnego (OKI), a jakie podmioty są podatnikami podatku od nadzwyczajnych zysków?
- **Oczekiwane źródła:** `DU/2026/1098 art. 3 ust. 1, DU/2026/1098 art. 3 ust. 2, DU/2026/1287 art. 5`
- **Oczekiwana odpowiedź (Golden):** Umowę o prowadzenie osobistego konta inwestycyjnego (OKI) może zawrzeć wyłącznie osoba fizyczna, która ukończyła 18 lat (na jednym OKI aktywa może gromadzić tylko jeden inwestujący). Podatnikiem podatku od nadzwyczajnych zysków jest natomiast podmiot prowadzący na terytorium RP działalność w zakresie wytwarzania paliw ciekłych lub obrotu paliwami ciekłymi na podstawie koncesji na obrót paliwami ciekłymi z zagranicą.
- **Odpowiedź agenta:**
> Zgodnie z fragmentami ustaw, do prowadzenia OKI uprawniona jest wyłącznie osoba fizyczna ukończona 18 lat [5]. Inwestujący może posiadać więcej niż jedną umowę o prowadzenie OKI [5]. Fragmenty nie zawierają informacji o podmiotach będących podatnikami podatku od nadzwyczajnych zysków.
> 
> Źródła:
>   [5] art. 3 ustawy o osobistych kontach inwestycyjnych (Dz.U. 2026 poz. 1098)
> 
> (retrieval 1.3s, generation 16.34s)

### `oos-01` (`oos`) — Cit. Recall: `0.00` | Emb. Sim: `0.610` | Czas: `17.7s`
- **Pytanie:** Ile dni urlopu przysługuje pracownikowi po 10 latach pracy?
- **Oczekiwane źródła:** `BRAK (OOS)`
- **Oczekiwana odpowiedź (Golden):** Odmowa – wybrane ustawy z 2026 r. nie regulują wymiaru urlopu (to Kodeks pracy).
- **Odpowiedź agenta:**
> Wybrane ustawy z 2026 r. nie zawierają odpowiedzi na to pytanie.
> 
> (retrieval 1.18s, generation 10.04s)

### `oos-02` (`oos`) — Cit. Recall: `0.00` | Emb. Sim: `0.499` | Czas: `17.8s`
- **Pytanie:** Ile wynosi obecnie pierwszy próg podatkowy oraz kwota wolna od podatku dochodowego od osób fizycznych (PIT)?
- **Oczekiwane źródła:** `BRAK (OOS)`
- **Oczekiwana odpowiedź (Golden):** Odmowa – dostępne akty prawne z 2026 r. nie zawierają ustawy o podatku dochodowym od osób fizycznych (PIT) ani nie określają progów podatkowych PIT.
- **Odpowiedź agenta:**
> Wybrane ustawy z 2026 r. nie zawierają odpowiedzi na to pytanie.
> 
> (retrieval 1.2s, generation 10.21s)

### `oos-03` (`oos`) — Cit. Recall: `0.00` | Emb. Sim: `0.564` | Czas: `18.5s`
- **Pytanie:** Ile godzin na dobę pies może przebywać na uwięzi i jaka jest jej minimalna dopuszczalna długość?
- **Oczekiwane źródła:** `BRAK (OOS)`
- **Oczekiwana odpowiedź (Golden):** Odmowa – dostępne ustawy z 2026 r. (w tym ustawa o Krajowym Rejestrze Oznakowanych Psów i Kotów) nie regulują warunków trzymania psów na uwięzi (to materia ustawy o ochronie zwierząt).
- **Odpowiedź agenta:**
> Wybrane ustawy z 2026 r. nie zawierają odpowiedzi na to pytanie.
> 
> (retrieval 1.16s, generation 10.97s)
