import { T } from "./tokens";

export const channelData = [
  { name: "WhatsApp", value: 312, color: T.whatsapp, icon: "WA" },
  { name: "Telegram", value: 198, color: T.telegram, icon: "TG" },
  { name: "E-Mail", value: 156, color: T.email, icon: "EM" },
  { name: "Telefon", value: 68, color: T.phone, icon: "PH" },
];

export const hourlyTrend = Array.from({ length: 24 }, (_, i) => ({
  hour: `${String(i).padStart(2, "0")}:00`,
  aiResolved: Math.floor(Math.random() * 35 + (i > 6 && i < 22 ? 25 : 5)),
  escalated: Math.floor(Math.random() * 10 + (i > 10 && i < 20 ? 5 : 1)),
  satisfaction: Math.floor(Math.random() * 10 + 82),
}));

export const weeklyTrend = [
  { day: "Mo", tickets: 680, resolved: 578, escalated: 102 },
  { day: "Di", tickets: 734, resolved: 598, escalated: 136 },
  { day: "Mi", tickets: 695, resolved: 580, escalated: 115 },
  { day: "Do", tickets: 712, resolved: 605, escalated: 107 },
  { day: "Fr", tickets: 789, resolved: 648, escalated: 141 },
  { day: "Sa", tickets: 423, resolved: 378, escalated: 45 },
  { day: "So", tickets: 312, resolved: 287, escalated: 25 },
];

export const topIssues = [
  { issue: "Terminbuchung & Änderungen", count: 157, aiRate: 90, trend: 5 },
  { issue: "Mitgliedschaftsfragen", count: 134, aiRate: 73, trend: -2 },
  { issue: "Kursinfos & Trainer", count: 89, aiRate: 91, trend: 8 },
  { issue: "Technische Probleme (App)", count: 67, aiRate: 63, trend: -5 },
  { issue: "Zahlungs- & Abo-Fragen", count: 61, aiRate: 57, trend: 3 },
  { issue: "Öffnungszeiten & Location", count: 45, aiRate: 98, trend: 0 },
  { issue: "Personal Training Anfragen", count: 38, aiRate: 68, trend: 12 },
  { issue: "Beschwerden & Feedback", count: 29, aiRate: 41, trend: -8 },
];

export const conversations = [
  { id: "T-4821", channel: "whatsapp", member: "Julia Meier", avatar: "JM", issue: "Kann ich mein Abo für 2 Wochen pausieren? Bin im Urlaub.", confidence: 94, status: "resolved", time: "vor 3 Min", messages: 4, sentiment: "positive" },
  { id: "T-4820", channel: "telegram", member: "Marco Klein", avatar: "MK", issue: "Termin für Kraft-Training am Montag 18 Uhr bitte.", confidence: 97, status: "resolved", time: "vor 7 Min", messages: 3, sentiment: "neutral" },
  { id: "T-4819", channel: "email", member: "Sandra Richter", avatar: "SR", issue: "Die App stürzt seit gestern ständig ab. Kann mich nicht einloggen.", confidence: 42, status: "escalated", time: "vor 12 Min", messages: 6, sentiment: "negative" },
  { id: "T-4818", channel: "whatsapp", member: "Thomas Berg", avatar: "TB", issue: "Welche Kurse gibt es am Freitag Nachmittag?", confidence: 99, status: "resolved", time: "vor 15 Min", messages: 2, sentiment: "positive" },
  { id: "T-4817", channel: "phone", member: "Anna Lang", avatar: "AL", issue: "Möchte den Trainer wechseln für Personal Training.", confidence: 62, status: "pending", time: "vor 18 Min", messages: 5, sentiment: "neutral" },
  { id: "T-4816", channel: "whatsapp", member: "Lukas Fischer", avatar: "LF", issue: "Wie kann ich meine Mitgliedschaft upgraden auf Premium?", confidence: 88, status: "resolved", time: "vor 22 Min", messages: 3, sentiment: "positive" },
  { id: "T-4815", channel: "telegram", member: "Emma Weber", avatar: "EW", issue: "Gibt es gerade Angebote für Neukunden? Mein Freund will sich anmelden.", confidence: 76, status: "pending", time: "vor 25 Min", messages: 4, sentiment: "positive" },
  { id: "T-4814", channel: "email", member: "Felix Braun", avatar: "FB", issue: "Vertrag kündigen zum nächstmöglichen Zeitpunkt.", confidence: 35, status: "escalated", time: "vor 31 Min", messages: 8, sentiment: "negative" },
  { id: "T-4813", channel: "whatsapp", member: "Lena Schneider", avatar: "LS", issue: "Sauna heute geöffnet? War letzte Woche wegen Wartung zu.", confidence: 95, status: "resolved", time: "vor 38 Min", messages: 2, sentiment: "neutral" },
  { id: "T-4812", channel: "phone", member: "Max Hoffmann", avatar: "MH", issue: "Parkmöglichkeiten in der Nähe vom Studio?", confidence: 91, status: "resolved", time: "vor 42 Min", messages: 2, sentiment: "neutral" },
];

