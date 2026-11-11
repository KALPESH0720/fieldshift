import { apiRequest, getAuthToken, setAuthToken, setCsrfToken } from './client';

function formatFarmerUser(farmer, phoneFallback = '') {
  if (!farmer) return null;
  return {
    id: farmer.id,
    phoneE164: farmer.phone || phoneFallback,
    displayName: farmer.name || '',
    preferredLocale: farmer.language || 'en',
    village: farmer.village || '',
    countryCode: 'IN',
    profileComplete: Boolean(farmer.name && farmer.name.trim()),
    roles: [
      {
        code: 'farmer',
        scope: 'global',
        groupId: null,
        permissions: ['plots:read', 'plots:write', 'soil:read', 'soil:write'],
      },
      {
        code: 'extension',
        scope: 'group',
        groupId: 'fpo-dicholi-01',
        permissions: ['group:read', 'farmers:read'],
      },
    ],
  };
}

export const realAuthAdapter = {
  async requestOtp(phoneE164) {
    const data = await apiRequest('/auth/otp/send', {
      method: 'POST',
      body: {
        phone: phoneE164,
      },
    });

    return {
      challengeId: phoneE164,
      expiresInSeconds: 300,
      resendAfterSeconds: 60,
      voiceAvailable: false,
      developmentOtp: data?.development_otp || null,
    };
  },

  async verifyOtp({ challengeId, phoneE164, code, profile = null }) {
    const phone = phoneE164 || challengeId;
    const data = await apiRequest('/auth/otp/verify', {
      method: 'POST',
      body: {
        phone,
        otp: String(code || '').trim(),
      },
    });

    if (data?.access_token) {
      setAuthToken(data.access_token);
    }
    if (data?.csrfToken) {
      setCsrfToken(data.csrfToken);
    }

    let farmer = null;
    let isNewUser = false;

    try {
      farmer = await apiRequest('/farmers/me', { method: 'GET' });
    } catch (err) {
      if (err.status === 404) {
        isNewUser = true;
      } else {
        throw err;
      }
    }

    if (farmer) {
      isNewUser = !farmer.name || !farmer.name.trim();
      return {
        user: formatFarmerUser(farmer, phone),
        isNewUser,
        csrfToken: data?.csrfToken || null,
      };
    }

    // Farmer record doesn't exist yet (404)
    if (profile && profile.displayName && profile.displayName.trim()) {
      farmer = await apiRequest('/farmers/me', {
        method: 'POST',
        body: {
          name: String(profile.displayName).trim(),
          language: profile.preferredLocale || 'en',
          village: profile.village || null,
        },
      });
      return {
        user: formatFarmerUser(farmer, phone),
        isNewUser: false,
        csrfToken: data?.csrfToken || null,
      };
    }

    return {
      user: {
        id: null,
        phoneE164: phone,
        displayName: '',
        preferredLocale: profile?.preferredLocale || 'en',
        village: '',
        countryCode: 'IN',
        profileComplete: false,
        roles: [],
      },
      isNewUser: true,
      csrfToken: data?.csrfToken || null,
    };
  },

  async completeProfile({ phoneE164, displayName, preferredLocale, village }) {
    let farmer = null;
    const body = {
      name: String(displayName || '').trim(),
      language: preferredLocale || 'en',
      village: village || null,
    };

    try {
      farmer = await apiRequest('/farmers/me', {
        method: 'PATCH',
        body,
      });
    } catch (err) {
      if (err.status === 404) {
        farmer = await apiRequest('/farmers/me', {
          method: 'POST',
          body,
        });
      } else {
        throw err;
      }
    }

    return {
      user: formatFarmerUser(farmer, phoneE164),
    };
  },

  async getSession() {
    const token = getAuthToken();
    if (!token) {
      return { user: null, csrfToken: null };
    }

    try {
      const farmer = await apiRequest('/farmers/me', { method: 'GET' });
      return {
        user: formatFarmerUser(farmer),
        csrfToken: null,
      };
    } catch (err) {
      if (err.status === 401 || err.status === 404) {
        setAuthToken(null);
        return { user: null, csrfToken: null };
      }
      throw err;
    }
  },

  async refreshSession() {
    return this.getSession();
  },

  async logout() {
    setAuthToken(null);
    setCsrfToken(null);
  },
};
