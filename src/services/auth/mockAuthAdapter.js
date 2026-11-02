import { ApiClientError } from '../../api/client';

export const MOCK_OTP_CODE = '123456';
export const MOCK_USERS_STORAGE_KEY = 'fieldshift-mock-users';
export const SESSION_STORAGE_KEY = 'fieldshift-session';
const MOCK_CHALLENGES_STORAGE_KEY = 'fieldshift-mock-challenges';

const DEFAULT_EXPIRES_IN_SECONDS = 300; // 5 minutes
const DEFAULT_RESEND_AFTER_SECONDS = 30;
const MAX_ATTEMPTS_PER_CHALLENGE = 5;
const LOCKOUT_SECONDS = 60;
const MOCK_DELAY_MS = 350;

function delay(ms = MOCK_DELAY_MS) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function generateId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `mock-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function readMockUsers() {
  try {
    const raw = window.localStorage.getItem(MOCK_USERS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeMockUsers(usersMap) {
  try {
    window.localStorage.setItem(MOCK_USERS_STORAGE_KEY, JSON.stringify(usersMap));
  } catch {
    // Ignore storage quota errors
  }
}

function readChallenges() {
  try {
    const raw = window.sessionStorage.getItem(MOCK_CHALLENGES_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeChallenges(challengesMap) {
  try {
    window.sessionStorage.setItem(MOCK_CHALLENGES_STORAGE_KEY, JSON.stringify(challengesMap));
  } catch {
    // Ignore storage quota errors
  }
}

function getRolesForPhone(phoneE164) {
  const configuredExtensionPhones = String(import.meta.env.VITE_MOCK_EXTENSION_PHONES || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  const isExtension = configuredExtensionPhones.includes(phoneE164);
  const roles = [
    {
      code: 'farmer',
      scope: 'global',
      groupId: null,
      permissions: ['plots:read', 'plots:write', 'soil:read', 'soil:write'],
    },
  ];

  if (isExtension) {
    roles.push({
      code: 'extension',
      scope: 'group',
      groupId: 'fpo-dicholi-01',
      permissions: ['group:read', 'farmers:read'],
    });
  }

  return roles;
}

export const mockAuthAdapter = {
  async requestOtp(phoneE164) {
    await delay();

    const ttlEnv = Number(import.meta.env.VITE_MOCK_OTP_TTL_SECONDS);
    const expiresInSeconds = Number.isFinite(ttlEnv) && ttlEnv > 0 ? ttlEnv : DEFAULT_EXPIRES_IN_SECONDS;
    const resendAfterSeconds = DEFAULT_RESEND_AFTER_SECONDS;
    const challengeId = generateId();

    const challenges = readChallenges();
    // Invalidate any previous active challenges for the same phone number
    Object.values(challenges).forEach((entry) => {
      if (entry && entry.phoneE164 === phoneE164 && !entry.consumedAt) {
        entry.invalidated = true;
      }
    });

    challenges[challengeId] = {
      challengeId,
      phoneE164,
      createdAt: Date.now(),
      expiresAt: Date.now() + expiresInSeconds * 1000,
      attempts: 0,
      maxAttempts: MAX_ATTEMPTS_PER_CHALLENGE,
      lockedUntil: null,
      verified: false,
      consumedAt: null,
    };
    writeChallenges(challenges);

    // Identical response whether or not the phone number is already registered
    return {
      challengeId,
      expiresInSeconds,
      resendAfterSeconds,
      voiceAvailable: import.meta.env.VITE_MOCK_VOICE_OTP === 'true',
    };
  },

  async verifyOtp({ challengeId, phoneE164, code, profile = null }) {
    await delay();

    const challenges = readChallenges();
    let challenge = challengeId ? challenges[challengeId] : null;

    if (!challenge && phoneE164) {
      // Fall back to the most recent challenge for this phone number
      const matching = Object.values(challenges)
        .filter((c) => c && c.phoneE164 === phoneE164 && !c.invalidated)
        .sort((a, b) => b.createdAt - a.createdAt);
      challenge = matching[0] || null;
    }

    if (!challenge || challenge.invalidated) {
      throw new ApiClientError({
        status: 410,
        code: 'otp_expired',
        message: 'Verification code has expired. Please request a new code.',
      });
    }

    const now = Date.now();
    if (now > challenge.expiresAt) {
      throw new ApiClientError({
        status: 410,
        code: 'otp_expired',
        message: 'Verification code has expired. Please request a new code.',
      });
    }

    if (challenge.lockedUntil && now < challenge.lockedUntil) {
      const retryAfterSeconds = Math.max(1, Math.ceil((challenge.lockedUntil - now) / 1000));
      throw new ApiClientError({
        status: 429,
        code: 'otp_attempts_exceeded',
        message: 'Too many incorrect attempts.',
        retryAfterSeconds,
      });
    }

    const normalizedCode = String(code || '').trim();
    if (!challenge.verified) {
      if (normalizedCode !== MOCK_OTP_CODE) {
        challenge.attempts = (challenge.attempts || 0) + 1;
        const attemptsRemaining = Math.max(0, challenge.maxAttempts - challenge.attempts);

        if (challenge.attempts >= challenge.maxAttempts) {
          challenge.lockedUntil = now + LOCKOUT_SECONDS * 1000;
          writeChallenges(challenges);
          throw new ApiClientError({
            status: 429,
            code: 'otp_attempts_exceeded',
            message: 'Too many incorrect attempts.',
            retryAfterSeconds: LOCKOUT_SECONDS,
            details: { attemptsRemaining: 0 },
          });
        }

        writeChallenges(challenges);
        throw new ApiClientError({
          status: 400,
          code: 'otp_invalid',
          message: 'Incorrect verification code.',
          details: { attemptsRemaining },
        });
      }

      challenge.verified = true;
      writeChallenges(challenges);
    }

    const targetPhone = challenge.phoneE164 || phoneE164;
    const users = readMockUsers();
    const existingUser = users[targetPhone];

    // Existing registered user -> log in immediately
    if (existingUser && existingUser.displayName && existingUser.profileComplete !== false) {
      const updatedUser = {
        ...existingUser,
        preferredLocale: profile?.preferredLocale || existingUser.preferredLocale || 'en',
        updatedAt: new Date().toISOString(),
        lastLoginAt: new Date().toISOString(),
      };
      users[targetPhone] = updatedUser;
      writeMockUsers(users);
      challenge.consumedAt = Date.now();
      writeChallenges(challenges);

      try {
        window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(updatedUser));
      } catch {
        // Ignore storage errors
      }

      return {
        user: updatedUser,
        isNewUser: false,
        csrfToken: 'mock-csrf-token',
      };
    }

    // New user: if profile.displayName is already supplied, complete sign-up right away
    if (profile && String(profile.displayName || '').trim()) {
      const nowIso = new Date().toISOString();
      const createdUser = {
        id: existingUser?.id || generateId(),
        displayName: String(profile.displayName).trim(),
        phoneE164: targetPhone,
        status: 'active',
        countryCode: profile.countryCode || 'IN',
        preferredLocale: profile.preferredLocale || 'en',
        profileComplete: true,
        consents: profile.consents || {
          privacyNoticeVersion: '2026-10',
          dataProcessing: true,
          smsMessages: true,
          acceptedAt: nowIso,
        },
        roles: getRolesForPhone(targetPhone),
        createdAt: existingUser?.createdAt || nowIso,
        updatedAt: nowIso,
        lastLoginAt: nowIso,
      };

      users[targetPhone] = createdUser;
      writeMockUsers(users);
      challenge.consumedAt = Date.now();
      writeChallenges(challenges);

      try {
        window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(createdUser));
      } catch {
        // Ignore storage errors
      }

      return {
        user: createdUser,
        isNewUser: false,
        csrfToken: 'mock-csrf-token',
      };
    }

    // New user verified OTP, now needs to provide displayName & consent
    const pendingUser = {
      id: existingUser?.id || generateId(),
      displayName: null,
      phoneE164: targetPhone,
      status: 'pending',
      countryCode: profile?.countryCode || 'IN',
      preferredLocale: profile?.preferredLocale || 'en',
      profileComplete: false,
      roles: getRolesForPhone(targetPhone),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    return {
      user: pendingUser,
      isNewUser: true,
      csrfToken: 'mock-csrf-token',
    };
  },

  async completeProfile({ phoneE164, displayName, preferredLocale, countryCode, consents }) {
    await delay(250);

    const nowIso = new Date().toISOString();
    const users = readMockUsers();
    const existing = phoneE164 ? users[phoneE164] : null;
    const resolvedPhone = phoneE164 || existing?.phoneE164;

    if (!resolvedPhone) {
      throw new ApiClientError({
        status: 401,
        code: 'unauthenticated',
        message: 'Phone verification session not found.',
      });
    }

    const completedUser = {
      id: existing?.id || generateId(),
      displayName: String(displayName || '').trim(),
      phoneE164: resolvedPhone,
      status: 'active',
      countryCode: countryCode || existing?.countryCode || 'IN',
      preferredLocale: preferredLocale || existing?.preferredLocale || 'en',
      profileComplete: true,
      consents: consents || {
        privacyNoticeVersion: '2026-10',
        dataProcessing: true,
        smsMessages: true,
        acceptedAt: nowIso,
      },
      roles: existing?.roles || getRolesForPhone(resolvedPhone),
      createdAt: existing?.createdAt || nowIso,
      updatedAt: nowIso,
      lastLoginAt: nowIso,
    };

    users[resolvedPhone] = completedUser;
    writeMockUsers(users);

    try {
      window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(completedUser));
    } catch {
      // Ignore storage errors
    }

    return {
      user: completedUser,
    };
  },

  async getSession() {
    try {
      const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
      if (!raw) return { user: null, csrfToken: null };
      const parsed = JSON.parse(raw);
      if (parsed && parsed.phoneE164 && parsed.displayName) {
        return { user: parsed, csrfToken: 'mock-csrf-token' };
      }
      return { user: null, csrfToken: null };
    } catch {
      return { user: null, csrfToken: null };
    }
  },

  async refreshSession() {
    return this.getSession();
  },

  async logout() {
    try {
      window.localStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      // Ignore storage errors
    }
  },
};

