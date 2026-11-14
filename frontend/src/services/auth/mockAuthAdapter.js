import { ApiClientError } from '../../api/client';

export const SESSION_STORAGE_KEY = 'fieldshift-session';
export const MOCK_USERS_STORAGE_KEY = 'fieldshift-mock-users';

const MOCK_DELAY_MS = 300;

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

function getRolesForUser() {
  return [
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
  ];
}

function ensureMockUserRoles(user) {
  if (!user || typeof user !== 'object') return user;
  const existingRoles = Array.isArray(user.roles) ? user.roles : [];
  const hasFarmer = existingRoles.some(
    (r) => (typeof r === 'string' ? r : r?.code) === 'farmer',
  );
  const hasExtension = existingRoles.some(
    (r) => (typeof r === 'string' ? r : r?.code) === 'extension',
  );
  if (hasFarmer && hasExtension) return user;
  return {
    ...user,
    roles: getRolesForUser(),
  };
}

export const mockAuthAdapter = {
  async login(email, password) {
    await delay();

    const normalizedEmail = String(email || '').trim().toLowerCase();
    if (!normalizedEmail) {
      throw new ApiClientError({
        status: 400,
        code: 'email_required',
        message: 'Email is required',
      });
    }

    if (normalizedEmail === 'demo@fieldshift.org' && password === 'demo1234') {
      const demoUser = {
        id: 'mock-demo-farmer-01',
        uid: 'mock-demo-farmer-01',
        email: 'demo@fieldshift.org',
        displayName: 'Demo Farmer',
        preferredLocale: 'en',
        countryCode: 'IN',
        profileComplete: true,
        roles: getRolesForUser(),
        isDemo: true,
      };
      try {
        window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(demoUser));
      } catch {
        // Ignore storage errors
      }
      return { user: demoUser, csrfToken: 'mock-csrf-token' };
    }

    const users = readMockUsers();
    const existing = users[normalizedEmail];

    if (!existing || existing.password !== password) {
      throw new ApiClientError({
        status: 401,
        code: 'invalid_credentials',
        message: 'Invalid email or password.',
      });
    }

    const hydrated = ensureMockUserRoles(existing);
    hydrated.lastLoginAt = new Date().toISOString();
    users[normalizedEmail] = hydrated;
    writeMockUsers(users);

    const safeUser = { ...hydrated };
    delete safeUser.password;

    try {
      window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(safeUser));
    } catch {
      // Ignore storage errors
    }

    return { user: safeUser, csrfToken: 'mock-csrf-token' };
  },

  async signup(email, password, displayName, profileOptions = {}) {
    await delay();

    const normalizedEmail = String(email || '').trim().toLowerCase();
    if (!normalizedEmail) {
      throw new ApiClientError({
        status: 400,
        code: 'email_required',
        message: 'Email is required',
      });
    }
    if (!password || password.length < 6) {
      throw new ApiClientError({
        status: 400,
        code: 'weak_password',
        message: 'Password must be at least 6 characters.',
      });
    }

    const users = readMockUsers();
    if (users[normalizedEmail]) {
      throw new ApiClientError({
        status: 409,
        code: 'email_in_use',
        message: 'An account with this email already exists.',
      });
    }

    const nowIso = new Date().toISOString();
    const newUser = {
      id: generateId(),
      uid: generateId(),
      email: normalizedEmail,
      displayName: String(displayName || '').trim() || normalizedEmail.split('@')[0],
      password,
      preferredLocale: profileOptions.preferredLocale || 'en',
      countryCode: profileOptions.countryCode || 'IN',
      profileComplete: true,
      roles: getRolesForUser(),
      createdAt: nowIso,
      updatedAt: nowIso,
      lastLoginAt: nowIso,
    };

    users[normalizedEmail] = newUser;
    writeMockUsers(users);

    const safeUser = { ...newUser };
    delete safeUser.password;

    try {
      window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(safeUser));
    } catch {
      // Ignore storage errors
    }

    return { user: safeUser, csrfToken: 'mock-csrf-token' };
  },

  async resetPassword(email) {
    await delay();
    const normalizedEmail = String(email || '').trim().toLowerCase();
    if (!normalizedEmail) {
      throw new ApiClientError({
        status: 400,
        code: 'email_required',
        message: 'Email is required',
      });
    }
    return { success: true };
  },

  async getSession() {
    try {
      const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
      if (!raw) return { user: null, csrfToken: null };
      const parsed = JSON.parse(raw);
      if (parsed && (parsed.email || parsed.uid) && parsed.displayName) {
        const hydratedUser = ensureMockUserRoles(parsed);
        if (hydratedUser !== parsed) {
          window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(hydratedUser));
        }
        return { user: hydratedUser, csrfToken: 'mock-csrf-token' };
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
