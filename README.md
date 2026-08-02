# Garden Irrigation

*[English version: README.en.md](README.en.md)*

Własna integracja Home Assistant do inteligentnego, wieloczujnikowego nawadniania ogrodu.
Zamiast harmonogramu czasowego, integracja prowadzi dla każdej strefy osobny **bilans wodny
gleby**: liczy, ile wody roślina traci przez parowanie i transpirację (na podstawie realnych
danych z Twojej stacji pogody), odejmuje faktycznie zmierzony opad, i sama decyduje, kiedy i
jak długo podlewać - z uwzględnieniem gleby, wybranych roślin, prognozy opadu oraz opadu
padającego w trakcie samego podlewania.

## Co robi integracja

- Liczy dobowe **ET0** (ewapotranspirację referencyjną) metodą FAO-56 Penman-Monteith na
  podstawie temperatury, nasłonecznienia, wiatru i wilgotności z Twojej stacji pogody. Gdy
  brakuje pełnych danych, automatycznie przechodzi na metodę zapasową (Hargreaves).
- Dla każdej strefy prowadzi bilans: **deficyt wody w glebie** rośnie o ETc (= ET0 × Kc
  rośliny) i maleje o zmierzony opad oraz o wodę faktycznie dostarczoną przy podlewaniu.
- Gdy deficyt przekroczy próg zależny od gleby i wybranych roślin, strefa dostaje status
  "do podlania" z konkretną rekomendacją w minutach.
- Może działać **w pełni automatycznie** (bez klikania czegokolwiek) albo **ręcznie**
  (Ty decydujesz, kiedy zatwierdzić) - do wyboru w konfiguracji.
- Zawory otwiera **sekwencyjnie, jeden po drugim**, z wyliczeniem startu wstecz od wschodu
  słońca, tak żeby ostatnia strefa skończyła podlewanie mniej więcej o wschodzie.
- Jeśli w trakcie podlewania zacznie padać - **wstrzymuje** zawór, czeka czy to tylko krótki
  opad, i albo wznawia od miejsca przerwania, albo anuluje resztę, jeśli deszcz się utrzymuje.
- Rozpoznaje zarówno encje `switch.*`, jak i `valve.*` (np. sterowniki Tuya).
- Potrafi ustawiać sprzętowy watchdog na sterowniku (licznik czasowy `number.*`), żeby zawór
  zamknął się sam, nawet gdyby Home Assistant się zawiesił.
- Pomija podlewanie przy silnym wietrze (strefy zraszaczy) i przy ryzyku przymrozku (cały
  system), respektuje minimalny odstęp między podlewaniami danej strefy (żeby korzenie uczyły
  się sięgać głębiej), i ma jeden przełącznik do globalnego wstrzymania wszystkiego (np. na
  wyjazd).
- Koryguje próg MAD co noc oficjalnym wzorem FAO-56 na podstawie wczorajszego tempa zużycia
  wody - przy upale/suszy próg jest automatycznie niższy (i minimalny odstęp między
  podlewaniami zostaje na ten dzień pominięty), przy chłodnej pogodzie wyższy.
- Liczy statystyki zużycia wody (dobowe/miesięczne, per strefa i łącznie) oraz zgłasza problemy
  sprzętowe (brakująca encja, zawór nie reaguje) przez wbudowany mechanizm HA Repairs.

## Instalacja

1. Skopiuj folder `custom_components/garden_irrigation` do `config/custom_components/` na
   swoim Home Assistant.
2. Zrestartuj Home Assistant.
3. Ustawienia → Urządzenia i usługi → Dodaj integrację → wyszukaj
   **"Ogród - Inteligentne Nawadnianie"**.
4. Przejdź przez trzy kroki kreatora: pogoda → liczba stref → szczegóły stref (opisane niżej).

Konfigurację można później zmienić w dowolnym momencie: karta integracji → **Konfiguruj**.
Otwiera się dokładnie ten sam kreator, z już wypełnionymi aktualnymi wartościami - zmieniasz
tylko to, co chcesz.

## Krok 1: stacja pogodowa i ustawienia globalne

**Wszystkie pola w tym kroku są opcjonalne** - integrację można skonfigurować z zerem
czujników pogodowych i uzupełniać je stopniowo. Bez temperatury (jedynego naprawdę
niezbędnego czujnika - nawet zapasowa metoda liczenia ET0 jej wymaga) bilans wodny nie
ruszy, ale integracja o tym poinformuje przez Ustawienia → System → Repairs, zamiast po
cichu nic nie robić.

| Pole | Znaczenie |
|---|---|
| Temperatura | Encja temperatury z Twojej stacji pogody |
| Nasłonecznienie (W/m²) | Do liczenia ET0 metodą Penman-Monteith |
| Prędkość wiatru (m/s) | Do liczenia ET0. **Automatycznie przelicza jednostkę** (km/h, mph, węzły) na m/s na podstawie `unit_of_measurement` czujnika - większość stacji pogodowych (Ecowitt/WS) podaje wiatr w km/h, nie trzeba nic samodzielnie przeliczać |
| Wilgotność powietrza (%) | Do liczenia ET0 |
| Opad - licznik narastający / total rain (mm) | **Musi to być licznik, który nigdy się nie zeruje** (rośnie bez końca) - NIE typowy "opad dzienny", który resetuje się o północy. Integracja sprawdza go co cykl aktualizacji i liczy różnicę względem poprzedniego odczytu, żeby na bieżąco (nie raz na dobę) redukować deficyt wody. Jeśli Twoja stacja ma tylko wariant dobowy, można w HA dodać helper `utility_meter` bez cyklu resetu, żeby uzyskać wersję narastającą |
| Encja usługi pogodowej (`weather.*`) | Opcjonalnie - integracja sama pobiera prognozę opadu przez usługę `weather.get_forecasts`, bez potrzeby budowania własnego szablonu |
| Ile najbliższych godzin prognozy sumować | Horyzont czasowy sumowania prognozowanego opadu (domyślnie 6h) |
| Jak rzadko odpytywać usługę pogodową | Osobny, niezależny interwał odpytywania prognozy (domyślnie 60 min) - prognoza nie musi być świeższa, a część usług pogodowych ma limity zapytań |
| Prognoza opadu (mm) - stary sposób | Alternatywa dla powyższego: własny szablon/sensor z prognozą, używany tylko jeśli pole `weather_entity` jest puste |
| Próg opadu do CAŁKOWITEGO pominięcia podlewania (mm) | Jeśli prognoza pokazuje opad ≥ ten próg, strefa jest tego dnia całkowicie pomijana (nie tylko zmniejszana dawka) |
| Tryb ustalania startu | Patrz sekcja "Kiedy dokładnie startuje podlewanie" niżej |
| Odstęp w minutach | Używany tylko dla trybów "przed/po wschodzie" |
| Szybki detektor "czy pada teraz" | Opcjonalnie - `binary_sensor` (dedykowany czujnik deszczu) LUB zwykły `sensor` liczbowy z natężeniem opadu w mm/h (np. `sensor.ws_rain_rate`) - integracja rozpoznaje typ po domenie encji. Dla sensora liczbowego porównuje wartość z progiem "Próg intensywności opadu (mm/h)". Przyspiesza wykrycie początku opadu w trakcie podlewania (patrz sekcja o pauzie) |
| Próg opadu wywołujący pauzę W TRAKCIE podlewania (mm) | Ile mm musi spaść, żeby integracja przerwała aktywne podlewanie (domyślnie 0,3 mm) |
| Co ile minut sprawdzać opad podczas pracy/pauzy | Częstotliwość kontroli w trakcie aktywnego podlewania i w trakcie pauzy (domyślnie 2 min) |
| Maks. czas oczekiwania na ustanie opadu | Po tym czasie integracja poddaje się i anuluje resztę sekwencji (domyślnie 30 min) |
| Włącz w pełni automatyczne podlewanie | Patrz sekcja "Tryb automatyczny" niżej |
| Bufor bezpieczeństwa przy liczeniu wyzwalacza (min) | Patrz sekcja "Tryb automatyczny" |
| Częstotliwość odczytu danych pogodowych (min) | Jak często odpytywane są POZOSTAŁE czujniki (temperatura, wiatr, opad total rain itd.) - domyślnie 10 min |
| Czujnik ciśnienia atmosferycznego | Opcjonalnie - lista zawężona do encji z `device_class: pressure`. Jeśli masz realny pomiar, integracja użyje go zamiast wzoru barometrycznego liczonego z wysokości. **Wybierz ciśnienie ABSOLUTNE/stacyjne** (u stacji Ecowitt/WS zwykle `sensor.ws_absolute_pressure`), **nie "relative"** (`sensor.ws_relative_pressure` to ciśnienie przeliczone do poziomu morza - nieprawidłowe dla wzoru FAO-56). **Uwaga:** filtr klasy urządzenia NIE rozróżni absolute/relative/VPD, jeśli wszystkie trzy mają tę samą `device_class: pressure` (częsty przypadek przy szablonach) - liczy się świadomy wybór po nazwie encji, nie klasa. `sensor.*vapour_pressure_deficit` (VPD) to zupełnie inna wielkość fizyczna, nie nadaje się jako czujnik ciśnienia mimo tej samej klasy/jednostki. Rozpoznaje jednostki hPa/mbar/kPa/inHg/mmHg - przy nierozpoznanej jednostce zakłada hPa (najczęstsza w HA) |
| Przerwa między zamknięciem jednej strefy a otwarciem kolejnej (s) | Domyślnie 5s - integracja czeka tyle po potwierdzonym zamknięciu zaworu, zanim otworzy następny w kolejności |
| Ile czekać na potwierdzenie otwarcia/zamknięcia zaworu (s) | Domyślnie 15s - jak długo integracja odpytuje stan encji zaworu, zanim uzna, że polecenie się nie powiodło |
| Główny przepływomierz - suma litrów | Opcjonalnie - jeśli masz JEDEN wspólny licznik na cały system (typowe przy sekwencyjnym podlewaniu, gdzie i tak tylko jedna strefa pracuje naraz), wskaż go tutaj. Strefy bez własnego przepływomierza automatycznie z niego skorzystają |
| Główny przepływomierz - przepływ CHWILOWY | To samo, ale dla pomiaru chwilowego (np. l/min) - używane do dodatkowej weryfikacji, że zawór faktycznie się otworzył/zamknął (patrz sekcja "Sekwencyjne uruchamianie stref") |
| Próg braku przepływu | Poniżej tej wartości przepływu integracja uznaje, że wody nie ma (zawór faktycznie zamknięty) |
| Powyżej tej prędkości wiatru... | Próg wiatru (m/s), powyżej którego pomijane są strefy oznaczone jako wrażliwe na wiatr (typowo zraszacze - drift/nierówne pokrycie) |
| Poniżej tej temperatury... | Próg temperatury (°C), poniżej którego CAŁE podlewanie jest wstrzymywane (ryzyko przymrozku - węże, zawory) |

