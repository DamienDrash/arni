"""
Seed script: Generate realistic chat conversations for a tenant.

Default target is GETIMPULSE Berlin (tenant_id=6), based on existing studio_members.
It can append realistic support traffic and create active handoffs for escalation views.

Usage examples:
    python scripts/seed_chat_data.py
    python scripts/seed_chat_data.py --tenant-id 6 --days 120 --target-sessions 1400 --open-handoffs 28
    python scripts/seed_chat_data.py --tenant-id 6 --reset
"""

from __future__ import annotations
import json
import random
import sys
import os
import argparse
from datetime import datetime, timedelta, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from redis import Redis

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://arni:arni_dev_password@postgres:5432/arni")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
TENANT_ID = 6  # GETIMPULSE Berlin

# ── Conversation templates (German, realistic Arni persona) ──────────────────

TEMPLATES = {
    "preise_premium": {
        "intent": "pricing",
        "agent": "persona",
        "confidence_range": (0.88, 0.97),
        "escalation_rate": 0.03,
        "turns": [
            ("user",      "Hi! Was kostet bei euch das Premium Abo?"),
            ("assistant", "Hey {name}! 💪 Der Premium-Tarif liegt bei 39,90€ im Monat – mit vollem Zugang zu allen Kursen, Sauna und Personal-Training-Rabatt. Flex-Tarif gibt's für 29,90€, ganz ohne Vertragsbindung. Was passt besser zu dir?"),
            ("user",      "Was ist der Unterschied genau?"),
            ("assistant", "Flex = monatlich kündbar, kein Kursvorrecht. Premium = 12-Monats-Vertrag, Kurs-Prio, 10% auf PT-Sessions und freier Saunazugang. Für Vieltrainer definitiv das bessere Angebot! 🔥"),
            ("user",      "Ok danke, ich überleg's mir"),
            ("assistant", "Klar, kein Stress! Wenn du Fragen hast oder direkt starten willst – ich bin da. ✅"),
        ]
    },
    "preise_flex_vs_premium": {
        "intent": "pricing",
        "agent": "persona",
        "confidence_range": (0.85, 0.95),
        "escalation_rate": 0.02,
        "turns": [
            ("user",      "Kann man bei euch auch ohne Vertrag trainieren?"),
            ("assistant", "Ja! 😊 Unser Flex-Tarif für 29,90€/Monat – monatlich kündbar, kein Mindestvertrag. Perfekt wenn du flexibel bleiben willst."),
            ("user",      "Und was bekomme ich alles dafür?"),
            ("assistant", "Freie Nutzung aller Geräte, Umkleide und Duschen, plus alle Kurse nach Verfügbarkeit (keine garantierte Prio wie beim Premium). Was ist dir am wichtigsten?"),
            ("user",      "Kurse nehme ich eig nicht so oft, das reicht dann"),
            ("assistant", "Dann bist du mit Flex perfekt bedient! Einfach vorbeikommen oder online abschließen. 💪"),
        ]
    },
    "oeffnungszeiten_allgemein": {
        "intent": "hours",
        "agent": "persona",
        "confidence_range": (0.90, 0.99),
        "escalation_rate": 0.01,
        "turns": [
            ("user",      "Wann habt ihr geöffnet?"),
            ("assistant", "Hey! 🏋️ GETIMPULSE ist für dich da:\nMo–Fr: 06:30–23:00 Uhr\nSa: 08:00–20:00 Uhr\nSo & Feiertage: 09:00–18:00 Uhr\nAn Heiligabend und Silvester haben wir kürzere Zeiten – infos dazu auf unserer Website. Noch Fragen?"),
            ("user",      "Und die Sauna, die hat eigene Zeiten?"),
            ("assistant", "Sauna läuft innerhalb der Studiozeiten, also täglich verfügbar. 🧖 Nur frühmorgens (vor 8 Uhr) und kurz vor Schluss (letzte 30 Min) ist sie gesperrt für Reinigung."),
        ]
    },
    "oeffnungszeiten_feiertag": {
        "intent": "hours",
        "agent": "persona",
        "confidence_range": (0.87, 0.97),
        "escalation_rate": 0.01,
        "turns": [
            ("user",      "Habt ihr an Pfingsten geöffnet?"),
            ("assistant", "Hey {name}! An Pfingstsonntag sind wir von 09:00–18:00 Uhr für dich da, Pfingstmontag ebenfalls 09:00–18:00. Normalbetrieb ab Dienstag. ✅"),
            ("user",      "Super danke!"),
        ]
    },
    "kurs_buchen_yoga": {
        "intent": "booking",
        "agent": "ops",
        "confidence_range": (0.82, 0.94),
        "escalation_rate": 0.05,
        "turns": [
            ("user",      "Kann ich noch für den Yoga-Kurs am Mittwoch anmelden?"),
            ("assistant", "Hey {name}! 🧘 Lass mich kurz nachschauen… Der Mittwoch-Yoga (18:30 Uhr) hat noch 3 freie Plätze. Soll ich dich direkt eintragen?"),
            ("user",      "Ja bitte!"),
            ("assistant", "Erledigt! Du bist für Mittwoch, 18:30 Yoga eingetragen. Denk an deine Matte und bequeme Klamotten. Bis dann! 🙏"),
            ("user",      "Perfekt danke"),
        ]
    },
    "kurs_buchen_spinning": {
        "intent": "booking",
        "agent": "ops",
        "confidence_range": (0.80, 0.93),
        "escalation_rate": 0.07,
        "turns": [
            ("user",      "Gibt es noch Plätze im Spinning Kurs Freitagabend?"),
            ("assistant", "Hi! 🚴 Der Freitag-Spinning (19:00 Uhr) ist leider ausgebucht. Aber Donnerstag 19:00 hat noch 5 Plätze – interessiert?"),
            ("user",      "Donnerstag geht leider nicht…"),
            ("assistant", "Kein Problem! Ich trag dich auf die Warteliste für Freitag. Falls jemand absagt, kriegst du direkt Bescheid. Deal? ✅"),
            ("user",      "Ja gerne"),
            ("assistant", "Auf der Liste! Drücken wir die Daumen. 🤞"),
        ]
    },
    "kurs_buchen_functional": {
        "intent": "booking",
        "agent": "ops",
        "confidence_range": (0.83, 0.95),
        "escalation_rate": 0.04,
        "turns": [
            ("user",      "Wann ist der nächste Functional Training Kurs?"),
            ("assistant", "Hey! 💪 Functional Training läuft bei uns:\n• Mo 07:00\n• Mi 12:30 (Mittags!)\n• Fr 18:00\n• Sa 09:30\n\nWelcher passt dir am besten?"),
            ("user",      "Samstag 9:30 klingt gut"),
            ("assistant", "Top! Samstag 09:30 Functional Training – Platz ist frei. Eintragen? 🔥"),
            ("user",      "Ja bitte!"),
            ("assistant", "Done! Bis Samstag früh. Komm ausgeschlafen, es wird schweißtreibend 😅"),
        ]
    },
    "abo_pausieren_urlaub": {
        "intent": "pause",
        "agent": "ops",
        "confidence_range": (0.78, 0.92),
        "escalation_rate": 0.08,
        "turns": [
            ("user",      "Ich fahre nächsten Monat 3 Wochen in Urlaub. Kann ich mein Abo pausieren?"),
            ("assistant", "Hey {name}! Klar, Urlaubspause ist kein Problem 🌴 Schick mir kurz: Ab wann? Und bis wann ungefähr?"),
            ("user",      "Vom 15. bis zum 5. nächsten Monats"),
            ("assistant", "Alles klar! Ich leite das an unser Team weiter. Die Pause wird für den Zeitraum eingetragen und deine Laufzeit entsprechend verlängert. Du erhältst eine Bestätigung per E-Mail. ✅"),
            ("user",      "Super danke!"),
            ("assistant", "Gern! Erhol dich gut und komm fit zurück 💪"),
        ]
    },
    "abo_pausieren_verletzung": {
        "intent": "pause",
        "agent": "ops",
        "confidence_range": (0.75, 0.90),
        "escalation_rate": 0.10,
        "turns": [
            ("user",      "Ich hab mir den Knöchel verdreht und kann 4 Wochen nicht trainieren. Kann ich das Abo aussetzen?"),
            ("assistant", "Oh nein, das tut mir leid! 😔 Natürlich pausieren wir für dich. Hast du ein Attest vom Arzt? Falls ja, schick es einfach an info@getimpulse.de – dann geht's ganz unkompliziert. Ohne Attest können wir mind. 2 Wochen pausieren."),
            ("user",      "Ich bekomm das Attest nächste Woche"),
            ("assistant", "Kein Problem! Sobald du es hast, einfach mailen. Gute Besserung und meld dich wenn du wieder fit bist! 🤞"),
        ]
    },
    "kuendigung_retention": {
        "intent": "cancellation",
        "agent": "sales",
        "confidence_range": (0.70, 0.88),
        "escalation_rate": 0.25,
        "turns": [
            ("user",      "Ich möchte mein Mitgliedschaft kündigen"),
            ("assistant", "Hey {name}, das tut mir leid zu hören 😕 Darf ich fragen was der Grund ist? Manchmal können wir eine Lösung finden – Pause, Tarifwechsel oder ähnliches."),
            ("user",      "Ich ziehe nächsten Monat um und das Studio ist zu weit weg"),
            ("assistant", "Ah, das verstehe ich! Wenn du innerhalb Berlins bleibst – wir schauen gerne ob ein anderes Studio näher liegt. Falls nicht, können wir die Kündigung natürlich veranlassen. Was möchtest du?"),
            ("user",      "Ich glaub kündigen ist dann doch besser"),
            ("assistant", "Alright. Die Kündigung läuft über unser Büro – einfach eine kurze Mail an kuendigung@getimpulse.de mit deiner Mitgliedsnummer und dem gewünschten Datum. Wir wünschen dir alles Gute beim Umzug! 🏠"),
        ]
    },
    "kuendigung_eskaliert": {
        "intent": "cancellation",
        "agent": "sales",
        "confidence_range": (0.60, 0.80),
        "escalation_rate": 1.0,  # always escalated
        "turns": [
            ("user",      "Ich will kündigen und zwar sofort. Das ist jetzt das dritte Mal dass ich frage und nichts passiert"),
            ("assistant", "Hey {name}, es tut mir sehr leid, dass du schon mehrfach nachfragen musstest! Das ist absolut nicht ok. Ich leite dich jetzt sofort an einen Kollegen weiter der das direkt für dich löst."),
            ("user",      "Bitte macht das schnell"),
            ("assistant", "Selbstverständlich! Ein Mitarbeiter meldet sich innerhalb der nächsten 30 Minuten persönlich bei dir. Tut mir wirklich leid für die Unannehmlichkeiten. 🙏"),
        ]
    },
    "app_login_problem": {
        "intent": "app_issue",
        "agent": "persona",
        "confidence_range": (0.72, 0.88),
        "escalation_rate": 0.15,
        "turns": [
            ("user",      "Ich komm nicht mehr in die App rein, das Passwort wird nicht akzeptiert"),
            ("assistant", "Hi! Ärgerlich 😅 Versuch mal: Passwort zurücksetzen über 'Passwort vergessen' auf dem Login-Screen. Die Mail kommt meist innerhalb 2 Minuten. Hat das schon geklappt?"),
            ("user",      "Nein die Mail kommt nicht an"),
            ("assistant", "Schau kurz in deinen Spam-Ordner – manchmal landen die da. Falls immer noch nichts, könnte die E-Mail-Adresse im System leicht anders sein. Welche Adresse nutzt du normalerweise?"),
            ("user",      "{email}"),
            ("assistant", "Danke! Ich schau das für dich nach und meld mich gleich. Eine Sekunde... Die Adresse ist korrekt im System. Soll ich dir einen manuellen Reset-Link schicken?"),
            ("user",      "Ja bitte"),
            ("assistant", "Erledigt! Check deine Mails – der Link ist 24h gültig. Klappt's dann? 🤞"),
        ]
    },
    "trainingsberatung": {
        "intent": "training",
        "agent": "persona",
        "confidence_range": (0.75, 0.92),
        "escalation_rate": 0.05,
        "turns": [
            ("user",      "Ich bin Anfänger und weiß nicht womit ich anfangen soll"),
            ("assistant", "Hey {name}! Willkommen 🎉 Als Anfänger empfehle ich dir: Erstmal eine Einführungsstunde mit unserem PT-Team buchen – die zeigen dir die Geräte und erstellen einen Grundplan. Das ist inklusive und dauert ca. 45 Min. Interesse?"),
            ("user",      "Ja das klingt gut, wie buche ich das?"),
            ("assistant", "Einfach an der Rezeption fragen oder kurz mailen an training@getimpulse.de. Am besten unter der Woche Vormittag – da ist mehr Zeit und Ruhe. 💪"),
            ("user",      "Ok mach ich, danke!"),
            ("assistant", "Gern! Viel Spaß beim ersten Training – du machst das! 🔥"),
        ]
    },
    "trainingsberatung_gewicht": {
        "intent": "training",
        "agent": "persona",
        "confidence_range": (0.73, 0.90),
        "escalation_rate": 0.03,
        "turns": [
            ("user",      "Ich will abnehmen, welche Kurse empfehlt ihr?"),
            ("assistant", "Hey! Für Abnehmen super geeignet: HIIT (High Intensity), Spinning und Functional Training – die verbrennen richtig Kalorien 🔥 Kombiniert mit 2-3x Gerätetraining ist das ein guter Mix. Wie viel Zeit hast du pro Woche?"),
            ("user",      "Ca 3 Stunden verteilt über die Woche"),
            ("assistant", "Perfekt! Ich würde empfehlen: 2x Kurs (z.B. Spinning + HIIT) + 1x Gerätetraining. In 2-3 Monaten merkst du definitiv was. Willst du direkt einen Kurs buchen?"),
            ("user",      "Ja den Spinning Dienstag"),
            ("assistant", "Spinning Dienstag 19:00 – noch 4 Plätze frei. Eintragen? ✅"),
            ("user",      "Ja gerne"),
            ("assistant", "Done! Viel Erfolg auf dem Weg zum Ziel 💪🔥"),
        ]
    },
    "sauna_frage": {
        "intent": "sauna",
        "agent": "persona",
        "confidence_range": (0.85, 0.97),
        "escalation_rate": 0.01,
        "turns": [
            ("user",      "Ist die Sauna im Premium Abo inklusive?"),
            ("assistant", "Hey! Ja, Sauna ist beim Premium-Tarif vollständig inklusive 🧖 Beim Flex-Tarif kostet der Saunazugang 5€ pro Besuch. Die Sauna hat täglich geöffnet – Mo–Fr ab 07:00, Wochenende ab 08:30."),
            ("user",      "Alles klar danke"),
        ]
    },
    "handtuch_schliessfach": {
        "intent": "facilities",
        "agent": "persona",
        "confidence_range": (0.88, 0.98),
        "escalation_rate": 0.01,
        "turns": [
            ("user",      "Gibt es Handtücher bei euch oder soll ich eigene mitbringen?"),
            ("assistant", "Hey {name}! Handtücher kannst du dir kostenlos an der Rezeption ausleihen – einfach deinen Mitgliedsausweis zeigen 🏋️ Schließfächer gibt's gratis, Schloss bitte mitbringen oder für 2€ kaufen."),
            ("user",      "Super das ist praktisch"),
        ]
    },
    "personal_training": {
        "intent": "personal_training",
        "agent": "sales",
        "confidence_range": (0.78, 0.92),
        "escalation_rate": 0.08,
        "turns": [
            ("user",      "Was kostet Personal Training bei euch?"),
            ("assistant", "Hey! PT-Sessions bei uns:\n• Einzelstunde (60 Min): 65€\n• 5er Pack: 290€ (58€/Stunde)\n• 10er Pack: 550€ (55€/Stunde)\n\nAls Premium-Mitglied bekommst du 10% Rabatt. 💪 Interesse an einer Probestunde?"),
            ("user",      "Eine Probestunde gibt es?"),
            ("assistant", "Ja! Erstgespräch + 30-Min-Schnupperstunde kostenlos für alle Mitglieder 🎉 Soll ich einen Termin anfragen?"),
            ("user",      "Ja gerne, am liebsten nachmittags"),
            ("assistant", "Ich gebe das weiter – unser PT-Team meldet sich innerhalb 24h per Mail und schlägt Termine vor. ✅"),
        ]
    },
    "neues_mitglied_info": {
        "intent": "onboarding",
        "agent": "persona",
        "confidence_range": (0.83, 0.95),
        "escalation_rate": 0.03,
        "turns": [
            ("user",      "Hallo! Ich überlege Mitglied zu werden, was brauche ich zum Anmelden?"),
            ("assistant", "Hey, schön dass du zu uns kommen möchtest! 🎉 Für die Anmeldung brauchst du: Personalausweis oder Reisepass, IBAN für die Lastschrift, und du bist startklar! Online geht's auf getimpulse.de oder direkt bei uns vor Ort. Hast du noch Fragen?"),
            ("user",      "Gibt es eine Probetraining Möglichkeit?"),
            ("assistant", "Ja! Du kannst einen kostenlosen Probetrainingstag buchen – einfach Bescheid geben wann du kommen möchtest 😊 Danach entscheidest du in Ruhe."),
            ("user",      "Das klingt super, ich meld mich dann"),
            ("assistant", "Sehr gerne! Wir freuen uns auf dich 💪"),
        ]
    },
    "checkin_problem": {
        "intent": "check_in",
        "agent": "ops",
        "confidence_range": (0.75, 0.91),
        "escalation_rate": 0.12,
        "turns": [
            ("user",      "Der Scanner an der Tür hat meine Karte nicht erkannt"),
            ("assistant", "Hey {name}! Das klingt nach einem Kartenproblem 🤔 Kurze Diagnose: Hast du die Karte nah genug ran gehalten (ca. 2-3 cm)? Manchmal hilft auch einmal neu starten – Karte kurz wegholen und wieder rankommen."),
            ("user",      "Hab ich alles versucht, funktioniert nicht"),
            ("assistant", "Dann ist die Karte wahrscheinlich entmagnetisiert. Komm kurz zur Rezeption – die aktivieren dir eine neue in 2 Minuten. Tut mir leid für den Aufwand! 😅"),
        ]
    },
    "studentenrabatt": {
        "intent": "pricing",
        "agent": "persona",
        "confidence_range": (0.82, 0.94),
        "escalation_rate": 0.04,
        "turns": [
            ("user",      "Gibt es Studentenrabatt?"),
            ("assistant", "Hey! Ja, Studenten bekommen 20% auf unsere Tarife 🎓 Einfach den Studentenausweis bei Anmeldung zeigen oder per Mail an info@getimpulse.de schicken. Gilt für alle Abo-Laufzeiten."),
            ("user",      "Cool! Und wie lange ist das gültig?"),
            ("assistant", "Solange du immatrikuliert bist – du musst jährlich deinen aktuellen Studentenausweis vorzeigen. Ganz einfach! 📚"),
            ("user",      "Top danke"),
        ]
    },
    "feedback_positiv": {
        "intent": "feedback",
        "agent": "persona",
        "confidence_range": (0.90, 0.99),
        "escalation_rate": 0.00,
        "turns": [
            ("user",      "Ich wollte mal sagen dass das Studio wirklich super ist! Die Trainer sind toll"),
            ("assistant", "Wow, vielen Dank {name}! Das freut uns riesig zu hören 🙏🔥 Ich gebe das direkt ans Team weiter – so ein Feedback motiviert ungemein! Wir sehen uns beim nächsten Training 💪"),
            ("user",      "Gerne! Weiter so"),
        ]
    },
    "getraenke_nutrition": {
        "intent": "nutrition",
        "agent": "persona",
        "confidence_range": (0.82, 0.95),
        "escalation_rate": 0.02,
        "turns": [
            ("user",      "Gibt es bei euch Protein Shakes zu kaufen?"),
            ("assistant", "Hey! Ja, wir haben an der Rezeption: Protein Shakes (Whey & Plant-Based), Energy Drinks, Wasser und Sportgetränke. Preise zwischen 3-6€. 🥤 Auch Protein Riegel und kleinere Snacks."),
            ("user",      "Was für Shake-Sorten habt ihr?"),
            ("assistant", "Aktuell: Schoko, Vanilla, Erdbeere und Neutral (für DIY-Mixes). Täglich frisch gemixt oder als Ready-to-drink. Schau einfach vorbei – die Auswahl wechselt manchmal 😊"),
        ]
    },
}

