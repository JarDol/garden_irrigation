approve_zone:
  name: Zatwierdź strefę
  description: Zatwierdza i natychmiast uruchamia rekomendowane podlewanie danej strefy.
  fields:
    zone_id:
      name: Numer strefy
      required: true
      selector:
        number:
          min: 1
          max: 8

approve_all:
  name: Zatwierdź wszystkie
  description: Zatwierdza i uruchamia wszystkie strefy oczekujące na podlewanie.

skip_zone:
  name: Pomiń strefę
  description: Anuluje dzisiejszą rekomendację podlewania dla danej strefy (bez zerowania deficytu).
  fields:
    zone_id:
      name: Numer strefy
      required: true
      selector:
        number:
          min: 1
          max: 8

run_zone:
  name: Uruchom strefę ręcznie
  description: Włącza strefę na zadaną liczbę minut, niezależnie od rekomendacji.
  fields:
    zone_id:
      name: Numer strefy
      required: true
      selector:
        number:
          min: 1
          max: 8
    minutes:
      name: Czas (minuty)
      required: false
      default: 10
      selector:
        number:
          min: 1
          max: 180

run_sequence_before_sunrise:
  name: Zaplanuj sekwencję przed wschodem słońca
  description: >
    Zbiera wszystkie strefy oczekujące na podlewanie, sprawdza świeżą prognozę opadu,
    i planuje ich sekwencyjne (jedna po drugiej) uruchomienie tak, aby ostatnia strefa
    zakończyła podlewanie mniej więcej o wschodzie słońca (na podstawie skonfigurowanej
    encji sun_next_rising). Jeśli łączny czas wszystkich stref nie zmieściłby się przed
    wschodem, sekwencja startuje natychmiast.