## Krok 2: lokalizacja ogrodu

Osobny, krótki krok - mapa z pinezką, domyślnie ustawioną na Twój dom (z ogólnej konfiguracji
HA). Jeśli ogród jest w innym miejscu (inna wysokość, spory kawałek dalej), przeciągnij
pinezkę. Krążek promienia jest widoczny i edytowalny (domyślnie 10 m) - to tylko wizualne
zaznaczenie na mapie, integracja i tak używa samego punktu (współrzędnych), nie promienia.
Używana do liczenia ET0 (szerokość geograficzna w metodzie zapasowej) oraz do samodzielnego
wyliczania wschodu słońca (patrz sekcja niżej). Można zostawić bez zmian - wtedy używana jest
lokalizacja domu.

## Krok 3: liczba stref

Integracja nie ma sztywnego limitu - podaj dowolną liczbę stref (1-32) odpowiadającą Twojemu
sterownikowi. W kolejnym kroku uzupełnisz tylko te, które faktycznie chcesz aktywować -
pozostałe zostaw z pustym polem zaworu.

## Krok 4: szczegóły każdej strefy

| Pole | Znaczenie |
|---|---|
| Nazwa strefy | Np. "Trawnik", "Donice" - jeśli puste, domyślnie "Strefa N" |
| Zawór / przełącznik | Encja `switch.*` lub `valve.*` sterująca tą strefą. **Puste pole = strefa nieaktywna** |
| Przepływomierz | Opcjonalnie - jeśli podłączony, realne zużycie wody jest dokładnie przeliczane na mm i odejmowane od deficytu; bez niego integracja szacuje ilość wody na podstawie czasu pracy i zadeklarowanej wydajności. **Automatycznie rozpoznaje jednostkę objętości** (m³, L, gal, ft³, CCF, MCF) na podstawie `unit_of_measurement` czujnika - liczniki wody w HA (device_class `water`) najczęściej podają m³, nie litry, więc nie trzeba nic samodzielnie przeliczać. Puste pole = strefa korzysta z **głównego przepływomierza** (jeśli skonfigurowany globalnie) |
| Przepływomierz chwilowy | Opcjonalnie - jeśli ta konkretna strefa ma własny czujnik przepływu chwilowego, różny od reszty. **Też automatycznie rozpoznaje jednostkę** (L/min, L/h, m³/h, m³/min, gal/min) i przelicza wewnętrznie na L/min. Puste pole = strefa korzysta z **głównego przepływomierza chwilowego** (jeśli skonfigurowany globalnie) |
| Typ gleby | Decyduje, ile wody gleba jest w stanie zatrzymać (patrz tabela gleb niżej) |
| Rośliny | Jedna lub więcej z listy (patrz tabela roślin niżej) - określają Kc, głębokość korzeni i próg wrażliwości na przesuszenie |
| Ręczna kalibracja Kc | Opcjonalnie - wpisana wartość liczbowa całkowicie zastępuje Kc wyliczone z wybranych roślin. Puste = użyj wyliczonego |
| Ręczna kalibracja MAD | To samo dla progu MAD |
| Głębokość korzeni z wybranej rośliny | Opcjonalnie - lista wyboru zbudowana z roślin **już zapisanych** w tej strefie (posortowana rosnąco wg Kc, z Kc widocznym w etykiecie), pozwala świadomie zastąpić automatyczne maksimum jedną konkretną rośliną - przydatne, gdy jedna głęboko korzeniąca się roślina w miksie (np. pojedyncze drzewo wśród krzewów/bylin) sztucznie zawyżałaby pojemność całej strefy dla reszty. **Lista jest pusta przy pierwszej konfiguracji strefy** (formularz nie może odczytać roślin wybieranych w tym samym kroku) - pojawi się dopiero po zapisaniu i ponownym wejściu w "Konfiguruj". Puste = automatyczne maksimum (jak dotychczas) |
| Powierzchnia (m²) | Dla zraszaczy - cała powierzchnia strefy; dla kroplówek - szacowana **zwilżana strefa wzdłuż linii** (długość × szerokość zwilżanego pasa), nie cała powierzchnia gruntu |
| Typ nawadniania | Zraszacze / Mikrozraszacze / Linia kroplująca / Pojedyncze kroplowniki - wpływa na to, jak liczona jest **domyślna, sugerowana** wartość pola "Wydajność" poniżej (patrz sekcja "Typ nawadniania" niżej) |
| Długość linii kroplującej (m) | Tylko dla typu "Linia kroplująca" - dla innych typów ignorowane (widoczne w formularzu, ale bez efektu) |
| Rozstaw kroplowników (cm) | Tylko dla "Linia kroplująca" - odległość między kroplownikami wzdłuż linii |
| Wydajność pojedynczego kroplownika (L/h) | Dla "Linia kroplująca" LUB "Pojedyncze kroplowniki" - zwykle podana na opakowaniu |
| Liczba kroplowników (szt.) | Tylko dla "Pojedyncze kroplowniki" - gdy nie masz linii, tylko pojedyncze emitery w sekcji |
| Wydajność (mm/h) | **Sugerowana automatycznie** na podstawie typu nawadniania i jego parametrów (patrz niżej) - punkt startowy, edytowalny ręcznie, **samo-korygowany później** na podstawie realnych pomiarów z przepływomierza, jeśli włączone (patrz "Ucz się z wodomierza" niżej). Jeśli nie masz przepływomierza, ta wartość zostaje na stałe. **Dopuszczalny zakres: 0,5-500 mm/h** - może się to wydawać dużo, ale małe strefy (np. donice) z niemałym przepływem potrafią legalnie osiągać 200+ mm/h - to matematyka (L/h ÷ mała powierzchnia), nie błąd |
| Ucz się wydajności z pomiaru wodomierza | Domyślnie włączone (jeśli strefa ma przepływomierz) - wyłącz, jeśli wolisz, żeby wydajność ZAWSZE pozostała dokładnie taka, jaką ręcznie wpisałeś, nawet gdy przepływomierz mówi coś innego |
| Maksymalny czas podlewania (min) | Twardy limit bezpieczeństwa - integracja nigdy nie przekroczy tej wartości, niezależnie od wyliczeń |
| Watchdog timer (`number.*`) | Opcjonalnie - jeśli sterownik ma sprzętowy licznik czasowy per strefa, integracja wpisuje tam aktualny, pozostały czas tuż przed każdym otwarciem zaworu (patrz sekcja "Watchdog sprzętowy") |
| Minimalny odstęp między podlewaniami (dni) | Domyślnie 0 (brak limitu). Nawet jeśli deficyt przekroczy próg wcześniej, strefa nie zostanie podlana częściej niż co tyle dni - to zachęca system korzeniowy do sięgania głębiej po wodę zamiast przyzwyczajania się do płytkiego, codziennego podlewania |
| Strefa wrażliwa na wiatr | Zaznacz dla zraszaczy (nie ma większego sensu dla kroplówek) - strefa będzie pomijana przy silnym wietrze (próg globalny) |

