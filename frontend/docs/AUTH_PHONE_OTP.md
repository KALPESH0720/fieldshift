# Phone + 6-Digit SMS OTP Authentication Specification

Field Shift uses **Phone Number + 6-Digit SMS One-Time Code (OTP)** as its sole authentication mechanism. Email addresses and passwords are not collected, stored, or accepted anywhere in the application.

---

## 1. End-to-End Authentication Flow

A single screen (`/login`) handles both returning users and first-time farmers:

1. **Step 1 — Request OTP (`POST /api/v1/auth/otp/request`)**
   - Client validates and formats the mobile number into strict E.164 (`+919876543210`) using `libphonenumber-js/mobile`.
   - Server validates E.164 format, checks rate limits, generates a cryptographically random 6-digit code (`000000`–`999999`, excluding all-zeros), stores only its HMAC-SHA256 hash in `otp_challenges`, and dispatches the SMS via the configured provider.
   - Server returns `202 Accepted` with `{ challengeId, expiresInSeconds: 300, resendAfterSeconds: 30, voiceAvailable }`.
   - **No Account Enumeration:** The response payload, status code, and timing must be identical whether the E.164 number already exists in `app_users` or is brand new.

2. **Step 2 — Verify OTP (`POST /api/v1/auth/otp/verify`)**
   - Client sends `{ challengeId, phoneE164, code, profile? }`.
   - Server verifies that the challenge is unconsumed, unexpired (`now() < expires_at`), and below the 5-attempt limit (`attempts < 5`).
   - Server increments `attempts` atomically before comparing `HMAC-SHA256(secret, challengeId || ':' || phoneE164 || ':' || code)` in constant time (`crypto.timingSafeEqual`).
   - On match:
     - Marks `consumed_at = now()`.
     - Upserts the user in `app_users` by `phone_e164`:
       - Existing active user → `isNewUser = false`, updates `last_login_at`.
       - New phone number (or `status = 'pending'` without `display_name`) → creates user with `status = 'pending'`, default `farmer` role, `isNewUser = true`.
     - Issues `Secure; HttpOnly; SameSite=Lax` access and rotating refresh cookies and returns `{ user, csrfToken, isNewUser }`.

3. **New-Farmer Profile Completion (`PATCH /api/v1/me`)**
   - When `isNewUser: true`, the `/login` screen prompts for:
     - **Display Name** (`displayName`, required)
     - **Preferred Language** (`preferredLocale`, pre-filled from the active UI language)
     - **SMS & Privacy Consent** (`smsOptIn: true`, `privacyConsent: true`, required)
   - Submitting calls `PATCH /api/v1/me`, which sets `display_name`, `preferred_locale`, `sms_opt_in_at = now()`, `privacy_accepted_at = now()`, and promotes `status` from `'pending'` to `'active'`.

---

## 2. Cryptographic Storage & Challenge Lifecycle

| Parameter | Specification |
|---|---|
| **Code format** | 6 decimal digits (`^\d{6}$`), generated via CSPRNG (`crypto.randomInt(100000, 1000000)`). |
| **At-rest storage** | Never store plaintext OTPs in PostgreSQL, Redis, or logs. Store `code_hash = encode(hmac(challenge_id || ':' || phone_e164 || ':' || code, OTP_HMAC_SECRET, 'sha256'), 'hex')`. |
| **Contact hashing** | Store `contact_hash = encode(hmac(phone_e164, CONTACT_HMAC_SECRET, 'sha256'), 'hex')` in `otp_challenges` so challenge tables do not leak raw phone numbers. |
| **TTL / Expiry** | **5 minutes** (`300 seconds`). Expired challenges return `410 Gone` with `error.code = "otp_expired"`. |
| **Attempt cap** | **Maximum 5 verification attempts** per `challengeId`. On the 5th failed attempt, invalidate the challenge and return `429 Too Many Requests` with `error.code = "otp_attempts_exceeded"` and `retryAfterSeconds: 300`. |
| **Resend cooldown** | Minimum **30 seconds** between `POST /auth/otp/request` calls for the same phone number, and at most **3 resends** (4 total codes) per 15-minute window. Issuing a new challenge immediately invalidates any prior unconsumed challenge for that `contact_hash`. |

---

## 3. Multi-Layer Rate Limiting

Enforce sliding-window rate limits in Redis / PostgreSQL across three dimensions:

1. **Per E.164 Phone Number (`contact_hash`)**
   - Max **4 OTP requests per 15 minutes**, max **10 OTP requests per 24 hours**.
   - Lockout for 15 minutes (`retryAfterSeconds: 900`) after 3 consecutive exhausted challenges.
2. **Per Client IP (`ip_hash`)**
   - Max **10 OTP requests per 15 minutes** and **30 verify requests per 15 minutes** per IP.
3. **Per Device (`X-Device-Id`)**
   - Max **6 OTP requests per 15 minutes** per device UUID.
4. **Country Prefix Allowlist**
   - Reject premium-rate or non-geographic prefixes (`+882`, `+883`, etc.) and restrict SMS dispatch to configured launch country prefixes unless explicitly enabled.

All rate-limit responses return HTTP `429` with:

```json
{
  "error": {
    "code": "rate_limited",
    "message": "Too many OTP requests. Please wait before trying again.",
    "requestId": "req_01J...",
    "retryAfterSeconds": 300
  }
}
```

---

## 4. India TRAI DLT Template & Web OTP Format

For Indian mobile numbers (`+91`), transactional/service SMS messages must be registered on a Telecom Regulatory Authority of India (TRAI) Distributed Ledger Technology (DLT) portal (Jio, Airtel, Vi, or BSNL) with an approved Header (Sender ID, e.g. `FLDSHF`) and Principal Entity ID.

### Recommended DLT & Web OTP Standard Template

To support automatic 1-tap SMS autofill via the browser **Web OTP API** (`navigator.credentials.get({ otp: { transport: ['sms'] } })`), the last line of the SMS **must** follow the origin-bound one-time code format (`@<domain> #<code_variable>`):

```text
Your Field Shift login code is {#var#}. Valid for 5 minutes. Do not share this code with anyone.
@{#var#} #{#var#}
```

Rendered example sent over SMS:

```text
Your Field Shift login code is 482910. Valid for 5 minutes. Do not share this code with anyone.
@fieldshift.example.org #482910
```

- Pass `dltEntityId` and `dltTemplateId` in the provider payload for `+91` destinations.
- Select localized DLT templates (`en`, `hi`, `mr`) based on the `locale` field in `POST /auth/otp/request`.

---

## 5. SMS Provider Abstraction

Implement a narrow server-side provider interface so gateways can be swapped or failed over per country without touching auth logic:

```ts
export interface OtpDispatchInput {
  phoneE164: string;
  code: string;
  locale: string;
  channel: 'sms' | 'voice';
  appDomain: string;
  requestId: string;
}

export interface OtpDeliveryProvider {
  readonly id: string;
  supportsCountry(iso2: string, channel: 'sms' | 'voice'): boolean;
  sendOtp(input: OtpDispatchInput): Promise<{ providerMessageId: string }>;
}
```

- **Primary India (`+91`) providers:** MSG91, Gupshup, or AWS SNS (ap-south-1) with DLT Entity/Template IDs.
- **International fallback:** Twilio Verify / Programmable Messaging or Infobip.
- **Voice OTP fallback (`channel: 'voice'`):** Only advertise `voiceAvailable: true` in `OtpChallenge` when a voice-capable provider is configured and enabled for the phone number's country code.

---

## 6. Consent, Privacy & Shared-Phone Safety

- **SMS & Privacy Consent:** During new-farmer sign-up, the user must explicitly check the consent box agreeing to receive one-time SMS login codes and enabled farm alerts. The server records `sms_opt_in_at` and `privacy_accepted_at` on `app_users` and writes an `audit_events` row (`action = 'auth.consent_granted'`).
- **Masked Phone Display:** The client stores the canonical E.164 phone number (`+919876543210`) in session state and displays it masked (`+91 ••••• ••210`) in the app header and Settings profile card.
- **Shared Phones ("Not you? Switch user"):** Because rural households and FPO field staff frequently share a single handset, tapping **Log Out** or **"Not you? Switch user"** revokes the server session, clears user-owned IndexedDB tables (`plots`, `soilRecords`, `weatherCache`, `syncQueue`), and warns the farmer first if `db.syncQueue` has unsynced offline changes.
- **Demo / Mock Mode (`VITE_USE_MOCKS=true`):** Uses `src/services/auth/mockAuthAdapter.js` in the browser, accepts only code `123456`, displays a visible **Demo** badge and hint on `/login`, and persists registered demo phone numbers in `localStorage` (`fieldshift-mock-users`) so both sign-up and returning login work offline during demos.

