# Single Court lokaal testen

Pak het zipbestand uit, open een terminal in de map single-court en voer `python3 server.py` uit. Op Windows kun je `py server.py` gebruiken. Python 3.9 of nieuwer volstaat. Open http://127.0.0.1:8000.

Meld je aan met een fictief adres zoals speler@example.com. Kies Iedereen en geef het eerste profiel een Smash voor een demomatch. Kies een vrij tijdslot en claim het. Test opnieuw met een ander fictief adres om te zien dat het tijdslot bezet blijft.

De server maakt single-court.sqlite3 bij de eerste start. Hierin staan 39 voorbeeldlocaties, 1.000 fictieve profielen, aanmeldingen en claims. Per club staan op zondag 14 februari 2027 tien voorbeeldslots van een uur klaar, van 10.00 tot 20.00 uur. Een claim reserveert het hele slot voor twee personen. Stop de server voordat je het databasebestand verwijdert om de demo te wissen.

Dit is een lokale testversie met fictieve matches. De demo deelt aanmeldingen niet met andere spelers. Echte matching, aanmeldlinks per mail, bevestiging door de tweede speler en de koppeling met FOYS en betalingen horen bij een volgende versie.

De clubkeuze bevat ook aangekondigde locaties als testoptie. Olympiaplein is weggelaten wegens sluiting. Je ziet profielen bij dezelfde club als jullie voorkeuren bij elkaar passen. De bereidheid van een fictief profiel om te matchen ligt vooraf vast.

Alle profielen krijgen een van zestien gegenereerde demoportretten. Portretten worden hergebruikt. Bij het starten worden de extra profielen toegevoegd aan een bestaande database. Gebruik voor een nieuwe aanmelding een nieuw fictief e-mailadres.
