# Real World Migration Guide (ARNI v1.4)

You are moving from Mock/Sandbox to Production. Follow these steps systematically.

## 1. WhatsApp Number Registration (Meta Dashboard)
*If you haven't connected your number yet:*

1. Go to [Meta Developers](https://developers.facebook.com/apps/) > My Apps > **WhatsApp** > **API Setup**.
2. Scroll to "Step 5: Add a phone number".
3. Click **Add Phone Number**.
4. Follow the wizard (Verify via SMS/Voice).
   - *Note: The number must NOT be active on WhatsApp mobile app. Delete the account on the phone if necessary.*
5. Once verified, you will see:
   - **Phone Number ID** (Copy this to `.env`)
   - **WhatsApp Business Account ID**

---

## 2. Environment Secrets (`.env`)
The current `.env` is minimal. You must fill in the real credentials.

### WhatsApp (Meta Cloud API)
- **META_APP_SECRET:** From Meta App Dashboard > App Settings > Basic.
- **META_ACCESS_TOKEN:** System User Token (Permanent) with `whatsapp_business_messaging` permission.
- **META_PHONE_NUMBER_ID:** From WhatsApp > API Setup.
- **META_VERIFY_TOKEN:** Choose a random string (e.g. `arni-verify-123`) and set it here AND in Meta Dashboard.

### Voice (ElevenLabs)
- **ELEVENLABS_API_KEY:** From ElevenLabs.io (Profile > API Key).
- Required for high-quality TTS. Fallback is currently "Silent Stub".

### Telegram (Optional)
- **TELEGRAM_BOT_TOKEN:** From @BotFather.

### Magicline
- Check `../getimpulse/Magicline/sandbox/.env` vs Production env.
- Provide `MAGICLINE_API_KEY` for the real studio if different.

---

## 2. Platform Configuration

### WhatsApp Webhook
1. Go to [Meta Developers](https://developers.facebook.com) > Your App > WhatsApp > Configuration.
2. Edit **Webhook**:
   - **Callback URL:** `http://185.209.228.251:8000/webhook/whatsapp`
   - **Verify Token:** The string you set in `META_VERIFY_TOKEN`.
3. Click "Verify and Save".
4. Subscribe to `messages` field.

### Magicline Webhook
1. The endpoint is `http://185.209.228.251:9010`.
2. Configure Magicline implementation to send webhooks here.

---

## 3. Hardware / Streams

### Vision (Cameras)
- Add `RTSP_URL=rtsp://user:pass@ip:554/stream` to `.env`.
- Ensure the VPS can reach this IP (VPN/Tunnel if camera is local).

---

## 4. Verification
After setting secrets, restart ARNI:
```bash
./scripts/launch.sh
```
Check logs:
```bash
tail -f logs/arni.log
```