# English templates for non-German speakers
TEMPLATES_EN = {
    "price_inquiry_en": {
        "intent": "pricing",
        "agent": "persona",
        "confidence_range": (0.85, 0.96),
        "escalation_rate": 0.03,
        "turns": [
            ("user",      "Hi! What are your membership prices?"),
            ("assistant", "Hey {name}! 💪 We have two options:\n• Flex: €29.90/month – cancel anytime\n• Premium: €39.90/month – 12-month contract, includes sauna, course priority & 10% PT discount\n\nWhich sounds better for you?"),
            ("user",      "What's included in the Premium?"),
            ("assistant", "Premium includes: all courses (priority booking), free sauna access, 10% off personal training, and locker without extra charge. Great value for regular gym-goers! 🔥"),
            ("user",      "I'll go with Premium then"),
            ("assistant", "Great choice! You can sign up online or just come by the studio. See you soon! ✅"),
        ]
    },
    "class_booking_en": {
        "intent": "booking",
        "agent": "ops",
        "confidence_range": (0.80, 0.94),
        "escalation_rate": 0.05,
        "turns": [
            ("user",      "Can I book a yoga class for this week?"),
            ("assistant", "Hi {name}! 🧘 We have yoga on:\n• Wednesday 6:30pm – 2 spots left\n• Friday 7:00am – 5 spots available\n• Saturday 10:00am – fully booked\n\nWhich works for you?"),
            ("user",      "Wednesday evening please!"),
            ("assistant", "Done! You're booked for Wednesday Yoga at 6:30pm. See you there 🙏"),
        ]
    },
    "pause_membership_en": {
        "intent": "pause",
        "agent": "ops",
        "confidence_range": (0.78, 0.92),
        "escalation_rate": 0.08,
        "turns": [
            ("user",      "I'm going on vacation for 3 weeks, can I pause my membership?"),
            ("assistant", "Of course {name}! Just let me know the dates and I'll pass it on to the team. Your contract will be extended by the pause period. 🌴"),
            ("user",      "From July 15 to August 5"),
            ("assistant", "Perfect, I've noted that. You'll get a confirmation email within 24h. Enjoy your vacation! ☀️"),
        ]
    },
}

