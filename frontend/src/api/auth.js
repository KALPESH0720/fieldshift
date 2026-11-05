/*
 * FieldShift frontend: Authentication API Adapter
 * Feature: Provides the real backend interface for account login, session creation, and user profile operations used by the auth system.
 * Impact: This adapter connects the app to the backend identity layer and keeps authentication logic separated from UI code.
 * Importance: Security and session continuity depend on this layer because it is the path between the farmer dashboard and authenticated services.
 */

import { apiRequest, setCsrfToken } from './client';

export const realAuthAdapter = {
  async requestOtp(phoneE164, { channel = 'sms', locale = 'en' } = {}) {
    const data = await apiRequest('/auth/otp/request', {
      method: 'POST',
      body: {
        phoneE164,
        purpose: 'login',
        ...(channel !== 'sms' ? { channel } : {}),
        ...(locale ? { locale } : {}),
      },
    });

    return {
      challengeId: data.challengeId,
      expiresInSeconds: data.expiresInSeconds ?? 300,
      resendAfterSeconds: data.resendAfterSeconds ?? 30,
      voiceAvailable: Boolean(data.voiceAvailable),
    };
  },

  async verifyOtp({ challengeId, phoneE164, code, profile = null }) {
    const payload = {
      challengeId,
      code: String(code || '').trim(),
    };

    if (profile && profile.displayName) {
      payload.profile = {
        displayName: String(profile.displayName).trim(),
        preferredLocale: profile.preferredLocale || 'en',
        countryCode: profile.countryCode || 'IN',
        ...(profile.consents ? { consents: profile.consents } : {}),
      };
    }

    const data = await apiRequest('/auth/otp/verify', {
      method: 'POST',
      body: payload,
    });

    if (data?.csrfToken) {
      setCsrfToken(data.csrfToken);
    }

    const user = data?.user || null;
    const isNewUser = Boolean(
      data?.isNewUser ?? (user && (!user.displayName || user.status === 'pending' || user.profileComplete === false)),
    );

    return {
      user: user ? { ...user, phoneE164: user.phoneE164 || phoneE164 } : null,
      isNewUser,
      csrfToken: data?.csrfToken || null,
    };
  },

  async completeProfile({ displayName, preferredLocale, countryCode, consents }) {
    const data = await apiRequest('/me', {
      method: 'PATCH',
      body: {
        displayName: String(displayName || '').trim(),
        preferredLocale: preferredLocale || 'en',
        countryCode: countryCode || 'IN',
        ...(consents ? { consents } : {}),
      },
    });

    return {
      user: data?.user || data,
    };
  },

  async getSession() {
    const data = await apiRequest('/me', { method: 'GET' });
    if (data?.csrfToken) {
      setCsrfToken(data.csrfToken);
    }
    return {
      user: data?.user || null,
      csrfToken: data?.csrfToken || null,
    };
  },

  async refreshSession() {
    const data = await apiRequest('/auth/refresh', {
      method: 'POST',
      skipAuthRefresh: true,
    });
    if (data?.csrfToken) {
      setCsrfToken(data.csrfToken);
    }
    return {
      user: data?.user || null,
      csrfToken: data?.csrfToken || null,
    };
  },

  async logout() {
    try {
      await apiRequest('/auth/logout', {
        method: 'POST',
        skipAuthRefresh: true,
      });
    } finally {
      setCsrfToken(null);
    }
  },
};

