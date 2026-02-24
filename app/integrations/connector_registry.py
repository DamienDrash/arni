"""ARIIA – Connector Registry.

Central registry for all integration connectors.
Each connector defines its metadata, required fields, category,
and inline setup documentation for the frontend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConnectorCategory(str, Enum):
    MESSAGING = "messaging"
    MEMBERS = "members"
    EMAIL = "email"
    VOICE = "voice"
    CRM = "crm"
    BILLING = "billing"


class FieldType(str, Enum):
    TEXT = "text"
    PASSWORD = "password"
    URL = "url"
    SELECT = "select"
    TOGGLE = "toggle"
    READONLY = "readonly"


@dataclass
class ConnectorField:
    """A single configuration field for a connector."""
    key: str
    label: str
    field_type: FieldType = FieldType.TEXT
    placeholder: str = ""
    hint: str = ""
    required: bool = True
    options: list[dict[str, str]] | None = None  # For SELECT type
    default: str = ""
    sensitive: bool = False  # Will be masked in GET responses
    setting_key: str = ""  # DB setting key (auto-derived if empty)
    env_fallback: str | None = None  # Env var fallback name


@dataclass
class SetupStep:
    """A single step in the setup documentation."""
    title: str
    description: str
    url: str = ""  # Optional link to open
    image_hint: str = ""  # Description of what screenshot would show
    warning: str = ""  # Optional warning text


@dataclass
class ConnectorDefinition:
    """Full definition of an integration connector."""
    id: str
    name: str
    description: str
    category: ConnectorCategory
    icon: str  # Emoji or icon identifier
    color: str  # Brand color hex
    fields: list[ConnectorField]
    setup_steps: list[SetupStep]
    supports_test: bool = True
    supports_sync: bool = False
    webhook_path: str = ""  # e.g. /webhook/whatsapp/{tenant_slug}
    docs_url: str = ""  # Official documentation URL
    is_beta: bool = False
    prerequisites: list[str] = field(default_factory=list)

    def to_dict(self, include_docs: bool = False) -> dict[str, Any]:
        """Serialize for API response."""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "icon": self.icon,
            "color": self.color,
            "supports_test": self.supports_test,
            "supports_sync": self.supports_sync,
            "webhook_path": self.webhook_path,
            "docs_url": self.docs_url,
            "is_beta": self.is_beta,
            "prerequisites": self.prerequisites,
            "fields": [
                {
                    "key": f.key,
                    "label": f.label,
                    "type": f.field_type.value,
                    "placeholder": f.placeholder,
                    "hint": f.hint,
                    "required": f.required,
                    "options": f.options,
                    "default": f.default,
                    "sensitive": f.sensitive,
                }
                for f in self.fields
            ],
        }
        if include_docs:
            result["setup_steps"] = [
                {
                    "title": s.title,
                    "description": s.description,
                    "url": s.url,
                    "image_hint": s.image_hint,
                    "warning": s.warning,
                }
                for s in self.setup_steps
            ]
        return result


# ─────────────────────────────────────────────────────────
# CONNECTOR DEFINITIONS
# ─────────────────────────────────────────────────────────

TELEGRAM = ConnectorDefinition(
    id="telegram",
    name="Telegram",
    description="Telegram Bot-Anbindung für Kundenkommunikation via Telegram Messenger.",
    category=ConnectorCategory.MESSAGING,
    icon="TG",
    color="#0088CC",
    webhook_path="/webhook/telegram/{tenant_slug}",
    docs_url="https://core.telegram.org/bots/api",
    fields=[
        ConnectorField(
            key="bot_token",
            label="Bot Token",
            field_type=FieldType.PASSWORD,
            placeholder="1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            hint="Das Token erhältst du vom BotFather in Telegram.",
            sensitive=True,
            setting_key="telegram_bot_token",
        ),
        ConnectorField(
            key="admin_chat_id",
            label="Admin Chat ID",
            placeholder="-100123456789",
            hint="Die Chat-ID deiner Admin-Gruppe oder deines persönlichen Chats.",
            required=False,
            setting_key="telegram_admin_chat_id",
        ),
        ConnectorField(
            key="webhook_secret",
            label="Webhook Secret",
            field_type=FieldType.PASSWORD,
            placeholder="mein-geheimes-webhook-token",
            hint="Optionaler Secret-Token zur Absicherung des Webhooks.",
            required=False,
            sensitive=True,
            setting_key="telegram_webhook_secret",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="BotFather öffnen",
            description="Öffne Telegram und suche nach @BotFather. Starte einen Chat mit ihm.",
            url="https://t.me/BotFather",
        ),
        SetupStep(
            title="Neuen Bot erstellen",
            description="Sende den Befehl /newbot an den BotFather. Er wird dich nach einem Namen und einem Benutzernamen für deinen Bot fragen. Der Benutzername muss auf 'bot' enden (z.B. 'MeinStudioBot').",
        ),
        SetupStep(
            title="Bot Token kopieren",
            description="Nach der Erstellung erhältst du ein Token im Format '1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11'. Kopiere dieses Token und füge es oben im Feld 'Bot Token' ein.",
            warning="Teile dieses Token niemals öffentlich! Jeder mit dem Token kann deinen Bot steuern.",
        ),
        SetupStep(
            title="Admin Chat ID ermitteln",
            description="Um die Chat-ID zu finden: Sende eine Nachricht an deinen Bot, dann öffne https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates im Browser. Die 'chat.id' in der Antwort ist deine Chat-ID.",
            url="https://api.telegram.org/bot{bot_token}/getUpdates",
        ),
        SetupStep(
            title="Webhook einrichten",
            description="ARIIA richtet den Webhook automatisch ein. Die Webhook-URL lautet: {base_url}/webhook/telegram/{tenant_slug}. Stelle sicher, dass dein Server öffentlich erreichbar ist.",
        ),
        SetupStep(
            title="Verbindung testen",
            description="Klicke auf 'Verbindung testen', um zu prüfen, ob der Bot erreichbar ist. Bei Erfolg wird der Bot-Benutzername angezeigt.",
        ),
    ],
)

WHATSAPP = ConnectorDefinition(
    id="whatsapp",
    name="WhatsApp",
    description="WhatsApp Business-Anbindung über Meta Cloud API oder QR-Code-Bridge.",
    category=ConnectorCategory.MESSAGING,
    icon="WA",
    color="#25D366",
    webhook_path="/webhook/whatsapp/{tenant_slug}",
    docs_url="https://developers.facebook.com/docs/whatsapp/cloud-api",
    fields=[
        ConnectorField(
            key="mode",
            label="Anschluss-Modus",
            field_type=FieldType.SELECT,
            options=[
                {"value": "qr", "label": "QR-Code / WhatsApp Web (Bridge)"},
                {"value": "meta", "label": "Meta Business API (Cloud)"},
            ],
            default="qr",
            hint="QR-Modus: Einfach per QR-Code verbinden. Meta API: Für Business-Accounts mit offizieller API.",
            setting_key="whatsapp_mode",
        ),
        ConnectorField(
            key="meta_phone_number_id",
            label="Phone Number ID",
            placeholder="123456789012345",
            hint="Die Phone Number ID aus dem Meta Developer Dashboard.",
            required=False,
            setting_key="meta_phone_number_id",
        ),
        ConnectorField(
            key="meta_verify_token",
            label="Verify Token",
            field_type=FieldType.PASSWORD,
            placeholder="mein-verify-token",
            hint="Frei wählbarer Token für die Webhook-Verifizierung.",
            required=False,
            sensitive=True,
            setting_key="meta_verify_token",
        ),
        ConnectorField(
            key="meta_access_token",
            label="Access Token",
            field_type=FieldType.PASSWORD,
            placeholder="EAAxxxxxxx...",
            hint="Permanenter System User Token aus dem Meta Business Manager.",
            required=False,
            sensitive=True,
            setting_key="meta_access_token",
        ),
        ConnectorField(
            key="meta_app_secret",
            label="App Secret",
            field_type=FieldType.PASSWORD,
            placeholder="App Secret aus dem Meta Developer Dashboard",
            hint="Wird zur Signaturprüfung eingehender Webhooks verwendet.",
            required=False,
            sensitive=True,
            setting_key="meta_app_secret",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="Meta Developer Account erstellen",
            description="Erstelle einen Account auf developers.facebook.com und verifiziere dein Unternehmen im Meta Business Manager.",
            url="https://developers.facebook.com/",
        ),
        SetupStep(
            title="WhatsApp Business App erstellen",
            description="Gehe zu 'Meine Apps' → 'App erstellen' → Wähle 'Business' als App-Typ → Wähle 'WhatsApp' als Use Case.",
            url="https://developers.facebook.com/apps/",
        ),
        SetupStep(
            title="Telefonnummer hinzufügen",
            description="Im WhatsApp-Setup deiner App: Füge eine Telefonnummer hinzu oder verwende die Test-Nummer. Notiere die 'Phone Number ID' und trage sie oben ein.",
        ),
        SetupStep(
            title="Permanenten Token erstellen",
            description="Gehe zu Business Settings → System Users → Erstelle einen System User mit Admin-Rechten → Generiere einen Token mit den Berechtigungen 'whatsapp_business_messaging' und 'whatsapp_business_management'.",
            url="https://business.facebook.com/settings/system-users",
            warning="Verwende NICHT den temporären Token aus dem Dashboard — dieser läuft nach 24h ab!",
        ),
        SetupStep(
            title="Webhook konfigurieren",
            description="Im Meta Developer Dashboard → WhatsApp → Configuration → Webhook URL: {base_url}/webhook/whatsapp/{tenant_slug}. Verify Token: Trage denselben Token ein, den du oben als 'Verify Token' gesetzt hast. Abonniere die Felder: 'messages'.",
        ),
        SetupStep(
            title="App Secret kopieren",
            description="Dashboard → App Settings → Basic → App Secret kopieren und oben eintragen. Damit werden eingehende Webhooks kryptographisch verifiziert.",
        ),
    ],
)

WHATSAPP_QR = ConnectorDefinition(
    id="whatsapp_qr",
    name="WhatsApp (QR-Modus)",
    description="Schnelle WhatsApp-Verbindung über QR-Code — wie WhatsApp Web.",
    category=ConnectorCategory.MESSAGING,
    icon="QR",
    color="#25D366",
    supports_test=True,
    fields=[],
    setup_steps=[
        SetupStep(
            title="QR-Code anzeigen",
            description="Klicke auf 'QR-Code anzeigen' um den Verbindungs-QR-Code zu generieren.",
        ),
        SetupStep(
            title="WhatsApp öffnen",
            description="Öffne WhatsApp auf deinem Smartphone → Menü (drei Punkte) oder Einstellungen → 'Verknüpfte Geräte' → 'Gerät hinzufügen'.",
        ),
        SetupStep(
            title="QR-Code scannen",
            description="Scanne den angezeigten QR-Code mit deinem Smartphone. Die Verbindung wird automatisch hergestellt.",
            warning="Das Smartphone muss mit dem Internet verbunden bleiben, damit die Bridge funktioniert.",
        ),
    ],
)

INSTAGRAM = ConnectorDefinition(
    id="instagram",
    name="Instagram DM",
    description="Instagram Direct Messages über die Meta Graph API empfangen und beantworten.",
    category=ConnectorCategory.MESSAGING,
    icon="IG",
    color="#E4405F",
    webhook_path="/webhook/instagram/{tenant_slug}",
    docs_url="https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging",
    is_beta=True,
    prerequisites=["Meta Business Account", "Instagram Professional Account (Business oder Creator)"],
    fields=[
        ConnectorField(
            key="instagram_page_id",
            label="Instagram Page ID",
            placeholder="17841400000000000",
            hint="Die Instagram Business Account ID, verknüpft mit deiner Facebook-Seite.",
            setting_key="instagram_page_id",
        ),
        ConnectorField(
            key="instagram_access_token",
            label="Page Access Token",
            field_type=FieldType.PASSWORD,
            placeholder="EAAxxxxxxx...",
            hint="Langlebiger Page Access Token mit instagram_manage_messages Berechtigung.",
            sensitive=True,
            setting_key="instagram_access_token",
        ),
        ConnectorField(
            key="instagram_app_secret",
            label="App Secret",
            field_type=FieldType.PASSWORD,
            placeholder="App Secret für Webhook-Signaturprüfung",
            required=False,
            sensitive=True,
            setting_key="instagram_app_secret",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="Instagram Business Account einrichten",
            description="Stelle sicher, dass dein Instagram-Account ein 'Professional Account' (Business oder Creator) ist. Gehe in der Instagram-App zu Einstellungen → Konto → Zu professionellem Konto wechseln.",
        ),
        SetupStep(
            title="Facebook-Seite verknüpfen",
            description="Verknüpfe deinen Instagram Business Account mit einer Facebook-Seite. Gehe zu Instagram → Einstellungen → Konto → Verknüpfte Konten → Facebook.",
        ),
        SetupStep(
            title="Meta Developer App konfigurieren",
            description="Verwende dieselbe Meta App wie für WhatsApp (oder erstelle eine neue). Füge das Produkt 'Instagram' hinzu. Gehe zu Instagram → Basic Display → Konfiguriere die OAuth-Redirect-URI.",
            url="https://developers.facebook.com/apps/",
        ),
        SetupStep(
            title="Berechtigungen anfordern",
            description="Deine App benötigt die Berechtigungen: 'instagram_manage_messages', 'pages_manage_metadata'. Für den Live-Modus muss die App von Meta geprüft werden (App Review).",
            warning="Im Entwicklungsmodus funktioniert die API nur mit Testnutzern. Für den Produktivbetrieb ist ein App Review erforderlich.",
        ),
        SetupStep(
            title="Page Access Token generieren",
            description="Im Graph API Explorer: Wähle deine App → Wähle 'Page Access Token' → Wähle die verknüpfte Facebook-Seite → Generiere den Token. Wandle ihn in einen langlebigen Token um.",
            url="https://developers.facebook.com/tools/explorer/",
        ),
        SetupStep(
            title="Webhook einrichten",
            description="Meta Developer Dashboard → Instagram → Webhooks → Callback URL: {base_url}/webhook/instagram/{tenant_slug}. Abonniere das Feld 'messages'.",
        ),
    ],
)

FACEBOOK_MESSENGER = ConnectorDefinition(
    id="facebook_messenger",
    name="Facebook Messenger",
    description="Facebook Messenger-Nachrichten über die Meta Send/Receive API empfangen und beantworten.",
    category=ConnectorCategory.MESSAGING,
    icon="FB",
    color="#0084FF",
    webhook_path="/webhook/facebook/{tenant_slug}",
    docs_url="https://developers.facebook.com/docs/messenger-platform",
    is_beta=True,
    prerequisites=["Meta Business Account", "Facebook-Seite"],
    fields=[
        ConnectorField(
            key="fb_page_id",
            label="Facebook Page ID",
            placeholder="123456789012345",
            hint="Die ID deiner Facebook-Seite (zu finden unter Seiteneinstellungen → Allgemein).",
            setting_key="fb_page_id",
        ),
        ConnectorField(
            key="fb_page_access_token",
            label="Page Access Token",
            field_type=FieldType.PASSWORD,
            placeholder="EAAxxxxxxx...",
            hint="Langlebiger Page Access Token mit pages_messaging Berechtigung.",
            sensitive=True,
            setting_key="fb_page_access_token",
        ),
        ConnectorField(
            key="fb_verify_token",
            label="Verify Token",
            field_type=FieldType.PASSWORD,
            placeholder="mein-verify-token",
            hint="Frei wählbarer Token für die Webhook-Verifizierung.",
            required=False,
            sensitive=True,
            setting_key="fb_verify_token",
        ),
        ConnectorField(
            key="fb_app_secret",
            label="App Secret",
            field_type=FieldType.PASSWORD,
            placeholder="App Secret für Signaturprüfung",
            required=False,
            sensitive=True,
            setting_key="fb_app_secret",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="Facebook-Seite erstellen",
            description="Falls noch nicht vorhanden: Erstelle eine Facebook-Seite für dein Unternehmen unter facebook.com/pages/create.",
            url="https://www.facebook.com/pages/create",
        ),
        SetupStep(
            title="Meta Developer App erstellen",
            description="Gehe zu developers.facebook.com → 'Meine Apps' → 'App erstellen' → Wähle 'Business' → Füge das Produkt 'Messenger' hinzu.",
            url="https://developers.facebook.com/apps/",
        ),
        SetupStep(
            title="Seite mit App verknüpfen",
            description="Im Messenger-Setup deiner App: Klicke auf 'Seiten hinzufügen oder entfernen' und wähle deine Facebook-Seite aus. Generiere einen Page Access Token.",
        ),
        SetupStep(
            title="Berechtigungen konfigurieren",
            description="Deine App benötigt: 'pages_messaging', 'pages_manage_metadata'. Für den Live-Modus ist ein App Review erforderlich.",
            warning="Im Entwicklungsmodus können nur Seiten-Admins und Testnutzer Nachrichten senden.",
        ),
        SetupStep(
            title="Webhook einrichten",
            description="Messenger → Settings → Webhooks → Callback URL: {base_url}/webhook/facebook/{tenant_slug}. Verify Token: Derselbe wie oben. Abonniere: 'messages', 'messaging_postbacks'.",
        ),
        SetupStep(
            title="Langlebigen Token erstellen",
            description="Der Standard-Token läuft nach 60 Tagen ab. Erstelle einen System User im Business Manager und generiere einen permanenten Token.",
            url="https://business.facebook.com/settings/system-users",
        ),
    ],
)

GOOGLE_BUSINESS = ConnectorDefinition(
    id="google_business",
    name="Google Business Messages",
    description="Kundennachrichten über Google Maps und Google Suche empfangen und beantworten.",
    category=ConnectorCategory.MESSAGING,
    icon="GB",
    color="#4285F4",
    webhook_path="/webhook/google-business/{tenant_slug}",
    docs_url="https://developers.google.com/business-communications/business-messages",
    is_beta=True,
    prerequisites=["Google Business Profile", "Google Cloud Projekt"],
    fields=[
        ConnectorField(
            key="gbm_agent_id",
            label="Agent ID",
            placeholder="brands/xxxxx/agents/xxxxx",
            hint="Die Agent-ID aus der Business Communications Console.",
            setting_key="gbm_agent_id",
        ),
        ConnectorField(
            key="gbm_service_account_json",
            label="Service Account JSON",
            field_type=FieldType.PASSWORD,
            placeholder='{"type": "service_account", ...}',
            hint="Der vollständige JSON-Inhalt des Google Cloud Service Account Keys.",
            sensitive=True,
            setting_key="gbm_service_account_json",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="Google Business Profile verifizieren",
            description="Stelle sicher, dass dein Unternehmen ein verifiziertes Google Business Profile hat. Gehe zu business.google.com und verifiziere deinen Standort.",
            url="https://business.google.com/",
        ),
        SetupStep(
            title="Business Communications registrieren",
            description="Registriere dich als Partner in der Google Business Communications Console. Erstelle einen Agent für dein Unternehmen.",
            url="https://business-communications.cloud.google.com/console/",
        ),
        SetupStep(
            title="Google Cloud Projekt einrichten",
            description="Erstelle ein Google Cloud Projekt und aktiviere die 'Business Messages API'. Erstelle einen Service Account und lade den JSON-Key herunter.",
            url="https://console.cloud.google.com/",
        ),
        SetupStep(
            title="Webhook konfigurieren",
            description="In der Business Communications Console → Agent → Integration → Webhook URL: {base_url}/webhook/google-business/{tenant_slug}.",
        ),
        SetupStep(
            title="Agent verifizieren und launchen",
            description="Teste den Agent über die Business Messages Test-App. Nach erfolgreichem Test: Beantrage den Launch über die Console.",
            warning="Der Launch-Prozess kann mehrere Tage dauern und erfordert eine Prüfung durch Google.",
        ),
    ],
)

SMTP_EMAIL = ConnectorDefinition(
    id="smtp",
    name="SMTP / E-Mail Versand",
    description="E-Mail-Versand für Verifizierungscodes, Benachrichtigungen und Systemmail.",
    category=ConnectorCategory.EMAIL,
    icon="EM",
    color="#EA4335",
    docs_url="https://support.google.com/a/answer/176600",
    fields=[
        ConnectorField(
            key="host",
            label="SMTP Host",
            placeholder="smtp.gmail.com",
            hint="Der SMTP-Server deines E-Mail-Providers.",
            setting_key="smtp_host",
        ),
        ConnectorField(
            key="port",
            label="SMTP Port",
            placeholder="587",
            hint="Standard: 587 (STARTTLS) oder 465 (SSL).",
            default="587",
            setting_key="smtp_port",
        ),
        ConnectorField(
            key="username",
            label="Benutzername",
            placeholder="noreply@mein-studio.de",
            hint="Meist die vollständige E-Mail-Adresse.",
            sensitive=True,
            setting_key="smtp_username",
        ),
        ConnectorField(
            key="password",
            label="Passwort",
            field_type=FieldType.PASSWORD,
            placeholder="App-Passwort oder SMTP-Passwort",
            hint="Bei Gmail: Verwende ein App-Passwort (nicht dein normales Passwort).",
            sensitive=True,
            setting_key="smtp_password",
        ),
        ConnectorField(
            key="from_email",
            label="Absender-E-Mail",
            placeholder="noreply@mein-studio.de",
            setting_key="smtp_from_email",
        ),
        ConnectorField(
            key="from_name",
            label="Absender-Name",
            placeholder="Mein Studio",
            required=False,
            setting_key="smtp_from_name",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="E-Mail-Provider wählen",
            description="Du kannst jeden SMTP-fähigen E-Mail-Provider verwenden: Gmail, Outlook/Microsoft 365, Amazon SES, Mailgun, oder den SMTP deines Webhosters.",
        ),
        SetupStep(
            title="Gmail: App-Passwort erstellen",
            description="Für Gmail: Gehe zu myaccount.google.com → Sicherheit → 2-Faktor-Authentifizierung aktivieren → App-Passwörter → Neues App-Passwort für 'Mail' erstellen. SMTP-Host: smtp.gmail.com, Port: 587.",
            url="https://myaccount.google.com/apppasswords",
            warning="Verwende NICHT dein normales Gmail-Passwort! Google blockiert Anmeldungen mit normalen Passwörtern für SMTP.",
        ),
        SetupStep(
            title="Microsoft 365 / Outlook",
            description="SMTP-Host: smtp.office365.com, Port: 587. Verwende deine Microsoft 365 E-Mail-Adresse und dein Passwort. SMTP-Authentifizierung muss im Admin Center aktiviert sein.",
        ),
        SetupStep(
            title="Zugangsdaten eintragen",
            description="Trage Host, Port, Benutzername und Passwort in die Felder oben ein. Klicke dann auf 'Verbindung testen', um die Konfiguration zu prüfen.",
        ),
    ],
)

POSTMARK_EMAIL = ConnectorDefinition(
    id="email_channel",
    name="E-Mail-Kanal (Postmark)",
    description="Bidirektionaler E-Mail-Kanal über Postmark — Kunden können per E-Mail mit dem AI-Assistenten kommunizieren.",
    category=ConnectorCategory.EMAIL,
    icon="PM",
    color="#FFCC00",
    docs_url="https://postmarkapp.com/developer",
    fields=[
        ConnectorField(
            key="enabled",
            label="Kanal aktiviert",
            field_type=FieldType.SELECT,
            options=[
                {"value": "true", "label": "Aktiviert"},
                {"value": "false", "label": "Deaktiviert"},
            ],
            default="false",
            setting_key="email_channel_enabled",
        ),
        ConnectorField(
            key="postmark_server_token",
            label="Postmark Server Token",
            field_type=FieldType.PASSWORD,
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            hint="Server API Token aus dem Postmark Dashboard.",
            sensitive=True,
            setting_key="postmark_server_token",
        ),
        ConnectorField(
            key="from_email",
            label="Absender-E-Mail",
            placeholder="ariia@mein-studio.de",
            hint="Muss als Sender Signature in Postmark verifiziert sein.",
            setting_key="email_outbound_from",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="Postmark-Account erstellen",
            description="Registriere dich auf postmarkapp.com. Postmark bietet zuverlässigen E-Mail-Versand mit hoher Zustellrate.",
            url="https://account.postmarkapp.com/sign_up",
        ),
        SetupStep(
            title="Server erstellen",
            description="Im Postmark Dashboard: Erstelle einen neuen Server (z.B. 'ARIIA Production'). Kopiere den 'Server API Token' und trage ihn oben ein.",
        ),
        SetupStep(
            title="Sender Signature einrichten",
            description="Sender Signatures → Add Domain or Sender → Verifiziere deine Absender-Domain oder E-Mail-Adresse. Ohne Verifizierung können keine E-Mails gesendet werden.",
            warning="Die Verifizierung kann per DNS (DKIM/SPF) oder per Bestätigungs-E-Mail erfolgen. DNS-Verifizierung wird empfohlen.",
        ),
        SetupStep(
            title="Inbound-Webhook einrichten (optional)",
            description="Für bidirektionalen E-Mail-Verkehr: Server → Settings → Inbound → Webhook URL: {base_url}/webhook/email/{tenant_slug}. Damit können Kunden per E-Mail antworten.",
        ),
    ],
)

SMS_CHANNEL = ConnectorDefinition(
    id="sms_channel",
    name="SMS-Kanal (Twilio)",
    description="SMS-Nachrichten über Twilio senden und empfangen.",
    category=ConnectorCategory.MESSAGING,
    icon="SM",
    color="#F22F46",
    webhook_path="/webhook/sms/{tenant_slug}",
    docs_url="https://www.twilio.com/docs/sms",
    fields=[
        ConnectorField(
            key="enabled",
            label="Kanal aktiviert",
            field_type=FieldType.SELECT,
            options=[
                {"value": "true", "label": "Aktiviert"},
                {"value": "false", "label": "Deaktiviert"},
            ],
            default="false",
            setting_key="sms_channel_enabled",
        ),
        ConnectorField(
            key="twilio_account_sid",
            label="Twilio Account SID",
            placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            hint="Zu finden auf der Twilio Console Startseite.",
            setting_key="twilio_account_sid",
        ),
        ConnectorField(
            key="twilio_auth_token",
            label="Twilio Auth Token",
            field_type=FieldType.PASSWORD,
            placeholder="Dein Twilio Auth Token",
            sensitive=True,
            setting_key="twilio_auth_token",
        ),
        ConnectorField(
            key="twilio_sms_number",
            label="SMS-Telefonnummer",
            placeholder="+4915123456789",
            hint="Deine Twilio-Telefonnummer im internationalen Format.",
            setting_key="twilio_sms_number",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="Twilio-Account erstellen",
            description="Registriere dich auf twilio.com. Twilio bietet einen kostenlosen Trial mit Guthaben zum Testen.",
            url="https://www.twilio.com/try-twilio",
        ),
        SetupStep(
            title="Telefonnummer kaufen",
            description="Twilio Console → Phone Numbers → Buy a Number → Wähle eine Nummer mit SMS-Fähigkeit. Für Deutschland: Wähle eine +49-Nummer.",
            url="https://console.twilio.com/us1/develop/phone-numbers/manage/search",
        ),
        SetupStep(
            title="Account SID und Auth Token kopieren",
            description="Twilio Console → Dashboard → Unter 'Account Info' findest du Account SID und Auth Token. Kopiere beide Werte und trage sie oben ein.",
            url="https://console.twilio.com/",
        ),
        SetupStep(
            title="Webhook konfigurieren",
            description="Twilio Console → Phone Numbers → Deine Nummer → Messaging → 'A message comes in' → Webhook URL: {base_url}/webhook/sms/{tenant_slug} (HTTP POST).",
        ),
    ],
)

VOICE_CHANNEL = ConnectorDefinition(
    id="voice_channel",
    name="Voice-Kanal (Twilio)",
    description="Telefonanrufe über Twilio empfangen — AI-gestützter Sprachassistent.",
    category=ConnectorCategory.VOICE,
    icon="VC",
    color="#A29BFE",
    webhook_path="/webhook/voice/{tenant_slug}",
    docs_url="https://www.twilio.com/docs/voice",
    fields=[
        ConnectorField(
            key="enabled",
            label="Kanal aktiviert",
            field_type=FieldType.SELECT,
            options=[
                {"value": "true", "label": "Aktiviert"},
                {"value": "false", "label": "Deaktiviert"},
            ],
            default="false",
            setting_key="voice_channel_enabled",
        ),
        ConnectorField(
            key="twilio_voice_number",
            label="Voice-Telefonnummer",
            placeholder="+49301234567",
            hint="Deine Twilio-Telefonnummer für eingehende Anrufe.",
            setting_key="twilio_voice_number",
        ),
        ConnectorField(
            key="twilio_voice_stream_url",
            label="Stream-URL (WebSocket)",
            field_type=FieldType.URL,
            placeholder="wss://deine-domain.de/voice/stream",
            hint="WebSocket-URL für das Echtzeit-Audio-Streaming.",
            required=False,
            setting_key="twilio_voice_stream_url",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="Twilio Voice einrichten",
            description="Verwende denselben Twilio-Account wie für SMS. Falls noch nicht vorhanden: Kaufe eine Telefonnummer mit Voice-Fähigkeit.",
        ),
        SetupStep(
            title="Voice Webhook konfigurieren",
            description="Twilio Console → Phone Numbers → Deine Nummer → Voice → 'A call comes in' → Webhook URL: {base_url}/webhook/voice/{tenant_slug} (HTTP POST).",
        ),
        SetupStep(
            title="Stream-URL konfigurieren (optional)",
            description="Für Echtzeit-Sprachverarbeitung: Trage die WebSocket-URL ein, über die das Audio-Streaming läuft. Format: wss://deine-domain.de/voice/stream.",
        ),
    ],
)

MAGICLINE = ConnectorDefinition(
    id="magicline",
    name="Magicline",
    description="Mitglieder-Sync und Studio-Daten über die Magicline Open API.",
    category=ConnectorCategory.MEMBERS,
    icon="ML",
    color="#FF6B35",
    supports_sync=True,
    docs_url="https://open-api.magicline.com/docs",
    fields=[
        ConnectorField(
            key="base_url",
            label="API-Basis-URL",
            field_type=FieldType.URL,
            placeholder="https://mein-studio.open-api.magicline.com",
            hint="Die Open API URL deines Magicline-Studios.",
            setting_key="magicline_base_url",
        ),
        ConnectorField(
            key="api_key",
            label="API Key",
            field_type=FieldType.PASSWORD,
            placeholder="Dein Magicline API Key",
            sensitive=True,
            setting_key="magicline_api_key",
        ),
        ConnectorField(
            key="tenant_id",
            label="Magicline Tenant-ID",
            placeholder="123456",
            hint="Die Tenant-ID deines Studios in Magicline.",
            setting_key="magicline_tenant_id",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="Magicline Open API aktivieren",
            description="Kontaktiere deinen Magicline-Ansprechpartner oder den Support, um die Open API für dein Studio freischalten zu lassen. Die API ist nicht standardmäßig aktiviert.",
        ),
        SetupStep(
            title="API-Zugangsdaten erhalten",
            description="Nach der Freischaltung erhältst du: Eine API-Basis-URL (z.B. https://mein-studio.open-api.magicline.com), einen API Key und deine Tenant-ID.",
        ),
        SetupStep(
            title="Zugangsdaten eintragen",
            description="Trage die drei Werte in die Felder oben ein und klicke auf 'Verbindung testen'. Bei Erfolg wird der Studio-Name angezeigt.",
        ),
        SetupStep(
            title="Mitglieder synchronisieren",
            description="Klicke auf 'Jetzt synchronisieren', um alle Mitglieder aus Magicline zu importieren. Der Sync kann auch automatisch per Cron-Job ausgeführt werden.",
        ),
    ],
)

SHOPIFY = ConnectorDefinition(
    id="shopify",
    name="Shopify",
    description="Kunden aus deinem Shopify-Store als Mitglieder synchronisieren.",
    category=ConnectorCategory.MEMBERS,
    icon="SH",
    color="#96BF48",
    supports_sync=True,
    docs_url="https://shopify.dev/docs/api/admin-rest",
    fields=[
        ConnectorField(
            key="shop_domain",
            label="Shop Domain",
            field_type=FieldType.URL,
            placeholder="my-store.myshopify.com",
            hint="Deine Shopify-Store-Domain (ohne https://).",
            setting_key="shopify_shop_domain",
        ),
        ConnectorField(
            key="access_token",
            label="Admin API Access Token",
            field_type=FieldType.PASSWORD,
            placeholder="shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            hint="Access Token einer Custom App mit read_customers Berechtigung.",
            sensitive=True,
            setting_key="shopify_access_token",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="Custom App erstellen",
            description="Shopify Admin → Settings → Apps and sales channels → Develop apps → Create an app. Gib der App einen Namen (z.B. 'ARIIA Sync').",
            url="https://admin.shopify.com/store/{shop}/settings/apps/development",
        ),
        SetupStep(
            title="API-Berechtigungen konfigurieren",
            description="In der App: Configuration → Admin API access scopes → Aktiviere 'read_customers'. Klicke auf 'Save'.",
        ),
        SetupStep(
            title="App installieren und Token kopieren",
            description="Klicke auf 'Install app' → Bestätige die Installation. Unter 'API credentials' findest du den 'Admin API access token'. Kopiere ihn sofort — er wird nur einmal angezeigt!",
            warning="Der Access Token wird nur einmal angezeigt! Speichere ihn sofort an einem sicheren Ort.",
        ),
        SetupStep(
            title="Verbindung testen und synchronisieren",
            description="Trage Domain und Token oben ein → 'Testen' → Bei Erfolg: 'Sync' klicken, um alle Kunden zu importieren.",
        ),
    ],
)

WOOCOMMERCE = ConnectorDefinition(
    id="woocommerce",
    name="WooCommerce",
    description="Kunden aus deinem WooCommerce-Shop als Mitglieder synchronisieren.",
    category=ConnectorCategory.MEMBERS,
    icon="WC",
    color="#7B2D8E",
    supports_sync=True,
    docs_url="https://woocommerce.github.io/woocommerce-rest-api-docs/",
    fields=[
        ConnectorField(
            key="store_url",
            label="Store URL",
            field_type=FieldType.URL,
            placeholder="https://mein-shop.de",
            hint="Die vollständige URL deines WooCommerce-Shops.",
            setting_key="woocommerce_store_url",
        ),
        ConnectorField(
            key="consumer_key",
            label="Consumer Key",
            field_type=FieldType.PASSWORD,
            placeholder="ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            sensitive=True,
            setting_key="woocommerce_consumer_key",
        ),
        ConnectorField(
            key="consumer_secret",
            label="Consumer Secret",
            field_type=FieldType.PASSWORD,
            placeholder="cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            sensitive=True,
            setting_key="woocommerce_consumer_secret",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="REST API aktivieren",
            description="WordPress Admin → WooCommerce → Settings → Advanced → REST API. Stelle sicher, dass die REST API aktiviert ist (Standard: aktiviert).",
        ),
        SetupStep(
            title="API-Schlüssel erstellen",
            description="REST API → Add key → Beschreibung: 'ARIIA Sync' → Benutzer: Wähle einen Admin → Berechtigungen: 'Read' → Generate API key.",
        ),
        SetupStep(
            title="Keys kopieren",
            description="Kopiere Consumer Key und Consumer Secret. Diese werden nur einmal angezeigt!",
            warning="Speichere beide Schlüssel sofort — sie können nicht erneut angezeigt werden.",
        ),
        SetupStep(
            title="SSL prüfen",
            description="WooCommerce REST API erfordert HTTPS. Stelle sicher, dass dein Shop ein gültiges SSL-Zertifikat hat.",
            warning="Ohne HTTPS funktioniert die API-Authentifizierung nicht korrekt.",
        ),
    ],
)

HUBSPOT = ConnectorDefinition(
    id="hubspot",
    name="HubSpot",
    description="Kontakte aus HubSpot CRM als Mitglieder synchronisieren.",
    category=ConnectorCategory.CRM,
    icon="HS",
    color="#FF7A59",
    supports_sync=True,
    docs_url="https://developers.hubspot.com/docs/api/crm/contacts",
    fields=[
        ConnectorField(
            key="access_token",
            label="Private App Access Token",
            field_type=FieldType.PASSWORD,
            placeholder="pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            hint="Access Token einer HubSpot Private App.",
            sensitive=True,
            setting_key="hubspot_access_token",
        ),
    ],
    setup_steps=[
        SetupStep(
            title="Private App erstellen",
            description="HubSpot → Settings (Zahnrad) → Integrations → Private Apps → Create a private app. Gib der App einen Namen (z.B. 'ARIIA Sync').",
            url="https://app.hubspot.com/private-apps/",
        ),
        SetupStep(
            title="Berechtigungen konfigurieren",
            description="Im Tab 'Scopes': Aktiviere unter 'CRM' die Berechtigung 'crm.objects.contacts.read'. Optional: 'crm.objects.companies.read' für Firmendaten.",
        ),
        SetupStep(
            title="App erstellen und Token kopieren",
            description="Klicke auf 'Create app' → Bestätige → Kopiere den angezeigten Access Token (beginnt mit 'pat-').",
        ),
        SetupStep(
            title="Verbindung testen",
            description="Trage den Token oben ein → 'Testen' → Bei Erfolg wird die Anzahl der Kontakte angezeigt. Dann 'Sync' klicken.",
        ),
    ],
)


# ─────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────

ALL_CONNECTORS: dict[str, ConnectorDefinition] = {
    c.id: c
    for c in [
        TELEGRAM,
        WHATSAPP,
        INSTAGRAM,
        FACEBOOK_MESSENGER,
        GOOGLE_BUSINESS,
        SMTP_EMAIL,
        POSTMARK_EMAIL,
        SMS_CHANNEL,
        VOICE_CHANNEL,
        MAGICLINE,
        SHOPIFY,
        WOOCOMMERCE,
        HUBSPOT,
    ]
}

CATEGORIES_ORDER = [
    ConnectorCategory.MESSAGING,
    ConnectorCategory.EMAIL,
    ConnectorCategory.VOICE,
    ConnectorCategory.MEMBERS,
    ConnectorCategory.CRM,
]

CATEGORY_LABELS = {
    ConnectorCategory.MESSAGING: "Messaging-Kanäle",
    ConnectorCategory.EMAIL: "E-Mail",
    ConnectorCategory.VOICE: "Telefonie & Voice",
    ConnectorCategory.MEMBERS: "Mitglieder-Quellen",
    ConnectorCategory.CRM: "CRM-Systeme",
    ConnectorCategory.BILLING: "Abrechnung",
}


def get_connectors_by_category() -> dict[str, list[dict]]:
    """Return all connectors grouped by category."""
    result = {}
    for cat in CATEGORIES_ORDER:
        connectors = [
            c.to_dict(include_docs=False)
            for c in ALL_CONNECTORS.values()
            if c.category == cat
        ]
        if connectors:
            result[cat.value] = {
                "label": CATEGORY_LABELS.get(cat, cat.value),
                "connectors": connectors,
            }
    return result


def get_connector(connector_id: str) -> ConnectorDefinition | None:
    """Get a single connector definition by ID."""
    return ALL_CONNECTORS.get(connector_id)