# ── Member selection ──────────────────────────────────────────────────────────

# Members with phone (for WhatsApp/SMS)
MEMBERS_WITH_PHONE = [
    (1229490347, "Simone", "Schlaak",       "haartante@aol.com",                "017646630365",  "FEMALE", "de"),
    (1229490460, "Christian","Stein",       "christian.stein@freenet.de",        "015111552084",  "MALE",   "de"),
    (1229490469, "Arne",   "Fischer",       "arne.fischer@fischer-partner.de",   "01781364480",   "MALE",   "de"),
    (1229490573, "Christian","Schlaak",     "knaufsak@aol.com",                  "017646632429",  "MALE",   "de"),
    (1229490680, "Eric",   "Schulz",        "e.schulz84@gmx.de",                 "015901410500",  "MALE",   "de"),
    (1229491197, "Julia",  "Esser",         "julia@get-impulse.de",              "015116525107",  "FEMALE", "de"),
    (1229491198, "Hejer",  "Denguir",       "hejerdenguir@web.de",               "01713142087",   "FEMALE", "de"),
    (1229491313, "Andreas","Keil",          "andikeil@yahoo.de",                 "01797941499",   "MALE",   "de"),
    (1229491526, "Luccas", "Menezes",       "luccasmenezes@gmail.com",           "0176/76571374", "MALE",   "de"),
    (1229492044, "Luiza",  "De Souza",      "luiza177music@gmail.com",           "017629908755",  "FEMALE", "de"),
    (1229492159, "Mika",   "Moriyama",      "c.mika.moriyama@gmail.com",         "01638832244",   "FEMALE", "de"),
    (1229492252, "Jennifer","Hanley",       "jennifer-hanley@t-online.de",       "017620453753",  "FEMALE", "de"),
    (1229492464, "Apurva", "Dharmadhirari", "apurvad1304@gmail.com",             "015164446022",  "FEMALE", "de"),
    (1229492560, "Pat",    "Broilo",        "patriciabrm@gmail.com",             "017660811339",  "FEMALE", "de"),
    (1229492562, "Prasanna","Deshpande",    "me_prasanna@hotmail.com",           "015164446020",  "MALE",   "de"),
    (1229492685, "Gianna", "Mewes",         "giannamewes@gmx.de",                "015737154707",  "FEMALE", "de"),
    (1229492788, "Valentina","Shabani",     "valentina.shabani@gmx.de",          "017622673703",  "FEMALE", "de"),
    (1229492982, "Daniel", "Nitt",          "daniel.nitt@publycite.de",          "01607311319",   "MALE",   "de"),
    (1229492984, "Joanna", "Piaskowska",    "bazylissaa@gmail.com",              "01728615619",   "FEMALE", "de"),
    (1229493173, "Martina","Rozok",         "m@rozok.de",                        "01702355988",   "FEMALE", "de"),
    (1229493174, "Frank",  "Reichow",       "mail@frankreichow.de",              "01732322212",   "MALE",   "de"),
    (1229493301, "Yeliz",  "Önen",          "yelizk81@hotmail.de",               "01794983019",   "FEMALE", "de"),
    (1229493922, "Jan-Simon","Wolff",       "kontakt@jansimonwolff.de",          "017664665150",  "MALE",   "de"),
    (1229493929, "Mirja",  "Mittermaier",   "mirja.mittermaier@gmail.com",       "01734853714",   "FEMALE", "de"),
    (1229494020, "Franziska","Mietk",       "franziska.zehe@gmx.de",             "017643887824",  "FEMALE", "de"),
    (1229494023, "Daniela","Bartke",        "daniela.bartke@me.com",             "015234025730",  "FEMALE", "de"),
    (1229494344, "Jenya",  "Kaploun",       "kaploun.evgenia@gmail.com",         "017698666965",  "FEMALE", "de"),
    (1229494633, "Martin", "Claus",         "ma.claus@outlook.de",               "01628717996",   "MALE",   "de"),
    (1229494743, "Tobias", "Guenther",      "t.guenther1987@gmail.com",          "017640431696",  "MALE",   "de"),
    (1229494950, "Sandra", "Lukaczewski",   "slukaczewski@gmail.com",            "01732431400",   "FEMALE", "de"),
    (1229494956, "Jasper", "Jauch",         "jasper.jauch@icloud.com",           "01724063010",   "MALE",   "de"),
    (1229495052, "Elisa",  "Moriyama",      "beniko-chan@hotmail.de",             "01784034567",   "FEMALE", "de"),
    (1229495157, "Christin","Ulrich",       "christin.ulrich@gmx.de",            "017585801119",  "FEMALE", "de"),
    (1229495355, "Yanhua", "Zhou",          "yanhuazhou67@gmail.com",            "01745121653",   "FEMALE", "de"),
    (1229495464, "Felix",  "Kayser",        "felix@kayserlich.net",              "01629294015",   "MALE",   "de"),
    (1229495561, "Miguel", "Salas",         "miguel.salas-ramirez@charite.de",   "015232005131",  "MALE",   "de"),
    (1229495881, "Seda",   "Kavaklipinar",  "sedaberberoglu@hotmail.com",        "015167843305",  "FEMALE", "de"),
    (1229495981, "Arzu",   "Baba",          "arzu_baba@yahoo.de",                "017680301867",  "FEMALE", "de"),
    (1229496098, "Binsy",  "Mathew",        "b.mathew@hotmail.de",               "01621569419",   "FEMALE", "de"),
    (1229496293, "Anja",   "Barth",         "barth.anja@outlook.com",            "01722369090",   "FEMALE", "de"),
    (1229496294, "Szymon", "Koscielniak",   "contact@szymonkoscielniak.com",     "017697922563",  "MALE",   "de"),
    (1229496299, "Sevin",  "Acikalim",      "sevinacikalin1997@gmail.com",       "017632757585",  "FEMALE", "de"),
    (1229496512, "Evgeniya","Nedeva",       "samuila.nedeva@gmail.com",          "015737610064",  "FEMALE", "de"),
    (1229496617, "Duygu",  "Kaya",          "duyguates0205@gmail.com",           "017670664924",  "FEMALE", "de"),
    (1229496618, "Rukiye", "Alpbayrak",     "rukiye-oren@hotmail.de",            "01785355965",   "FEMALE", "de"),
    (1229496619, "Linda",  "Foerster",      "linda.foerster@posteo.de",          "01799355494",   "FEMALE", "de"),
    (1229496723, "Damien", "Frigewski",     "dfrigewski@gmail.com",              "01743095371",   "MALE",   "de"),
    (1229496836, "Kalojan","Christow",      "k.christow@gmail.com",              "01746393207",   "MALE",   "de"),
    (1229496930, "Michael","Brumbauer",     "msbrumbauer@aol.com",               "01723891472",   "MALE",   "de"),
    (1229496933, "Janine", "Döring",        "reimianzi@gmail.com",               "015901711924",  "FEMALE", "de"),
    (1229496936, "Olya",   "Pallade",       "olya.pallade@gmail.com",            "017626463019",  "FEMALE", "de"),
    (1229496937, "Michael","Klemund",       "m.klemund@me.com",                  "01715396359",   "MALE",   "de"),
    (1229496938, "Jessica","Patel",         "jessica.jameson@gmail.com",         "015125013807",  "FEMALE", "en"),
    (1229497040, "Tara",   "Marhun",        "taramaruhn@gmail.com",              "01773050824",   "FEMALE", "de"),
    (1229497043, "Tim",    "Dröscher",      "tim.droescher@gmail.com",           "015119442625",  "MALE",   "de"),
    (1229497044, "Carmen", "Parrino",       "carmenmparrino@web.de",             "01785197787",   "FEMALE", "de"),
    (1229497048, "Norman", "Kowalewski",    "refreenorman@yahoo.de",             "01716869099",   "MALE",   "de"),
    (1229497152, "Peter",  "Hirschfeld",    "p.hirschfeld@dentalwelten.de",      "016097984242",  "MALE",   "de"),
    (1229497156, "Emir",   "Arslan",        "emir.arslan@hotmail.com",           "01632248371",   "MALE",   "de"),
    (1229497255, "Nicole", "Rabert",        "nicole@rabert.de",                  "01736045864",   "FEMALE", "de"),
    (1229497362, "Annabell","Eichinger",    "annabell.eichinger@gmx.de",         "+491624264717", "FEMALE", "de"),
    (1229497369, "Marti",  "Fischer",       "martitomfischer@gmail.com",         "015140108115",  "MALE",   "de"),
    (1229497471, "Juliane","Ahrendt",       "juliane.ahrendt@web.de",            "017648883660",  "FEMALE", "de"),
    (1229497476, "Burak",  "Karakoca",      "kkocaburak@gmail.com",              "01629762263",   "MALE",   "de"),
    (1229497479, "Sruthi", "Sreekumar",     "sruthi.sreekumar0311@gmail.com",    "017662019309",  "FEMALE", "de"),
    (1229497661, "Faye",   "Günther",       "fayeo@web.de",                      "017630347669",  "FEMALE", "de"),
    (1229497664, "Annika", "Lübbers",       "annikalubbers@gmail.com",           "01622072502",   "FEMALE", "de"),
    (1229497761, "Robert", "von Steinau",   "robert.steinrueck@luther-lawfirm.com","015201621150","MALE",   "de"),
    (1229497762, "Lars",   "von Wiegen",    "sport-druck@gmx.de",                "017662400516",  "MALE",   "de"),
    (1229497861, "Martina","Hirschfeld",    "martinahirschfeld@icloud.com",      "016097984242",  "FEMALE", "de"),
    (1229497869, "Emilia", "Raschewski",    "emilia.raschewski@gmx.de",          "01759019814",   "FEMALE", "de"),
    (1229498191, "Rasha",  "Abdel Wahab",   "rasha.wahab@me.com",                "017627136106",  "FEMALE", "de"),
    (1229498605, "Anke",   "Chemnitz",      "anke.chemnitz75@gmail.com",         "01721898046",   "FEMALE", "de"),
    (1229498607, "Martin", "Kuipers",       "martin@co.kuipers-welt.de",         "01755800930",   "MALE",   "de"),
    (1229498736, "Diana",  "Passut",        "diana.passut@googlemail.com",       "01726667014",   "FEMALE", "de"),
    (1229498738, "Ellert", "Klotz",         "ellert.klotz@web.de",               "017640110033",  "MALE",   "de"),
    (1229498841, "Christian","Chmiel",      "christian.chmiel@gmx.de",           "01778116198",   "MALE",   "de"),
    (1229499070, "Lena",   "Chmiel",        "l.a.lauterbach@gmail.com",          "015161474962",  "FEMALE", "de"),
    (1229499182, "Filipe", "Gonzaga",       "fil.gmiranda@gmail.com",            "01704066800",   "MALE",   "de"),
    (1229499406, "Ines",   "Cumbrowski",    "ines.cumbrowski@gmx.de",            "01773415375",   "FEMALE", "de"),
    (1229499539, "Sebastian","Bosse",       "sebastian.bosse.online@gmail.com",  "015757809049",  "MALE",   "de"),
    (1229500161, "Christoph","Jochum",      "christoph.jochum@charite.de",       "01717944900",   "MALE",   "de"),
    (1229500284, "Viktor", "Angelov",       "negcrew@gmail.com",                 "017622916792",  "MALE",   "de"),
    (1229500948, "Daniela","Bache",         "dani.bache@gmail.com",              "01722965626",   "FEMALE", "de"),
    (1229501041, "Franz",  "Förster",       "franz.foerster@online.de",          "01623191994",   "MALE",   "de"),
    (1229501153, "Franziska","Berlin",      "berlin.franziska@outlook.de",       "017624953128",  "FEMALE", "de"),
    (1229501156, "Patrick","Russek",        "russek.patrick@gmail.com",          "01713107371",   "MALE",   "de"),
    (1229501252, "David",  "Göhler",        "davidgoertz.1@gmx.de",              "015222968951",  "MALE",   "de"),
    (1229501378, "Omar",   "Fergani",       "omar@1000kelvin.com",               "017661620473",  "MALE",   "de"),
    (1229501586, "Dawid",  "Piaskowski",    "googlarz@gmail.com",                "01739048003",   "MALE",   "en"),
    (1229501709, "Florian","Rockmeier",     "florian.rockmeier@gmx.de",          "01785317920",   "MALE",   "de"),
    (1229501815, "Sven",   "Vieler",        "s.vieler@vieler-group.de",          "01722841369",   "MALE",   "de"),
    (1229502581, "Sven",   "Voß",           "meinzeuch@web.de",                  "017666991615",  "MALE",   "de"),
    (1229502583, "Robin",  "Jung",          "robin.jung@hhl.de",                 "01608506095",   "MALE",   "de"),
    (1229502682, "Linda",  "Hesse",         "lindahesse@icloud.com",             "01726409031",   "FEMALE", "de"),
    (1229502683, "Tobias", "Hinz",          "tobi_hinz@yahoo.de",                "01636281470",   "MALE",   "de"),
    (1229502686, "Christiane","Schreitmüller","christiane@maui-entertainment.de","017623885848",  "FEMALE", "de"),
    (1229502815, "Baris",  "Özcelik",       "originius@gmail.com",               "017637577201",  "MALE",   "de"),
    (1229502935, "Yulia",  "Rudenko",       "yul.rudenko@gmail.com",             "015175012741",  "FEMALE", "de"),
    (1229503154, "Aldin",  "Hadzifejzovic", "aldinko@live.de",                   "01621856420",   "MALE",   "de"),
    (1229503368, "Bianca", "Horbach",       "horbach_bianca@icloud.com",         "01602211790",   "FEMALE", "de"),
    (1229503462, "Andre",  "Blanco",        "andremblanco@gmail.com",            "015255857376",  "MALE",   "de"),
    (1229503672, "Sara",   "Simicic",       "sara.simicic86@gmail.com",          "017676792843",  "FEMALE", "de"),
    (1232158618, "Emilien","Maree",         "emilien.maree@gmail.com",           "0032472077577", "MALE",   "fr"),
    (1232159040, "Fatemeh","Chegini",       "chegini@zib.de",                    "015510278670",  "FEMALE", "en"),
    (1232208212, "Peter",  "Smits",         "peter.smits@pietsmiet.de",          "01754155201",   "MALE",   "de"),
    (1232368600, "Hendrik","Holling",       "hendrik.holling@web.de",            "015111813800",  "MALE",   "de"),
    (1232561780, "Anna",   "von Kalm",      "annavkalm@gmail.com",               "015167009030",  "FEMALE", "de"),
    (1232638010, "Ernst",  "Salzmann",      "ErnstSalzmann@gmail.com",           "015732918664",  "MALE",   "de"),
    (1232668700, "Hanna",  "Khaurdinova",   "hanna.khaurdinova@gmx.de",          "015141345852",  "FEMALE", "de"),
    (1233066680, "Tessa",  "Bederke",       "tessa@bederke.com",                 "+491711162708", "FEMALE", "de"),
    (1233068650, "Michael","Müller",        "hallo@michaelmuellerfotografie.com","017624217472",  "MALE",   "de"),
    (1233337520, "Madhuri","Varikuti",      "madhuri.varikuti@gmail.com",        "017630307908",  "FEMALE", "de"),
    (1233439280, "Peter",  "Schrader",      "peterschrader95@gmail.com",         "015170535868",  "MALE",   "de"),
    (1233600290, "Selin",  "Kilic",         "sel.kilic@outlook.com",             "01735912753",   "FEMALE", "de"),
    (1233763040, "Alexandrine","Navarrete", "alexandrinenvrrt@gmail.com",        "017656998019",  "FEMALE", "fr"),
    (1234023730, "Martin", "Schmieder",     "martin.schmieder-lemke@icono.de",   "01736508979",   "MALE",   "de"),
    (1234726581, "Damla",  "Demirhan",      "damlademirhnn@gmail.com",           "01786763700",   "FEMALE", "de"),
    (1234797360, "Nicky",  "Stange",        "nickystange@gmail.com",             "01729901141",   "MALE",   "de"),
    (1234931180, "Taner",  "Savci",         "taner.sav@hotmail.com",             "017630303497",  "MALE",   "de"),
    (1234999430, "Benjamin","Barth",        "benjaminbarth.contact@gmail.com",   "017664680027",  "MALE",   "de"),
    (1235540720, "Vera",   "Braun",         "vera-melina.braun@hotmail.com",     "015734729747",  "FEMALE", "de"),
    (1235626880, "Georgia","Toepffer",      "gtoepffer@gmail.com",               "491738562870",  "FEMALE", "de"),
    (1235747930, "Julia",  "Knabe",         "julia.knabe@web.de",                "015208837840",  "FEMALE", "de"),
    (1236133770, "Doa",    "Al-Ahmad",      "doa.ammouri@gmail.com",             "017662742053",  "FEMALE", "de"),
    (1236154000, "Moffat", "Ngugi",         "ngugimoffat@gmail.com",             "016091319554",  "MALE",   "de"),
    (1236314890, "Sarah",  "Pietzsch",      "sarahpietzsch@gmx.de",              "+4915156170078","FEMALE", "de"),
    (1236407980, "Cathy",  "Albert",        "catherine.diana.albert@gmail.com",  "+4917647746534","FEMALE", "de"),
    (1236411230, "Marco",  "Müllner",       "mmuellner2510@gmail.com",           "0049162 2830183","MALE",  "de"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def pick_template(lang: str) -> tuple[str, dict]:
    if lang == "en":
        pool = {**TEMPLATES_EN}
        # mix in some German templates for code-switching (realistic for Berlin)
        if random.random() > 0.6:
            pool = {**TEMPLATES}
    else:
        pool = {**TEMPLATES}
    key = random.choice(list(pool.keys()))
    return key, pool[key]


def apply_template(turns: list[tuple], name: str, email: str) -> list[tuple]:
    result = []
    for role, text in turns:
        text = text.replace("{name}", name).replace("{email}", email)
        result.append((role, text))
    return result


def random_timestamp(base_date: datetime, spread_hours: int = 14) -> datetime:
    """Random timestamp within a day, weighted towards gym hours."""
    # Peak hours: 7-9 and 17-21
    hour_weights = [1, 0.5, 0.3, 0.2, 0.2, 0.5, 1.5, 3, 3.5, 2, 1.5, 1, 1, 1, 1, 1.5, 2, 2.5, 3.5, 4, 3, 2, 1.5, 1]
    hour = random.choices(range(24), weights=hour_weights)[0]
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return base_date.replace(hour=hour, minute=minute, second=second, tzinfo=timezone.utc)


def conversations_per_day(weekday: int) -> int:
    """Number of conversations per day by weekday (0=Mon, 6=Sun)."""
    base = {0: 10, 1: 8, 2: 8, 3: 8, 4: 7, 5: 6, 6: 4}[weekday]
    return max(1, base + random.randint(-2, 3))


def channel_for_member(member: tuple, prefer: str | None = None) -> tuple[str, str]:
    """Pick channel and construct user_id."""
    cid, first, last, email, phone, gender, lang = member
    channels = ["whatsapp", "whatsapp", "whatsapp", "telegram", "telegram", "email", "sms"]
    if prefer:
        channel = prefer
    else:
        channel = random.choice(channels)
    clean_phone = phone.replace("/", "").replace(" ", "").replace("-", "").strip()
    if channel == "whatsapp":
        uid = f"seed:wa_{clean_phone}" if clean_phone else f"seed:wa_{cid}"
    elif channel == "telegram":
        uid = f"seed:tg_{cid}"
    elif channel == "sms":
        uid = f"seed:sms_{clean_phone}" if clean_phone else f"seed:sms_{cid}"
    else:
        uid = f"seed:email_{email.replace('@','_at_').replace('.','_')}"
    return channel, uid


# ── Main seeding ──────────────────────────────────────────────────────────────

def _load_members_from_db(engine, tenant_id: int) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    customer_id,
                    COALESCE(NULLIF(first_name, ''), 'Member') AS first_name,
                    COALESCE(NULLIF(last_name, ''), 'User') AS last_name,
                    COALESCE(NULLIF(email, ''), CONCAT('member_', customer_id, '@example.com')) AS email,
                    COALESCE(NULLIF(phone_number, ''), '') AS phone_number,
                    COALESCE(NULLIF(gender, ''), 'UNKNOWN') AS gender,
                    COALESCE(NULLIF(preferred_language, ''), 'de') AS preferred_language
                FROM studio_members
                WHERE tenant_id = :tid
                ORDER BY member_since DESC NULLS LAST, created_at DESC
                """
            ),
            {"tid": tenant_id},
        ).fetchall()
    return [tuple(r) for r in rows]


def _seed_open_handoffs(user_ids: list[str], tenant_id: int, count: int) -> int:
    r = Redis.from_url(REDIS_URL, decode_responses=True)
    # Cleanup previous seed handoffs to keep sample size deterministic.
    for key in r.scan_iter(match="session:seed:*:human_mode"):
        r.delete(key)
    for key in r.scan_iter(match=f"t{tenant_id}:human_mode:seed:*"):
        r.delete(key)

    if count <= 0 or not user_ids:
        return 0
    sample = random.sample(user_ids, min(count, len(user_ids)))
    for uid in sample:
        # Current admin handoff view still reads legacy key pattern.
        r.setex(f"session:{uid}:human_mode", 60 * 60 * 24 * 7, "true")
        # Tenant-scoped key for runtime compatibility.
        r.setex(f"t{tenant_id}:human_mode:{uid}", 60 * 60 * 24 * 7, "true")
    return len(sample)


def seed(
    *,
    tenant_id: int,
    days: int,
    target_sessions: int,
    reset: bool,
    append: bool,
    campaign: str,
    open_handoffs: int,
    escalation_multiplier: float,
) -> None:
    random.seed(42)
    engine = create_engine(DATABASE_URL)
    members = _load_members_from_db(engine, tenant_id)
    if len(members) < 20:
        print(f"WARNING: Only {len(members)} members found in DB for tenant {tenant_id}. Falling back to bundled sample.")
        members = MEMBERS_WITH_PHONE
    print(f"Using {len(members)} members for tenant {tenant_id}.")

    if reset:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT COUNT(*) FROM chat_sessions WHERE tenant_id = :tid"),
                {"tid": tenant_id},
            ).scalar()
            print(f"Existing sessions for tenant {tenant_id}: {existing}")
            if existing and existing > 0:
                print(f"Clearing existing chat sessions/messages for tenant {tenant_id}...")
                conn.execute(text("DELETE FROM chat_messages WHERE tenant_id = :tid"), {"tid": tenant_id})
                conn.execute(text("DELETE FROM chat_sessions WHERE tenant_id = :tid"), {"tid": tenant_id})
                print("Cleared.")
    elif not append:
        # Keep real traffic untouched and only refresh previous seeded artifacts.
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM chat_messages WHERE tenant_id = :tid AND session_id LIKE 'seed:%'"),
                {"tid": tenant_id},
            )
            conn.execute(
                text("DELETE FROM chat_sessions WHERE tenant_id = :tid AND user_id LIKE 'seed:%'"),
                {"tid": tenant_id},
            )

    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=max(1, days))

    sessions_data = []
    messages_data = []
    session_count = 0
    message_count = 0

    # Track which member/channel combos we've used to avoid exact duplicates
    used_uid_dates: set[str] = set()

    span_days = max(1, (now.date() - start_date.date()).days + 1)
    base_per_day = max(2, target_sessions // span_days)
    current_date = start_date
    while current_date <= now:
        weekday = current_date.weekday()
        n_convos = max(conversations_per_day(weekday), base_per_day + random.randint(-2, 3))

        # Slightly increase volume for last 30 days (growth trend)
        days_ago = (now - current_date).days
        if days_ago < 30:
            n_convos = int(n_convos * 1.3)
        elif days_ago < 60:
            n_convos = int(n_convos * 1.15)

        members_today = random.sample(members, min(n_convos, len(members)))

        for member in members_today:
            cid, first, last, email, phone, gender, lang = member

            # Pick channel (some members have preferred channels)
            prefer = None
            if hash(cid) % 3 == 0:
                prefer = "telegram"
            elif hash(cid) % 5 == 0:
                prefer = "email"
            channel, uid = channel_for_member(member, prefer)
            # Treat each day as a separate support thread for richer analytics samples.
            uid = f"{uid}:{campaign}:{current_date.strftime('%Y%m%d')}"

            # Avoid same member on same channel on same day (but allow repeats across days)
            uid_date_key = f"{uid}_{current_date.strftime('%Y-%m-%d')}"
            if uid_date_key in used_uid_dates:
                uid = f"{uid}_{random.randint(1000,9999)}"  # make unique
            used_uid_dates.add(uid_date_key)

            tpl_key, tpl = pick_template(lang)
            turns = apply_template(tpl["turns"], first, email)
            escalated = random.random() < min(0.9, tpl["escalation_rate"] * max(0.1, escalation_multiplier))

            # Session timestamp
            created_at = random_timestamp(current_date)
            last_message_at = created_at

            # Build session
            display_name = f"{first} {last}"
            clean_phone = phone.replace("/", "").replace(" ", "").strip()

            session = {
                "user_id": uid,
                "tenant_id": tenant_id,
                "platform": channel,
                "created_at": created_at,
                "last_message_at": created_at,
                "is_active": False,
                "user_name": display_name,
                "phone_number": clean_phone if channel in ("whatsapp", "sms") else None,
                "email": email if channel == "email" else None,
                "member_id": str(cid),
            }

            # Build messages
            msgs = []
            turn_ts = created_at
            confidence = round(random.uniform(*tpl["confidence_range"]), 3)
            intent = tpl["intent"]
            agent = tpl["agent"]

            for i, (role, content) in enumerate(turns):
                turn_ts = turn_ts + timedelta(seconds=random.randint(15, 180))
                is_last = i == len(turns) - 1

                meta: dict = {
                    "channel": channel,
                    "member_id": str(cid),
                    "intent": intent,
                }
                if role == "assistant":
                    meta["agent"] = agent
                    meta["confidence"] = confidence
                    if is_last and escalated:
                        meta["escalated"] = True
                        meta["handoff"] = True

                msgs.append({
                    "session_id": uid,
                    "tenant_id": tenant_id,
                    "role": role,
                    "content": content,
                    "timestamp": turn_ts,
                    "metadata_json": json.dumps(meta, ensure_ascii=False),
                })

            session["last_message_at"] = turn_ts
            sessions_data.append(session)
            messages_data.extend(msgs)
            session_count += 1
            message_count += len(msgs)

        current_date += timedelta(days=1)

    print(f"\nGenerated: {session_count} sessions, {message_count} messages")
    print("Inserting into database...")

    # Insert in batches
    with engine.begin() as conn:
        BATCH = 200
        for i in range(0, len(sessions_data), BATCH):
            batch = sessions_data[i:i+BATCH]
            conn.execute(text("""
                INSERT INTO chat_sessions
                    (user_id, tenant_id, platform, created_at, last_message_at,
                     is_active, user_name, phone_number, email, member_id)
                VALUES
                    (:user_id, :tenant_id, :platform, :created_at, :last_message_at,
                     :is_active, :user_name, :phone_number, :email, :member_id)
                ON CONFLICT DO NOTHING
            """), batch)

        for i in range(0, len(messages_data), BATCH):
            batch = messages_data[i:i+BATCH]
            conn.execute(text("""
                INSERT INTO chat_messages
                    (session_id, tenant_id, role, content, timestamp, metadata_json)
                VALUES
                    (:session_id, :tenant_id, :role, :content, :timestamp, :metadata_json)
            """), batch)

    # Verify
    with engine.connect() as conn:
        s_count = conn.execute(text(
            "SELECT COUNT(*) FROM chat_sessions WHERE tenant_id = :tid"
        ), {"tid": tenant_id}).scalar()
        m_count = conn.execute(text(
            "SELECT COUNT(*) FROM chat_messages WHERE tenant_id = :tid"
        ), {"tid": tenant_id}).scalar()
        channel_dist = conn.execute(text(
            "SELECT platform, COUNT(*) FROM chat_sessions WHERE tenant_id = :tid GROUP BY platform ORDER BY COUNT(*) DESC"
        ), {"tid": tenant_id}).fetchall()

        print(f"\n✅ Seeded: {s_count} sessions, {m_count} messages")
        print("\nChannel distribution:")
        for row in channel_dist:
            print(f"  {row[0]:12s}: {row[1]} sessions")

        escalated_session_ids = [
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT session_id, MAX(timestamp) AS last_ts
                    FROM chat_messages
                    WHERE tenant_id = :tid
                      AND role = 'assistant'
                      AND session_id LIKE 'seed:%'
                      AND metadata_json LIKE '%\"escalated\": true%'
                    GROUP BY session_id
                    ORDER BY last_ts DESC
                    LIMIT 500
                    """
                ),
                {"tid": tenant_id},
            ).fetchall()
        ]

    handoffs_seeded = _seed_open_handoffs(escalated_session_ids, tenant_id=tenant_id, count=open_handoffs)
    print(f"\n🚨 Active handoffs seeded: {handoffs_seeded}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed realistic chat traffic and escalations.")
    parser.add_argument("--tenant-id", type=int, default=TENANT_ID, help="Tenant ID (default: 6)")
    parser.add_argument("--days", type=int, default=90, help="Lookback range in days (default: 90)")
    parser.add_argument("--target-sessions", type=int, default=900, help="Approximate session count target (default: 900)")
    parser.add_argument("--open-handoffs", type=int, default=24, help="How many active handoffs to keep open (default: 24)")
    parser.add_argument("--escalation-multiplier", type=float, default=1.0, help="Scale template escalation probability (default: 1.0)")
    parser.add_argument("--campaign", type=str, default="base", help="Campaign label for session IDs (default: base)")
    parser.add_argument("--reset", action="store_true", help="Delete existing tenant chat_sessions/chat_messages before seeding")
    parser.add_argument("--append", action="store_true", help="Append campaign data instead of replacing prior seed data")
    args = parser.parse_args()

    seed(
        tenant_id=args.tenant_id,
        days=args.days,
        target_sessions=args.target_sessions,
        reset=args.reset,
        append=args.append,
        campaign=args.campaign.strip().replace(":", "-") or "base",
        open_handoffs=args.open_handoffs,
        escalation_multiplier=args.escalation_multiplier,
    )