### Jak liczone jest zapotrzebowanie przy kilku roślinach w jednej strefie

Gdy w jednej strefie wybierzesz kilka roślin o różnym zapotrzebowaniu (np. iglaki + hortensje
na jednej linii kroplującej), integracja stosuje podejście **konserwatywne**:
- **Kc** i **głębokość korzeni** bierze od najbardziej wymagającej rośliny z wybranych (żeby
  żadna nie usychała) - **głębokość korzeni można świadomie zastąpić** wyborem z listy (patrz
  wyżej "Głębokość korzeni z wybranej rośliny"), jeśli jedna głęboko korzeniąca się roślina w
  niewielkiej liczbie zniekształca pojemność całej strefy dla reszty roślin,
- **próg MAD** bierze od najbardziej wrażliwej (najniższy próg = najwcześniej włącza
  podlewanie) - **ten parametr celowo NIE ma odpowiednika ręcznego wyboru z listy** (tylko
  ręczna kalibracja liczbowa wyżej, jeśli naprawdę potrzebna) - to jedyny parametr bezpośrednio
  chroniący najbardziej wrażliwą roślinę przed przesuszeniem, więc pozostawienie go w pełni
  automatycznym minimalizuje ryzyko przypadkowego wybrania zbyt tolerancyjnej wartości.

To może oznaczać lekkie przelanie najbardziej suszoodpornych roślin w strefie kosztem
pewności, że wrażliwe nie usychają. Który konkretnie parametr od której rośliny został przyjęty,
widać w sensorach diagnostycznych opisanych niżej - a jeśli po obserwacji ogrodu chcesz to
skorygować, użyj pól ręcznej kalibracji Kc/MAD zamiast zmieniać dobór roślin.

### Typy gleb

| Gleba | Dostępna woda (mm na metr głębokości) |
|---|---|
| Piasek | 80 |
| Piasek gliniasty | 120 |
| Glina piaszczysta (lekka) | 130 |
| Glina (średnia, uniwersalna) | 155 |
| Pył gliniasty (ciężka, zwięzła) | 180 |
| Ił / glina ciężka | 185 |
| Substrat donicowy / ziemia uniwersalna | 100 |

### Rośliny

| Roślina | Kc | Głębokość korzeni | MAD |
|---|---|---|---|
| Trawnik ozdobny | 0.80 | 150 mm | 0.40 |
| Warzywa liściaste | 1.00 | 300 mm | 0.50 |
| Warzywa korzeniowe | 0.90 | 350 mm | 0.50 |
| Truskawki / poziomki | 0.85 | 200 mm | 0.40 |
| Róże | 0.60 | 400 mm | 0.50 |
| Byliny ogrodowe (ogólnie) | 0.70 | 300 mm | 0.45 |
| Hortensje | 0.80 | 300 mm | 0.35 |
| Funkie / hosty | 0.70 | 250 mm | 0.40 |
| Wysokie trawy ozdobne | 0.55 | 400 mm | 0.55 |
| Krzewy liściaste ozdobne | 0.55 | 400 mm | 0.50 |
| Żywopłot liściasty formowany | 0.60 | 400 mm | 0.45 |
| Żywopłot / krzewy iglaste | 0.45 | 450 mm | 0.55 |
| Duże iglaki (jodły, sosny, świerki) | 0.40 | 600 mm | 0.60 |
| Cisy | 0.45 | 450 mm | 0.55 |
| Płożące iglaki | 0.40 | 300 mm | 0.55 |
| Drzewa liściaste dojrzałe | 0.50 | 700 mm | 0.60 |
| Drzewa owocowe | 0.65 | 600 mm | 0.50 |
| Rośliny w donicach (ogólnie) | 0.90 | 200 mm | 0.30 |

## Pomiar opadu (total rain)

Encja opadu **musi być licznikiem narastającym, nigdy się nie zerującym**. Integracja
sprawdza ją przy każdym cyklu aktualizacji (domyślnie co 10 minut) i liczy różnicę względem
poprzedniego odczytu - jeśli przybyło wody, natychmiast odejmuje ją od deficytu wszystkich
stref. Dzięki temu deszcz, który spadnie np. o 2:00, jest uwzględniony zanim integracja
zdąży odpalić podlewanie o 4:00 - nie trzeba czekać do najbliższej północy.

Dodatkowo, tuż przed każdym zatwierdzeniem/startem, integracja jeszcze raz świeżo sprawdza
ten licznik (nie polega na odczycie sprzed nawet kilku minut). Jeśli licznik się zresetuje
(np. restart stacji pogodowej), integracja wykrywa spadek wartości i po prostu zaczyna liczyć
różnicę od nowa, bez fałszywego "ujemnego opadu".

## Prognoza opadu i całkowite pominięcie podlewania

Niezależnie od pomiaru rzeczywistego opadu, integracja sprawdza też prognozę (z encji
`weather.*` albo z własnego szablonu) i porównuje ją z progiem `rain_skip_threshold_mm`.
Jeśli prognoza pokazuje więcej opadu niż ten próg, dana strefa jest tego dnia **całkowicie
pomijana** - deficyt wody zostaje zapamiętany i dogoni się następnego dnia, jeśli deszcz się
nie sprawdzi. Sprawdzenie prognozy dzieje się dwa razy: raz przy nocnym przeliczeniu, i
jeszcze raz świeżo tuż przed samym startem.

## Pauza w trakcie podlewania

Integracja pilnuje pogody nie tylko przed startem, ale **przez cały czas aktywnego
podlewania**:

- Co `rain_pause_check_interval_min` minut sprawdza, czy zaczęło padać - najpierw przez
  szybki detektor binarny (jeśli skonfigurowany), w jego braku przez różnicę total rain.
- Jeśli tak - **natychmiast zamyka zawór**.
- W trakcie pauzy integracja **sumuje cały opad, który spadł**, i porównuje go z celem tej
  strefy - **jeśli sam deszcz już pokryje zapotrzebowanie**, podlewanie zostaje uznane za
  niepotrzebne (status: `deficyt pokryty przez deszcz w trakcie pauzy`), niezależnie od tego,
  czy w danym momencie nadal pada.
- Jeśli deszcz **nie** pokrył jeszcze całego zapotrzebowania, integracja czeka na
  `rain_stop_confirmation_min` minut **nieprzerwanego** braku opadu, zanim uzna deszcz za
  zakończony (nie po pierwszym czystym sprawdzeniu - deszcz często pada falami, nie ciągle;
  bez tego zabezpieczenia zawór otwierałby się i zamykał na przemian z każdą przerwą między
  falami, niepotrzebnie zużywając mechanicznie elektrozawór).
- **Integracja nigdy nie rezygnuje z podlewania wyłącznie z powodu długiego opadu.** Jeśli
  oczekiwanie na potwierdzenie ciszy przekroczy `rain_pause_max_wait_min`, po prostu przestaje
  czekać i **wznawia mimo to** - jedynym powodem całkowitej rezygnacji jest to, że sam opad już
  pokrył zapotrzebowanie (patrz wyżej).
- **Po wznowieniu cel jest przeliczany na nowo** - pomniejszony dokładnie o tyle mm, ile spadło
  podczas TEJ konkretnej pauzy. Woda już dostarczona z wodociągu w tej sesji (przed pauzą) i tak
  liczy się bez przerwy dalej (sterowanie objętościowe śledzi to przez całą sesję, niezależnie
  od liczby pauz) - **nic nie zaczyna się od zera**, ani z powodu deszczu, ani z powodu wody
  już dolanej przed pauzą.

## Wschód słońca liczony samodzielnie