export const escalations = [
  { id: "ESC-102", ticket: "T-4819", member: "Sandra Richter", reason: "Technisches Problem außerhalb AI-Kompetenz", priority: "high", assignee: "Unassigned", age: "12 Min", channel: "email" },
  { id: "ESC-101", ticket: "T-4814", member: "Felix Braun", reason: "Kündigungsanfrage erfordert Retention-Gespräch", priority: "critical", assignee: "Maria S.", age: "31 Min", channel: "email" },
  { id: "ESC-100", ticket: "T-4811", member: "Sophie Wagner", reason: "Abrechnungsfehler – Doppelabbuchung", priority: "high", assignee: "Unassigned", age: "45 Min", channel: "whatsapp" },
  { id: "ESC-099", ticket: "T-4808", member: "Jan Müller", reason: "Beschwerde über Hygiene – Management nötig", priority: "medium", assignee: "Tom K.", age: "1.2 Std", channel: "telegram" },
  { id: "ESC-098", ticket: "T-4805", member: "Petra Schulz", reason: "Spezielle Gesundheitsfrage – Trainer-Input nötig", priority: "low", assignee: "Lisa H.", age: "2.1 Std", channel: "phone" },
];

export const knowledgeCategories = [
  { name: "Mitgliedschaft & Verträge", articles: 24, coverage: 87, lastUpdated: "vor 2 Tagen" },
  { name: "Kursangebot & Zeitplan", articles: 18, coverage: 94, lastUpdated: "vor 4 Std" },
  { name: "Terminbuchung", articles: 12, coverage: 96, lastUpdated: "vor 1 Tag" },
  { name: "Preise & Angebote", articles: 15, coverage: 82, lastUpdated: "vor 5 Tagen" },
  { name: "Studio & Ausstattung", articles: 21, coverage: 91, lastUpdated: "vor 3 Tagen" },
  { name: "Trainer & Personal Training", articles: 9, coverage: 78, lastUpdated: "vor 1 Woche" },
  { name: "Technischer Support", articles: 8, coverage: 63, lastUpdated: "vor 2 Wochen" },
  { name: "FAQ & Allgemein", articles: 32, coverage: 95, lastUpdated: "vor 6 Std" },
];

export const syncStatus = {
  lastSync: "vor 2 Min",
  totalMembers: 2847,
  activeMembers: 2134,
  newToday: 7,
  churned: 2,
  syncErrors: 0,
  apiCalls: 1247,
  apiLimit: 10000,
};

export const syncHistory = Array.from({ length: 24 }, (_, i) => ({
  time: `${String(23 - i).padStart(2, "0")}:00`,
  records: Math.floor(Math.random() * 50 + 20),
  errors: Math.floor(Math.random() * 3),
  latency: Math.floor(Math.random() * 200 + 80),
})).reverse();
