# PR_DKE_Gruppe02

+++++++++++++++++++++++++++++++++++++++++

## Start aller vier Applikationen mit Befehl:

### Linux / macOS: 
    ./start-all.sh
falls nicht ausreichend rechte:

    chmod +x start-all.sh
    ./start-all.sh

+++++++++++++++++++++++++++++++++++++++++

### Ports:

    Strecken: http://127.0.0.1:5001

    Fahrplan: http://127.0.0.1:5002

    Flotten: http://127.0.0.1:5003

    Ticket: http://127.0.0.1:5004

+++++++++++++++++++++++++++++++++++++++++

## Fahrplan 

### User und Passwörter:
    Benutzername:admin
    Passwort: admin

Für die User auch: 

    username = pw
    eg: user1 --> pw(user1) = user1

### Navigation

Im Reiter oben folgende Drei Seiten wählbar:

    -Dashboard
    -Fahrten
    -Mitarbeiter
    -Haltepläne
    

### Admin Dashboard: Daten synchronisieren
Im Admin-Dashboard können Daten aus den externen Services geladen werden:

    -Alles synchronisieren (Strecken + Züge + Wartungen)
    -Nur Flotte (Züge + Wartungen)
    -Nur Strecken


### Fahrten / Fahrplan-Logik

Die Fahrplan-Erstellung funktioniert nach dem Prinzip “All or Nothing”:

    Eine Fahrtdurchführung kann nur gespeichert werden, wenn:
        -ein Zug gewählt wurde
        -der Zug im Zeitraum verfügbar ist
        -der Zug keine Wartung im Zeitraum hat
        -alle benötigten Daten für die Berechnung der Halte/Segmente vorhanden sind

### Neue Fahrtdurchführung erstellen

Pfad: Fahrten → Neue Fahrtdurchführung

    Beim Erstellen werden automatisch erzeugt:

        Dienstzuweisungen (Mitarbeiter)

        Fahrt-Halte (Start → Ziel)

        Fahrt-Segmente inkl. Preisberechnung (base_price * price_factor)

#### Konfliktprüfungen beim Speichern

    Beim Speichern wird geprüft:
        Wartungskonflikt: der Zug darf keine Wartung überlappen
        Zug-Belegung: der Zug darf nicht gleichzeitig in einer anderen Fahrtdurchführung verwendet werden
        Falls ein Konflikt besteht, wird abgebrochen und es erfolgt ein Rollback.



+++++++++++++++++++++++++++++++++++++++++

Ticketsystem Login:

Predefined admin-user für Zugang zu Adminportal:
Benutzername: admin
Passwort: admin

Predefined dummy-user für Zugang zum Kundenportal:
Benutzername: user
Passwort: user

+++++++++++++++++++++++++++++++++++++++++

Flotten Login:

Admin Login Daten: 
Username: admin
Passwort admin

Mitarbeiter Login Daten für Mitarbeiter 2:
Username: User2 
Passwort: User2

(Für alle Mitarbeiter identisch - es ändert sich nur die Nummer
eg: User3 / User3, User4 / User4 )

+++++++++++++++++++++++++++++++++++++++++

