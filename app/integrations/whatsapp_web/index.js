const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const express = require('express');
const QRCode = require('qrcode');
const axios = require('axios');
const pino = require('pino');
const path = require('path');

// ─── Config (via env or defaults) ───
const PORT = parseInt(process.env.BRIDGE_PORT || '3000');
const WEBHOOK_URL = process.env.BRIDGE_WEBHOOK_URL || 'http://localhost:8000/webhook/whatsapp';
const BRIDGE_MODE = process.env.BRIDGE_MODE || 'production'; // 'self' = dev (self-chat only), 'production' = all incoming
const AUTH_DIR = process.env.BRIDGE_AUTH_DIR || path.join(__dirname, 'auth_info_baileys');
const LOG_LEVEL = process.env.BRIDGE_LOG_LEVEL || 'silent';

const app = express();
app.use(express.json());

// Live QR state
let latestQR = null;
let connectionStatus = 'disconnected';
let messageStats = { forwarded: 0, ignored: 0, errors: 0 };

console.log(`[ARIIA Bridge] Mode: ${BRIDGE_MODE} | Port: ${PORT} | Webhook: ${WEBHOOK_URL}`);

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

    const sock = makeWASocket({
        auth: state,
        logger: pino({ level: LOG_LEVEL }),
        browser: ["ARIIA", "Chrome", "1.0"]
    });

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            latestQR = qr;
            connectionStatus = 'waiting_for_scan';
            console.log('[QR] New QR code. Open http://0.0.0.0:' + PORT + '/qr to scan.');
        }

        if (connection === 'close') {
            latestQR = null;
            connectionStatus = 'reconnecting';
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log(`[Connection] Closed (code: ${statusCode}). Reconnecting: ${shouldReconnect}`);
            if (shouldReconnect) {
                setTimeout(() => connectToWhatsApp(), 3000); // 3s backoff
            } else {
                console.log('[Connection] Logged out. Delete auth_info_baileys/ and restart to re-scan.');
                connectionStatus = 'logged_out';
            }
        } else if (connection === 'open') {
            latestQR = null;
            connectionStatus = 'connected';
            const ownNumber = sock.user?.id?.replace(/:\d+@/, '@') || 'unknown';
            console.log(`[Connection] ✅ Connected as ${ownNumber}`);
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return;

        for (const msg of messages) {
            if (!msg.message) continue;
            if (msg.key.remoteJid === 'status@broadcast') continue;

            // ─── Mode-based filtering ───
            const ownJid = sock.user?.id?.replace(/:\d+@/, '@') || '';
            const isGroup = msg.key.remoteJid?.endsWith('@g.us');
            const isSelfChat = msg.key.remoteJid === ownJid;

            if (BRIDGE_MODE === 'self') {
                // Dev mode: only self-chat, only own messages
                if (!isSelfChat || !msg.key.fromMe) {
                    messageStats.ignored++;
                    continue;
                }
            } else {
                // Production mode: all incoming from customers (not fromMe, not groups)
                if (msg.key.fromMe || isGroup) {
                    messageStats.ignored++;
                    continue;
                }
            }

            const text = msg.message.conversation ||
                msg.message.extendedTextMessage?.text ||
                "";

            if (!text) continue;

            const senderJid = msg.key.remoteJid.replace('@s.whatsapp.net', '');

            const payload = {
                object: "whatsapp_business_account",
                entry: [{
                    id: "WHATSAPP_WEB_BRIDGE",
                    changes: [{
                        value: {
                            messaging_product: "whatsapp",
                            metadata: {
                                display_phone_number: ownJid.replace('@s.whatsapp.net', ''),
                                phone_number_id: "ARIIA_BRIDGE"
                            },
                            contacts: [{
                                profile: { name: msg.pushName || "User" },
                                wa_id: senderJid
                            }],
                            messages: [{
                                from: senderJid,
                                id: msg.key.id,
                                timestamp: msg.messageTimestamp,
                                text: { body: text },
                                type: "text"
                            }]
                        },
                        field: "messages"
                    }]
                }]
            };

            try {
                await axios.post(WEBHOOK_URL, payload, { timeout: 10000 });
                messageStats.forwarded++;
                console.log(`[MSG] ${msg.pushName || senderJid}: "${text.substring(0, 50)}..."`);
            } catch (error) {
                messageStats.errors++;
                console.error(`[ERR] Webhook failed: ${error.message}`);
            }
        }
    });

    // ─── HTTP Endpoints ───

    // Health / status
    app.get('/health', (req, res) => {
        res.json({
            status: connectionStatus,
            mode: BRIDGE_MODE,
            stats: messageStats,
            uptime: process.uptime(),
        });
    });

    // Live QR page
    app.get('/qr', async (req, res) => {
        if (connectionStatus === 'connected') {
            return res.send(`
                <html><body style="background:#111;color:#0f0;font-family:monospace;text-align:center;padding:60px">
                <h1>✅ WhatsApp Connected!</h1>
                <p>ARIIA Bridge is active (${BRIDGE_MODE} mode). You can close this page.</p>
                </body></html>
            `);
        }
        if (!latestQR) {
            return res.send(`
                <html><head><meta http-equiv="refresh" content="3"></head>
                <body style="background:#111;color:#fff;font-family:monospace;text-align:center;padding:60px">
                <h1>⏳ Waiting for QR Code...</h1>
                <p>Page refreshes automatically.</p>
                </body></html>
            `);
        }
        try {
            const qrDataUrl = await QRCode.toDataURL(latestQR, { width: 400, margin: 2 });
            res.send(`
                <html><head><meta http-equiv="refresh" content="15"></head>
                <body style="background:#111;color:#fff;font-family:monospace;text-align:center;padding:40px">
                <h1>📱 ARIIA WhatsApp Bridge</h1>
                <p>Scan with WhatsApp → Linked Devices → Link a Device</p>
                <img src="${qrDataUrl}" style="margin:20px;border-radius:12px"/>
                <p style="color:#888">Auto-refreshes every 15s</p>
                </body></html>
            `);
        } catch (err) {
            res.status(500).send('QR generation error: ' + err.message);
        }
    });

    // Send message API
    app.post('/send', async (req, res) => {
        const { to, text } = req.body;
        if (!to || !text) return res.status(400).json({ error: "Missing 'to' or 'text'" });

        try {
            const jid = to.includes('@') ? to : to + '@s.whatsapp.net';
            const sent = await sock.sendMessage(jid, { text: text });
            res.json({ status: "sent", id: sent.key.id });
        } catch (error) {
            console.error('[ERR] Send failed:', error.message);
            res.status(500).json({ error: error.message });
        }
    });
}

// Start
connectToWhatsApp();
app.listen(PORT, '0.0.0.0', () => console.log(`[ARIIA Bridge] Running on http://0.0.0.0:${PORT}`));