Integracja **nie korzysta z żadnej zewnętrznej encji** (np. `sensor.sun_next_rising`) do
ustalenia godziny wschodu - liczy go sama, na podstawie lokalizacji i wysokości ogrodu (patrz
sekcja o ET0 wyżej), biblioteką `astral` (ta sama, na której opiera się wbudowana integracja
Sun w Home Assistant). `astral` jest twardą zależnością wbudowanej integracji Sun, więc jest
już obecna w Twoim systemie - integracja jej nie deklaruje jako własnego wymagania (żeby HA
nie próbował jej dodatkowo doinstalowywać z PyPI przy starcie, co może się nie udać np. przy
braku dostępu do internetu w danym momencie, i wywalić całą integrację błędem "Requirements
... not found"). Jeśli mimo to `astral` byłby z jakiegoś powodu niedostępny, reszta integracji
(bilans wodny, ręczne podlewanie) nadal działa normalnie - tylko funkcje zależne od wschodu
(sekwencja, tryb automatyczny) się wyłączą, z czytelnym komunikatem w logach.

## Kiedy dokładnie startuje podlewanie

Strefy są zawsze uruchamiane **jedna po drugiej**, nigdy równolegle (przydatne przy
ograniczonym ciśnieniu wody). Kiedy dokładnie zaczyna się pierwsza strefa, ustala pole "Tryb
ustalania startu" w konfiguracji:

| Tryb | Jak liczony jest start |
|---|---|
| Zakończ ostatnią strefę o wschodzie (domyślny) | `start = wschód − suma_minut_wszystkich_stref` - tak żeby ostatnia strefa skończyła mniej więcej o wschodzie. Suma zmienia się codziennie zależnie od tego, ile stref faktycznie potrzebuje wody |
| Start dokładnie o wschodzie | `start = wschód`, niezależnie od tego, ile to potrwa |
| Start X minut PRZED wschodem | `start = wschód − X` (stały odstęp, ustawiany polem "Odstęp w minutach") |
| Start X minut PO wschodzie | `start = wschód + X` (stały odstęp) |

Jeśli wyliczony start wypadłby w przeszłości (np. suma czasów zbyt duża na tryb "zakończ o
wschodzie"), sekwencja startuje natychmiast, bez czekania.

Można to uruchomić ręcznie: przycisk "Zaplanuj sekwencję przed wschodem" albo usługa
`garden_irrigation.run_sequence_before_sunrise`.

## Tryb w pełni automatyczny

Włączony domyślnie (`auto_mode_enabled`). Integracja sama, bez żadnej zewnętrznej
automatyzacji, codziennie:

1. Liczy moment "obudzenia się" jako punkt odniesienia wybranego trybu startu (patrz wyżej)
   minus bufor bezpieczeństwa. Dla trybu "zakończ o wschodzie" punkt odniesienia to celowo
   GÓRNE oszacowanie (suma MAKSYMALNYCH czasów wszystkich stref) - dokładny start jest i tak
   przeliczany precyzyjnie w kroku 2.
2. O tym momencie świeżo przelicza bilans wodny, sprawdza opad, prognozę, wiatr i przymrozek.
3. Uruchamia sekwencję z dokładnym, wyliczonym z aktualnych danych momentem startu.

Wyzwalacz jest automatycznie przeliczany co noc przy nocnym przeliczeniu dnia (nie trzeba
niczego nasłuchiwać zewnętrznie - integracja liczy jutrzejszy wschód sama). Żeby wyłączyć tryb
automatyczny i wrócić do ręcznego zatwierdzania - odznacz `auto_mode_enabled` w konfiguracji,
albo włącz przełącznik globalnej pauzy (patrz niżej). Przyciski i usługi ręcznego zatwierdzania
działają zawsze, niezależnie od tych ustawień.

**Nadrabianie po restarcie HA w oknie wyzwalacza.** Wewnętrzny timer integracji (mechanizm
`async_track_point_in_time`) **nie przetrwa restartu HA** - to normalne, żaden zaplanowany
timer w pamięci procesu nie przetrwa. Jeśli restart nastąpi dokładnie w wąskim oknie między
wyliczonym momentem "obudzenia się" a faktycznym wschodem słońca, integracja **wykrywa** to przy
starcie (zaplanowany czas już minął, ale dzisiejsza sekwencja jeszcze się nie odbyła i wschód
jeszcze nie nadszedł) i uruchamia sekwencję **od razu, z kilkusekundowym opóźnieniem**, zamiast
po cichu czekać do jutra i tracić całodniowe podlewanie. Jeśli natomiast wschód już minął, albo
sekwencja już dziś ruszyła - nic więcej się nie dzieje, czeka na kolejny wschód, jak zwykle.

**Druga warstwa bezpieczeństwa - cykliczny bezpiecznik.** Powyższe chroni tylko przed
restartem w newralgicznym oknie - ale co, jeśli zaplanowany timer z jakiegokolwiek INNEGO
powodu nie wystrzeli (nieobsłużony wyjątek, chwilowe zawieszenie HA), bez żadnego restartu?
Na wypadek takiego scenariusza integracja przy **każdym** cyklu głównej aktualizacji (co ok. 10
min) sprawdza: czy tryb automatyczny jest włączony, czy dzisiejsza sekwencja jeszcze nie ruszyła,
i czy nie ma już żywego, zaplanowanego timera - jeśli wszystkie trzy warunki są spełnione,
ponownie wywołuje tę samą logikę planowania (z tym samym mechanizmem nadrabiania opisanym
wyżej). Celowo **nie ma tu żadnego sztywno wpisanego zakresu godzin** (np. "1:00-7:00") - okno,
w którym bezpiecznik może zadziałać, wynika **wprost z Twojej konfiguracji** (trybu startu,
wschodu, bufora), więc automatycznie dostosowuje się do pory roku i Twoich ustawień, zamiast
być moim zgadywaniem.

## Watchdog sprzętowy

Jeśli Twój sterownik nawadniania ma sprzętowy licznik czasowy per strefa (typowo encja
`number.*`, gdzie wpisana wartość powoduje automatyczne zamknięcie zaworu przez sam
sterownik, niezależnie od Home Assistant), wskaż ją w polu "Watchdog timer" przy danej
strefie. Zachowanie zależy od jednego przełącznika: **"Automatycznie dostosuj czas
podlewania zgodny z pomiarem zużycia"** (domyślnie włączony, wymaga przepływomierza) - ta
sama decyzja steruje jednocześnie dwiema powiązanymi rzeczami, nie osobno:

- **Włączony**: czas podlewania może się wydłużyć/skrócić na żywo wg przepływomierza (patrz
  "Sterowanie objętościowe" wyżej), a watchdog ustawiany jest na **cały skonfigurowany limit
  bezpieczeństwa strefy** (`max_runtime_min`, pomniejszony o czas już zużyty w tej sesji) -
  żeby sterownik nigdy nie przeciął fizycznie zaworu, zanim integracja zdąży dociągnąć do celu
  objętościowego. Nadal chroni przed zawieszeniem HA - jeśli HA przestanie odpowiadać,
  sterownik i tak zamknie zawór sam, najpóźniej po upływie tego limitu.
- **Wyłączony**: czysto czasowe, bez wydłużania/skracania na żywo (nawet jeśli strefa ma
  przepływomierz - wtedy nadal służy do pomiaru zużycia i samo-kalibracji, tylko nie do
  regulacji czasu tej konkretnej sesji), a watchdog dopasowany dokładnie do wyliczonego/
  pozostałego czasu tej sesji - ciaśniejsze zabezpieczenie, spójne z tym, że integracja i tak
  nigdy nie zamierza podlewać dłużej.

**Ważne zastrzeżenie przy włączonym dostosowywaniu:** sumaryczny czas całej sekwencji może
nie zakończyć się dokładnie o wschodzie ani o zaplanowanej godzinie startu, jeśli wybrano tryb
"zacznij przed wschodem" - dostarczenie właściwej ilości wody ma pierwszeństwo przed trzymaniem
się harmonogramu co do minuty.

## Skąd biorą się dane do liczenia ET0

Metoda FAO-56 Penman-Monteith wymaga, oprócz danych z Twojej stacji pogody, dwóch dodatkowych
wielkości: **ciśnienia atmosferycznego** (do stałej psychrometrycznej) i pośrednio **wysokości
n.p.m.** (bo ciśnienie standardowe zależy od wysokości). Integracja radzi sobie z tym tak:

- **Ciśnienie**: jeśli wskażesz czujnik ciśnienia w konfiguracji, używany jest **realny
  pomiar** (dokładniejszy, bo uwzględnia aktualny układ pogodowy, nie tylko wysokość). Jeśli
  nie wskażesz - ciśnienie jest wyliczane standardowym wzorem barometrycznym FAO-56 z
  wysokości n.p.m. (to i tak wystarczająco dokładne dla potrzeb nawadniania).
- **Szerokość geograficzna**: z wybranej lokalizacji ogrodu (Krok 2 - mapa), jeśli ustawiona,
  w przeciwnym razie wprost z ogólnej konfiguracji HA. **Wysokość** zawsze wprost z ogólnej
  konfiguracji HA (Ustawienia → System → Ogólne) - krok mapy jej nie obejmuje.

W praktyce dla większości ogrodów przydomowych różnica między lokalizacją domu a lokalizacją
ogrodu jest pomijalna. **Ta sama lokalizacja służy też do samodzielnego
wyliczania wschodu słońca** (patrz sekcja niżej) - integracja nie potrzebuje do tego żadnej
dodatkowej encji.

## Typ nawadniania

Cztery typy per strefa, każdy inaczej liczony:

- **Zraszacze** / **Mikrozraszacze** - bez zmian koncepcyjnych względem reszty modelu: cała
  powierzchnia strefy, wydajność w mm/h wprost. Typ zmienia wyłącznie **sugerowaną wartość
  domyślną** wydajności (zraszacze ~12 mm/h, mikrozraszacze ~6 mm/h) - punkt startowy do
  ewentualnej korekty, nie coś wymuszonego.

- **Linia kroplująca** - inny model: **powierzchnia strefy jest ignorowana**, liczy się
  wyłącznie długość linii. Zakładane uproszczenie: linia prowadzona tuż obok roślin. Z długości
  i rozstawu integracja wylicza liczbę kroplowników, z tego i ich wydajności - całkowity
  przepływ, a z **efektywnej powierzchni** (długość × umowna szerokość zwilżanego pasa, 40 cm) -
  wydajność w mm/h, żeby dało się to połączyć ze wspólnym modelem bilansu wodnego (Kc/MAD/gleba
  działają wyłącznie w mm). Ta sama efektywna powierzchnia (nie "powierzchnia strefy" z
  formularza) jest też używana do przeliczania faktycznie dostarczonych litrów na mm - żeby
  obie strony rachunku były spójne.

- **Pojedyncze kroplowniki** - dla sekcji z kilkoma pojedynczymi emiterami (typowo donice/
  skrzynki), bez linii i bez rozstawu: liczba kroplowników × ich wydajność, podzielone przez
  **powierzchnię strefy z formularza** (używaną normalnie, tak jak dla zraszaczy).

**Wszystkie cztery typy dają tylko SUGEROWANĄ wartość** w polu "Wydajność" - zawsze można ją
ręcznie nadpisać, a jeśli strefa ma przepływomierz i włączone uczenie się, i tak zostanie z
czasem skorygowana na podstawie rzeczywistych pomiarów (patrz niżej).

**Pole "Wyliczaj wydajność automatycznie z typu nawadniania"** (domyślnie włączone) dotyczy
**WYŁĄCZNIE tego formularza** - co się pokazuje jako podpowiedź w polu "Wydajność" poniżej, gdy
wchodzisz w konfigurację. **Nie steruje** rzeczywistą wydajnością używaną do podlewania ani
wartością widoczną na sensorze strefy (`sensor.<strefa>_wydajnosc`) w Home Assistant - to
zależy wyłącznie od tego, co faktycznie zapiszesz w polu "Wydajność", i od przełącznika "Ucz
się z wodomierza" (patrz niżej), niezależnie od tego pola. Dotyczy **wszystkich
czterech typów** (zraszacze/mikrozraszacze dostają wartość z tabeli, linia/pojedyncze
kroplowniki - wyliczoną z parametrów). Jeśli wolisz mieć pewność, że Twoja ręcznie wpisana
wartość **nigdy** nie zostanie nadpisana przy kolejnej wizycie w "Konfiguruj" (np. bo wiesz, że
rzeczywiste ciśnienie w Twojej instalacji różni się od nominalnego z tabeli) - wyłącz to pole.
Wartość w polu "Wydajność" zostanie wtedy dokładnie taka, jaką ostatnio zapisałeś - w tym
formularzu.

**Priorytet nad statycznym wzorem: samo-wyuczona wartość z przepływomierza.** Jeśli integracja
zdążyła się już czegoś nauczyć z realnych pomiarów (patrz "Samo-kalibracja" niżej), podpowiedź w
formularzu pokazuje **wyuczoną** wartość zamiast generycznej z tabeli/wzoru - bardziej
wiarygodną, bo opartą na faktycznym zużyciu wody w Twoim ogrodzie, nie na nominalnych danych z
opakowania. **Sama kalibracja nigdy nie ginie przy ponownym wejściu w konfigurację** -
niezależnie od tego, co zapiszesz w polu "Wydajność", rzeczywiste podlewanie i tak korzysta z
wyuczonej wartości (dopóki "Ucz się z wodomierza" zostaje włączone) - ten mechanizm żyje w
osobnym, trwałym magazynie danych integracji, nie w samej konfiguracji strefy.

**Uwaga - te dwa przełączniki są od siebie NIEZALEŻNE, nie jeden nie "wyłącza" drugiego.**
Wyłączenie "Wyliczaj automatycznie" chroni wyłącznie to, co widzisz w tym formularzu - nie ma
żadnego wpływu na "Ucz się z wodomierza". Jeśli chcesz mieć **pełną, absolutną pewność**, że
Twoja ręcznie wpisana wartość rządzi rzeczywistym podlewaniem, a integracja nigdy jej nie
zastąpi wyuczoną liczbą - musisz wyłączyć **obie** opcje, nie tylko pierwszą.

**Ograniczenie techniczne:** sugerowana wartość dla linii/pojedynczych kroplowników jest
wyliczana z parametrów **już zapisanych** w poprzedniej konfiguracji tej strefy (formularz HA
nie może odczytać pól wypełnianych w tym samym kroku) - przy pierwszym ustawieniu strefy
wypełnij pole "Wydajność" ręcznie, wyliczy się ono automatycznie dopiero po zapisaniu i ponownym
wejściu w "Konfiguruj".

## Samo-kalibracja wydajności strefy z przepływomierza

Jeśli strefa ma podpięty przepływomierz, integracja **uczy się** jej rzeczywistej wydajności
zamiast polegać wyłącznie na wartości wpisanej ręcznie w konfiguracji, która często jest tylko
przybliżeniem "na oko" ze specyfikacji zraszaczy/kroplówki.

Po każdym podlaniu, w którym zawór był otwarty co najmniej minutę i mamy realny odczyt
przepływomierza (nie szacunek), integracja liczy: `zmierzona_wydajność = dostarczona_głębokość
(mm) / czas_pracy (h)`, i aktualizuje wykładnią średnią ważoną (nowsze pomiary liczą się
bardziej niż starsze, żeby model nadążał za realnymi zmianami - np. zapchany kroplownik,
spadek ciśnienia w sieci). Pojedynczy, skrajnie nierealny odczyt (np. glitch przepływomierza)
jest odrzucany, żeby nie zepsuć całej wyuczonej historii.

**Wyuczona wartość automatycznie zastępuje ręczną we wszystkich obliczeniach** (próg
podlewania, potrzebny czas, sprawdzenie limitu bezpieczeństwa w Repairs) - nie trzeba nic
ręcznie przełączać. Widoczna w `sensor.<strefa>_wydajnosc`, razem z wartością ręczną, liczbą
próbek i ostatnim pojedynczym pomiarem w atrybutach - do porównania i weryfikacji.

Bez przepływomierza samo-kalibracja nie działa (nie ma z czego się uczyć) - wartość ręczna
zostaje używana na stałe, tak jak dotychczas. **Nawet z przepływomierzem** możesz to świadomie
wyłączyć przełącznikiem "Ucz się wydajności z pomiaru wodomierza" per strefa (domyślnie
włączony) - przydatne, jeśli wolisz mieć pełną, przewidywalną kontrolę nad wpisaną ręcznie
wartością i nie chcesz, żeby integracja ją kiedykolwiek zmieniała.

## Sterowanie objętościowe (dla stref z przepływomierzem i włączonym dostosowywaniem)

Strefy z podłączonym przepływomierzem **i** włączonym przełącznikiem "Automatycznie dostosuj
czas podlewania zgodny z pomiarem zużycia" (patrz "Watchdog sprzętowy" niżej - to jedna,
wspólna decyzja) nie są już podlewane "na czas" - integracja mierzy
**faktycznie dostarczoną wodę na bieżąco** (co `rain_pause_check_interval_min`, tym samym
cyklem co sprawdzanie deszczu) i zamyka zawór, gdy dostarczona objętość osiągnie wyliczony cel
(zalecana ilość mm × powierzchnia strefy) - **niezależnie od tego, czy stało się to szybciej
czy wolniej niż wstępny szacunek czasowy**:

- **Szybciej niż szacowano** (wyższa rzeczywista wydajność niż zakładana): zawór zamyka się
  wcześniej - bez przelewania.
- **Wolniej niż szacowano** (spadek ciśnienia, wolniejszy przepływ): podlewanie jest
  **automatycznie wydłużane** ponad pierwotny szacunek, aż cel zostanie osiągnięty -
  ograniczone wyłącznie twardym limitem bezpieczeństwa `max_runtime_min`, który nigdy nie jest
  przekraczany niezależnie od niczego. Jeśli limit zostanie osiągnięty bez dostarczenia pełnej
  wyliczonej ilości, integracja loguje ostrzeżenie (warto wtedy sprawdzić ciśnienie/wydajność).

To może sprawić, że pojedyncze podlewanie (albo cała sekwencja, jeśli dotyczy to którejś ze
stref w kolejce) przekroczy pierwotnie zakładaną godzinę startu czy nawet sam wschód słońca -
uznane za akceptowalne, bo dostarczenie właściwej ilości wody jest ważniejsze niż trzymanie się
sztywnego harmonogramu co do minuty.

Strefy **bez** przepływomierza, albo z wyłączonym przełącznikiem dostosowywania, działają jak
dotychczas - czysto na czas, bez możliwości potwierdzenia czy wydłużenia (w pierwszym
przypadku nie ma czym zmierzyć rzeczywistej dostarczonej ilości; w drugim - to świadomy wybór
ciaśniejszego, przewidywalnego czasu).

Ręczne wymuszenie usługą `garden_irrigation.run_zone` **zawsze** respektuje dokładnie podaną
liczbę minut, bez sterowania objętościowego - to świadome polecenie "podlej dokładnie tyle",
nie "podlej aż wystarczy".

Sposób zakończenia ostatniego podlewania widoczny w atrybutach `sensor.<strefa>_zalecane_podlewanie`:
- `ostatnie_podlewanie_sposob_zakonczenia`: `objetosc_osiagnieta` / `czas` / `limit_bezpieczenstwa`
- `ostatnie_podlewanie_planowany_czas_min` / `_faktyczny_czas_min` / `_wydluzenie_min`

## Sekwencyjne uruchamianie stref z weryfikacją

Zawory są otwierane **zawsze pojedynczo, nigdy równolegle**. Dla każdej strefy, zaczynając od
pierwszej, integracja:

1. Wysyła polecenie otwarcia zaworu.
2. **Odpytuje stan encji co 1 sekundę**, aż potwierdzi, że faktycznie się otworzył (albo upłynie
   `valve_verify_timeout_sec`, domyślnie 15s). Jeśli masz skonfigurowany przepływomierz
   chwilowy (główny albo per strefa), weryfikacja **dodatkowo** wymaga, żeby przepływ przekroczył
   próg braku przepływu - to mocniejsze potwierdzenie niż sam stan encji, bo wychwytuje np.
   zawór, który zgłasza "otwarty", ale fizycznie się nie otworzył. Brak odczytu z
   przepływomierza nie blokuje weryfikacji - liczy się wtedy tylko stan encji, jak bez tej opcji.
   Jeśli zawór się nie otworzy - loguje błąd, pomija tę strefę i **kontynuuje z kolejną**
   (jedna wadliwa strefa nie blokuje reszty ogrodu).
3. Po zakończeniu czasu podlewania wysyła polecenie zamknięcia.
4. **Znowu odpytuje stan** (i przepływ chwilowy, jeśli skonfigurowany - musi spaść poniżej
   progu), aż potwierdzi zamknięcie. To jednocześnie moment, w którym event zmiany stanu zdąży
   wyzwolić odczyt przepływomierza SKUMULOWANEGO (jeśli podłączony) i policzenie zużytej wody.
   Jeśli zawór nie potwierdzi zamknięcia w limicie czasu - integracja loguje błąd na poziomie
   ERROR i **przerywa całą resztę sekwencji** (nie otwiera kolejnej strefy, dopóki nie ma
   pewności, że poprzednia jest bezpiecznie zamknięta - unika to np. spadku ciśnienia przez
   dwie jednocześnie otwarte/przeciekające strefy).
5. Dopiero po potwierdzonym zamknięciu czeka `zone_transition_delay_sec` (domyślnie 5s) i
   przechodzi do otwarcia kolejnej strefy w kolejności, powtarzając od punktu 1.

Ten sam mechanizm weryfikacji działa też przy pojedynczym ręcznym uruchomieniu strefy
(przycisk / usługa `run_zone`), nie tylko w sekwencji.

## Minimalny odstęp między podlewaniami

Sam model bilansu wodnego już naturalnie prowadzi do rzadszego, głębszego podlewania niż
harmonogram czasowy - ale jeśli chcesz mieć twardą gwarancję (np. żeby świadomie przyzwyczajać
korzenie do sięgania głębiej), ustaw `min_days_between_watering` dla danej strefy.
Nawet gdy deficyt wody przekroczy próg wcześniej, strefa poczeka do upływu tylu dni od
ostatniego faktycznego podlewania - deficyt w tym czasie dalej rośnie (nic się nie zeruje ani
nie przepada), po prostu rekomendacja jest wstrzymywana do upływu minimalnego odstępu.

### Dynamiczna korekta progu MAD wg FAO-56 (i automatyczne obejście przy upale)

Próg MAD **nie jest już sztywną liczbą** z wybranych roślin - integracja koryguje go co noc
oficjalnym wzorem z FAO-56 (rozdział 8), na podstawie wczorajszego tempa zużycia wody (ETc):

```
próg_skorygowany = próg_bazowy + 0,04 × (5 − ETc)     [ograniczone do zakresu 0,1-0,8]
```

Sens fizyczny: przy upale/suszy (wysokie ETc) roślina zaczyna cierpieć **wcześniej**, bo
korzenie nie nadążają dostarczać wody przy tak dużym zapotrzebowaniu atmosfery, nawet zanim
gleba wyschnie do "normalnego" poziomu - próg jest wtedy automatycznie **niższy**, więc
podlewanie włącza się szybciej. Przy chłodnej, pochmurnej pogodzie próg jest **wyższy** -
gleba może bezpiecznie wyschnąć bardziej, zanim to problem.

**To automatycznie rozwiązuje napięcie między minimalnym odstępem a falą upałów**, bez
ręcznego pilnowania: gdy wczorajsze ETc przekroczy 5 mm/dzień (dokładnie próg, przy którym
korekta FAO-56 staje się ujemna - oficjalna definicja "gorących, suchych warunków"),
**minimalny odstęp między podlewaniami jest tego dnia automatycznie pomijany** dla tej
strefy. Nie trzeba ręcznie podnosić ani obniżać niczego przed spodziewanym upałem - model
sam to wykryje z rzeczywistych danych pogodowych i na jeden dzień zniesie sztywny limit,
zamiast czekać, aż roślina zacznie realnie cierpieć.

Efektywny (skorygowany) próg, wartość bazowa, wczorajsze ETc i informacja, czy dziś
zadziałało obejście, są widoczne w atrybutach `sensor.<strefa>_przyjety_prog_mad`.

Cały ten mechanizm można wyłączyć **na bieżąco**, bez ponownej konfiguracji integracji -
przełącznikiem `switch.garden_irrigation_dynamic_mad_enabled` ("Dynamiczna korekta MAD
(FAO-56)"). Wyłączenie przywraca sztywny, bazowy próg MAD (z wybranych roślin/ręcznej
kalibracji), bez żadnej dziennej korekty ani automatycznego obejścia minimalnego odstępu.
Pole `dynamic_mad_enabled` w kreatorze konfiguracji ustawia tylko wartość **początkową** przy
pierwszej instalacji - późniejsze zmiany realnie kontroluje ten przełącznik, nie kreator.

## Ochrona przed wiatrem i przymrozkiem

- **Wiatr**: strefy oznaczone jako `wind_sensitive` (typowo zraszacze - drift, nierówne
  pokrycie) są pomijane, gdy aktualna prędkość wiatru przekroczy `wind_skip_threshold_ms`.
  Sprawdzane świeżo tuż przed startem (podobnie jak opad).
- **Przymrozek**: jeśli aktualna temperatura spadnie poniżej `frost_threshold_c`, **całe**
  podlewanie (wszystkie strefy) jest wstrzymywane tego dnia - to ryzyko dla całego systemu
  (węże, zawory), nie tylko konkretnej rośliny. Sprawdzane co noc i świeżo przed startem.

Obie kontrole nie zerują deficytu - jeśli danego dnia zostanie pominięte, dogoni się przy
najbliższej okazji, gdy warunki na to pozwolą.

## Wyłącznik globalny (tryb urlopowy)

Encja `switch.wstrzymaj_cale_podlewanie` - włączona blokuje WSZYSTKO: ręczne zatwierdzanie,
`approve_all`, sekwencję przed wschodem i tryb automatyczny, dopóki nie zostanie wyłączona.
Przydatne na czas wyjazdu, prac ogrodowych, albo gdy woda jest fizycznie odcięta. Deficyt wody
w tym czasie nadal jest liczony (nic nie przepada) - po wyłączeniu pauzy integracja po prostu
zaproponuje podlewanie zgodnie z aktualnym stanem.

## Statystyki zużycia wody

Dostępne jako osobne sensory (patrz niżej) - dobowe, miesięczne i roczne zużycie per strefa
oraz łącznie dla całego ogrodu, liczone z tych samych danych co bilans wodny (realny odczyt
przepływomierza, jeśli podłączony, w przeciwnym razie oszacowanie z czasu pracy i wydajności).
Liczniki dobowe zerują się o północy, miesięczne pierwszego dnia miesiąca, roczne pierwszego
stycznia.

## Zgłoszenia w Home Assistant Repairs

Integracja korzysta z wbudowanego mechanizmu HA Repairs (Ustawienia → System → Repairs) do
zgłaszania problemów wymagających Twojej uwagi, zamiast chować je wyłącznie w logach:

- **Brakująca encja strefy** - sprawdzane przy starcie integracji, jeśli skonfigurowany zawór
  nie istnieje w HA.
- **Za niski limit czasu podlewania strefy** - sprawdzane przy starcie: jeśli skonfigurowany
  `max_runtime_min` jest mniejszy niż czas potrzebny do pełnego napełnienia strefy korzeniowej
  od zera (przy obecnej wydajności zraszaczy/kroplówki), integracja nigdy nie zdąży dolać pełnej
  dawki po dłuższej przerwie (urlop, seria pominiętych dni z powodu deszczu) - zgłoszenie
  podaje dokładną, wyliczoną wartość, o jaką warto podnieść limit.
- **Zawór nie potwierdził otwarcia** - informacyjne, ta jedna strefa została pominięta, reszta
  działa dalej.
- **Zawór nie potwierdził zamknięcia** - poważniejsze, bo mógł zostać fizycznie otwarty; reszta
  sekwencji jest przerywana dla bezpieczeństwa, warto sprawdzić ręcznie jak najszybciej.

Zgłoszenia znikają automatycznie, gdy problem ustąpi (np. zawór znów zacznie poprawnie
odpowiadać).

## Przewidywalne identyfikatory encji

Każda encja ma wymuszony, stabilny `entity_id` w formacie
`<domena>.garden_irrigation_<zone_NN>_<angielski_sufiks>` (np.
`sensor.garden_irrigation_zone_01_recommended_watering`,
`switch.garden_irrigation_irrigation_paused`) - **prefiks integracji** minimalizuje ryzyko
kolizji z innymi encjami w Twoim HA, a **numer strefy zamiast jej opisowej nazwy** (`zone_01`,
`zone_02`...) chroni przed absurdalnie długimi identyfikatorami, jeśli nadasz strefie długą
nazwę, i nie zmienia się nawet jeśli tę nazwę później zmienisz - zmienia się tylko wyświetlana
etykieta (`friendly_name`), nie techniczny identyfikator. Numer strefy odpowiada jej pozycji w
konfiguracji (pole `zoneN_*`), nie kolejności wyświetlania. Nazwy encji (`friendly_name`,
widoczna w UI) pozostają w pełni po polsku i budowane są z nazwy, którą sam nadałeś strefie -
zmienia się wyłącznie techniczny `entity_id` w tle.

**Ważne:** to działa niezawodnie tylko dla **nowo tworzonych** encji - rejestr encji HA raz
nadany `entity_id` trzyma na stałe, nawet po zmianie kodu integracji. Jeśli aktualizujesz z
wcześniejszej wersji (a nie instalujesz od zera), stare encje zachowają swoje dotychczasowe
identyfikatory - żeby dostać nowe, trzeba usunąć integrację i dodać ją ponownie (świeży rejestr).

## Podgląd zmian w ciągu dnia (sensory "przewidywany")

Główny deficyt wody i zalecane podlewanie przeliczają się **raz na dobę** (nocne
przeliczenie) plus **świeżo tuż przed startem** - to jedyne wartości, które faktycznie
sterują podlewaniem, i celowo nie zmieniają się w trakcie dnia poza tymi dwoma momentami.

Obok nich dostępna jest **osobna, czysto informacyjna para sensorów** per strefa:
`sensor.<strefa>_przewidywany_deficyt_wody` i `sensor.<strefa>_przewidywany_czas_podlewania`.
Rosną **płynnie przez cały dzień** - integracja rozkłada dobową stratę wody (ETc) na małe
przyrosty co każdy cykl aktualizacji (razem z na bieżąco odejmowanym opadem), zamiast czekać
do najbliższej północy. Dzięki temu widać "na żywo", jak system ocenia sytuację w danym
momencie dnia.

**Ważne szczegóły tych sensorów** (żeby wiedzieć, na czym stoisz):
- Rozkład straty wody w ciągu dnia jest **równomierny w czasie**, nie ważony rzeczywistym
  rytmem parowania (które w naturze koncentruje się w dzień, prawie zerowe w nocy) - to
  celowe uproszczenie, nie próba maksymalnej dokładności.
- **Liczba minut na `_przewidywany_czas_podlewania` jest ZAWSZE czystą funkcją przewidywanego
  deficytu** - dokładnie ta sama zależność co w głównym sensorze (czas = potrzebna ilość mm /
  wydajność), bez wyjątków i bez zerowania przez cokolwiek. Informacja o tym, co *aktualnie*
  blokowałoby zatwierdzenie (deszcz/prognoza/wiatr/przymrozek/minimalny odstęp) jest **osobnym
  atrybutem `zablokowane_przez`** (lista powodów albo `null`) - nigdy nie zmienia samej liczby
  minut, tylko dodaje kontekst obok niej.
- `zablokowane_przez` jest odświeżany **raz na godzinę**, nie co cykl (10 min) - wiatr i
  temperatura naturalnie skaczą z minuty na minutę, więc częstsze sprawdzanie dawałoby
  migoczący wynik (blokada → brak blokady → blokada w ciągu jednej godziny). Sam deficyt i
  liczba minut nadal aktualizują się płynnie co 10 minut - throttling dotyczy wyłącznie tego
  jednego atrybutu kontekstowego.
- **Nie wpływają na żadną faktyczną decyzję** - to wyłącznie podgląd. Jedynym źródłem prawdy
  dla tego, czy i kiedy podlewanie faktycznie się odbędzie, pozostają główne sensory
  (`_zalecane_podlewanie`, `_deficyt_wody_w_glebie`) i logika opisana w resztę tego dokumentu.

## Dostępne encje

**Sensory:**
- `sensor.garden_irrigation_et0_yesterday` - ET0 wyliczone dla poprzedniej doby
- `sensor.garden_irrigation_weather_inputs` ("Dane wejściowe pogody") - do weryfikacji, czy nic
  nie jest pomijane: wartość główna to metoda użyta wczoraj (`penman_monteith` / `hargreaves` /
  `brak_danych`); atrybuty: żywy odczyt teraz (temperatura, nasłonecznienie, wilgotność, wiatr),
  dokładne dane wejściowe z wczoraj (tmax/tmin/tmean, uśrednione nasłonecznienie/wiatr/
  wilgotność, liczba próbek każdego), prognoza opadu (mm i kiedy pobrana), surowy licznik opadu
  total rain, `opad_zmierzony_dzisiaj_mm` (suma przyrostów licznika od ostatniej północy,
  faktycznie odjęta od deficytu każdej strefy - nie surowy odczyt, tylko realnie policzona
  dzisiejsza suma), `prognoza_nocna` (trwała migawka z ostatniego nocnego przeliczenia -
  wartość prognozy, próg, czy wstrzymano - nadpisywana wyłącznie przy KOLEJNYM nocnym
  przeliczeniu, nie w ciągu dnia) i `prognoza_ostatnie_sprawdzenie` (najnowsze sprawdzenie
  prognozy z JAKIEGOKOLWIEK źródła - noc / przed zatwierdzeniem strefy / przed sekwencją /
  godzinne odświeżenie - z opisem, kiedy i skąd, nadpisywane przy każdym kolejnym sprawdzeniu)
- per strefa `sensor.<nazwa>_zalecane_podlewanie` ma dodatkowo atrybut
  `opad_podczas_biezacej_pauzy_mm` - żywa suma opadu zmierzonego od momentu wstrzymania tej
  konkretnej strefy z powodu deszczu (aktualizowana co cykl sprawdzania, widoczna w trakcie
  trwania pauzy, nie tylko po jej zakończeniu)
- `sensor.przewidywana_godzina_rozpoczecia_sekwencji` - godzina startu najbliższej
  zaplanowanej sekwencji (encja typu timestamp). Atrybuty: status
  (`scheduled`/`running`/`done`/`cancelled_rain`/`no_zones`), planowany wschód, łączny czas,
  oraz pełna kolejność i planowana godzina startu każdej strefy
- per strefa `sensor.<nazwa>_zalecane_podlewanie` - wartość w minutach, atrybuty: status, mm,
  powód pominięcia, sposób zakończenia ostatniego podlewania (patrz sekcja "Sterowanie
  objętościowe")
- per strefa `sensor.<nazwa>_deficyt_wody_w_glebie` - aktualny deficyt w mm
- per strefa `sensor.<nazwa>_woda_w_glebie` / `_woda_w_glebie_na_zywo` - odwrotność deficytu:
  ile wody realnie jest teraz w strefie korzeniowej (mm i % pojemności w atrybutach) - pierwszy
  to samo tempo aktualizacji co główny deficyt, drugi płynnie w ciągu dnia jak sensory "na żywo"
- per strefa `sensor.<nazwa>_przewidywany_deficyt_wody` / `_przewidywany_czas_podlewania` -
  podgląd rosnący w ciągu dnia, czysto informacyjny (patrz sekcja wyżej)
- per strefa `sensor.<nazwa>_parametry_gleby_i_roslin` - wartość to lista wybranych roślin;
  atrybuty pokazują glebę, przyjęte Kc/głębokość/MAD oraz pełny rozkład WSZYSTKICH wybranych
  roślin z ich indywidualnymi parametrami
- per strefa `sensor.<nazwa>_przyjete_kc` - wartość liczbowa Kc używana w bilansie, z
  atrybutem "przyjęte od" (nazwa rośliny albo "ręczna kalibracja") i pełną listą
  rośliny→Kc dla wszystkich wybranych roślin w tej strefie
- per strefa `sensor.<nazwa>_przyjety_prog_mad` - to samo dla progu MAD (skorygowanego FAO-56)
- per strefa `sensor.<nazwa>_minimalny_odstep_miedzy_podlewaniami` - skonfigurowana liczba dni
  (0 = brak limitu), z atrybutami: data ostatniego podlewania, ile dni minęło, czy dziś aktywny
- per strefa `sensor.<nazwa>_maksymalny_czas_podlewania` - skonfigurowany limit bezpieczeństwa
  (min), z atrybutem `wymagany_czas_pelnego_napelnienia_min` (ile faktycznie potrzeba, żeby w
  pełni napełnić strefę korzeniową od zera) i `za_niski_limit` (True/False)
- per strefa `sensor.<nazwa>_powierzchnia_strefy` (m²)
- per strefa `sensor.<nazwa>_wydajnosc` (mm/h) - efektywna (wyuczona jeśli już jest, w
  przeciwnym razie ręczna), z atrybutami: wartość ręczna, wyuczona, liczba próbek, ostatni pomiar
- per strefa `sensor.<nazwa>_zuzycie_wody_dzis` / `_zuzycie_wody_w_tym_miesiacu` / `_zuzycie_wody_w_tym_roku` (litry)
- per strefa `sensor.<nazwa>_zuzycie_wody_podczas_ostatniego_podlewania` (litry) - tylko ostatnie,
  pojedyncze podlanie (nie suma), z atrybutem `kiedy`
- `sensor.laczne_zuzycie_wody_dzis` / `_w_tym_miesiacu` / `_w_tym_roku` (litry, cały ogród)
- `sensor.garden_irrigation_total_water_last` - suma ostatniego pojedynczego podlewania KAŻDEJ
  strefy z osobna (niekoniecznie ten sam dzień dla wszystkich), z rozbiciem per strefa w atrybutach

**Switch:**
- `switch.garden_irrigation_irrigation_paused` - globalna pauza (tryb urlopowy), patrz wyżej
- `switch.garden_irrigation_dynamic_mad_enabled` - włącza/wyłącza dynamiczną korektę MAD wg
  FAO-56 (patrz sekcja "Minimalny odstęp między podlewaniami")

**Binary sensory:**
- per strefa `binary_sensor.<nazwa>_wstrzymane_z_powodu_deszczu` - włączony, gdy TA strefa
  jest właśnie wstrzymana z powodu opadu w trakcie podlewania
- `binary_sensor.podlewanie_wstrzymane_z_powodu_deszczu` - włączony, gdy JAKAKOLWIEK strefa
  jest wstrzymana; atrybut z listą wstrzymanych stref

**Przyciski:**
- per strefa "zatwierdź i uruchom" / "pomiń dzisiaj"
- "Zatwierdź wszystkie oczekujące strefy"
- "Zaplanuj sekwencję przed wschodem słońca"

## Usługi

| Usługa | Parametry | Działanie |
|---|---|---|
| `garden_irrigation.approve_zone` | `zone_id` | Zatwierdza i uruchamia rekomendację dla jednej strefy (ze świeżym sprawdzeniem opadu/prognozy) |
| `garden_irrigation.approve_all` | - | Zatwierdza wszystkie oczekujące strefy po kolei |
| `garden_irrigation.skip_zone` | `zone_id` | Anuluje dzisiejszą rekomendację bez podlewania |
| `garden_irrigation.run_zone` | `zone_id`, `minutes` | Uruchamia strefę ręcznie na zadany czas, niezależnie od rekomendacji |
| `garden_irrigation.run_sequence_before_sunrise` | - | Buduje i planuje sekwencję wszystkich zatwierdzonych stref, licząc start wstecz od wschodu |

## Kalibracja

System startuje z rozsądnymi wartościami domyślnymi (Kc, MAD, pojemność wodna gleby), ale to
przybliżenia - Twój ogród, mikroklimat i faktyczne warunki glebowe mogą się różnić. Po
pierwszych 2-3 tygodniach obserwacji:

- Jeśli roślina usycha mimo regularnego podlewania - obniż próg MAD dla tej strefy (pole
  "Ręczna kalibracja MAD", np. z 0.45 na 0.35) - spowoduje to wcześniejsze uruchamianie
  podlewania.
- Jeśli strefa jest przelewana - podnieś próg MAD, albo obniż Kc (pole "Ręczna kalibracja
  Kc") - spowoduje to wolniejszy przyrost deficytu i rzadsze podlewanie.
- Sensor `sensor.<nazwa>_przyjete_kc` i `sensor.<nazwa>_przyjety_prog_mad` pokazują dokładnie,
  jaka wartość jest aktualnie używana i skąd się wzięła (z której rośliny albo z ręcznej
  kalibracji) - to punkt wyjścia do oceny, co warto skorygować.

## Rzeczy warte świadomości

- Sekwencja podlewania i oczekiwanie na "obudzenie się" w trybie automatycznym działają jako
  zadania w tle wewnątrz uruchomionego Home Assistanta - **nie** są zapisywane w bazie ani
  odtwarzane po restarcie. Restart HA w trakcie oczekiwania na start przerywa zaplanowane
  podlewanie na tę noc.
- Dokładny kształt danych zwracanych przez `weather.get_forecasts` może się różnić między
  integracjami pogodowymi - jeśli po skonfigurowaniu encji `weather.*` w logach pojawi się
  ostrzeżenie o nieudanym pobraniu prognozy, sprawdź ręcznie w Developer Tools → Usługi,
  wywołując `weather.get_forecasts` z `type: hourly` na swojej encji (część integracji
  obsługuje tylko prognozę dobową, nie godzinową).
- Integracja celowo NIE wysyła powiadomień push (np. przy pauzie z powodu deszczu) - stan
  zawsze widać w sensorach/atrybutach, ale nikt nie zostanie w nocy obudzony przez telefon.
  Jeśli mimo to chcesz powiadomienia, najprościej dodać własną automatyzację HA nasłuchującą
  zmian `binary_sensor.podlewanie_wstrzymane_z_powodu_deszczu` albo stanu `sensor.*_zalecane_podlewanie`.
- Pola stref w kreatorze konfiguracji mają czytelne opisy dla pierwszych 12 stref - przy
  większej liczbie kolejne pola nadal działają, tylko bez tłumaczonej etykiety.
