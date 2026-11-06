/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { db } from '../db/db';
import { realAuthAdapter } from '../api/auth';
import { mockAuthAdapter, SESSION_STORAGE_KEY } from '../services/auth/mockAuthAdapter';
import { saveCountry } from '../services/landRegistry/registry';
import { AUTH_COUNTRY_STORAGE_KEY } from '../utils/phone';

const AuthContext = createContext(null);

const LEGACY_USER_KEY = 'fieldshift-user';
const DATA_OWNER_KEY = 'fieldshift-data-owner';
const USER_SCOPED_LOCAL_KEYS = [
  LEGACY_USER_KEY,
  SESSION_STORAGE_KEY,
  'fieldshift-role',
  'fieldshift-land-document',
  'fieldshift-weather-units',
  'fieldshift-reminders',
  DATA_OWNER_KEY,
];

export const IS_MOCK_AUTH = String(import.meta.env.VITE_USE_MOCKS ?? 'true').toLowerCase() === 'true';

function getAdapter() {
  return IS_MOCK_AUTH ? mockAuthAdapter : realAuthAdapter;
}

function readCachedSessionUser() {
  if (typeof window === 'undefined') return null;
  try {
    // Clean up any legacy email-based marker from older versions
    const legacy = window.localStorage.getItem(LEGACY_USER_KEY);
    if (legacy) {
      window.localStorage.removeItem(LEGACY_USER_KEY);
    }

    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && parsed.phoneE164 && parsed.displayName) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

function writeCachedSessionUser(user) {
  if (typeof window === 'undefined') return;
  try {
    if (user && user.phoneE164 && user.displayName) {
      window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(user));
    } else {
      window.localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  } catch {
    // Ignore storage errors
  }
}

async function clearUserDatabaseAndCaches() {
  try {
    await Promise.all([
      db.plots.clear(),
      db.soilRecords.clear(),
      db.weatherCache.clear(),
      db.syncQueue.clear(),
    ]);
  } catch (err) {
    console.warn('Could not clear Dexie tables:', err);
  }

  if (typeof window !== 'undefined') {
    try {
      USER_SCOPED_LOCAL_KEYS.forEach((key) => window.localStorage.removeItem(key));
      window.sessionStorage.removeItem('fieldshift_recommenderCached');
      window.sessionStorage.removeItem('fieldshift_startupNotifShown');
    } catch {
      // Ignore storage errors
    }
  }
}

export function userHasRole(user, roleCode) {
  if (!user || !Array.isArray(user.roles)) return false;
  return user.roles.some((role) => (typeof role === 'string' ? role : role?.code) === roleCode);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => readCachedSessionUser());
  const [status, setStatus] = useState(() => {
    const cached = readCachedSessionUser();
    if (IS_MOCK_AUTH || (typeof navigator !== 'undefined' && navigator.onLine === false)) {
      return cached ? 'authenticated' : 'anonymous';
    }
    return 'loading';
  }); // 'loading' | 'authenticated' | 'anonymous'
  const activeChallengeRef = useRef({
    challengeId: null,
    phoneE164: null,
    lastVerifiedCode: null,
  });

  const adapter = getAdapter();

  const activateAuthenticatedUser = useCallback(async (authenticatedUser) => {
    if (!authenticatedUser) {
      setUser(null);
      setStatus('anonymous');
      return;
    }

    if (typeof window !== 'undefined') {
      try {
        const previousOwner = window.localStorage.getItem(DATA_OWNER_KEY);
        if (previousOwner && previousOwner !== authenticatedUser.phoneE164) {
          await clearUserDatabaseAndCaches();
        }
        window.localStorage.setItem(DATA_OWNER_KEY, authenticatedUser.phoneE164);
        if (authenticatedUser.countryCode) {
          saveCountry(authenticatedUser.countryCode);
          window.localStorage.setItem(AUTH_COUNTRY_STORAGE_KEY, authenticatedUser.countryCode);
        }
      } catch {
        // Ignore storage errors
      }
    }

    writeCachedSessionUser(authenticatedUser);
    setUser(authenticatedUser);
    setStatus('authenticated');
  }, []);

  const refreshSession = useCallback(async () => {
    try {
      const cachedUser = readCachedSessionUser();

      if (IS_MOCK_AUTH) {
        if (cachedUser) {
          setUser(cachedUser);
          setStatus('authenticated');
        } else {
          setUser(null);
          setStatus('anonymous');
        }
        return;
      }

      // Offline startup: preserve already signed-in user so cached farm data remains accessible
      if (typeof navigator !== 'undefined' && navigator.onLine === false) {
        if (cachedUser) {
          setUser(cachedUser);
          setStatus('authenticated');
        } else {
          setUser(null);
          setStatus('anonymous');
        }
        return;
      }

      const data = await adapter.getSession();
      if (data?.user && data.user.displayName && data.user.profileComplete !== false) {
        await activateAuthenticatedUser(data.user);
      } else {
        writeCachedSessionUser(null);
        setUser(null);
        setStatus('anonymous');
      }
    } catch (error) {
      // If network error while offline or flaky connection, keep cached user signed in
      const cachedUser = readCachedSessionUser();
      if (cachedUser && (error?.code === 'network' || error?.code === 'timeout')) {
        setUser(cachedUser);
        setStatus('authenticated');
        return;
      }
      writeCachedSessionUser(null);
      setUser(null);
      setStatus('anonymous');
    }
  }, [activateAuthenticatedUser, adapter]);

  useEffect(() => {
    if (IS_MOCK_AUTH || (typeof navigator !== 'undefined' && navigator.onLine === false)) {
      return undefined;
    }
    let cancelled = false;
    adapter
      .getSession()
      .then(async (data) => {
        if (cancelled) return;
        if (data?.user && data.user.displayName && data.user.profileComplete !== false) {
          await activateAuthenticatedUser(data.user);
        } else {
          writeCachedSessionUser(null);
          setUser(null);
          setStatus('anonymous');
        }
      })
      .catch((error) => {
        if (cancelled) return;
        const cachedUser = readCachedSessionUser();
        if (cachedUser && (error?.code === 'network' || error?.code === 'timeout')) {
          setUser(cachedUser);
          setStatus('authenticated');
          return;
        }
        writeCachedSessionUser(null);
        setUser(null);
        setStatus('anonymous');
      });
    return () => {
      cancelled = true;
    };
  }, [activateAuthenticatedUser, adapter]);

  const requestOtp = useCallback(
    async (phoneE164, options = {}) => {
      const result = await adapter.requestOtp(phoneE164, options);
      activeChallengeRef.current = {
        challengeId: result.challengeId,
        phoneE164,
        lastVerifiedCode: null,
      };
      return result;
    },
    [adapter],
  );

  /**
   * Supports both:
   *   verifyOtp(phoneE164, code, profile?)
   * and:
   *   verifyOtp(code, profile?)
   */
  const verifyOtp = useCallback(
    async (phoneOrCode, codeOrProfile = undefined, maybeProfile = undefined) => {
      let phoneE164 = activeChallengeRef.current.phoneE164;
      let code;
      let profile;

      if (typeof phoneOrCode === 'string' && phoneOrCode.startsWith('+')) {
        phoneE164 = phoneOrCode;
        code = codeOrProfile;
        profile = maybeProfile || null;
      } else {
        code = phoneOrCode;
        profile = codeOrProfile && typeof codeOrProfile === 'object' ? codeOrProfile : null;
      }

      const challengeId = activeChallengeRef.current.challengeId;
      const result = await adapter.verifyOtp({
        challengeId,
        phoneE164,
        code,
        profile,
      });

      activeChallengeRef.current = {
        challengeId,
        phoneE164: result?.user?.phoneE164 || phoneE164,
        lastVerifiedCode: String(code || '').trim(),
      };

      const needsProfile = Boolean(
        result.isNewUser && (!profile || !String(profile.displayName || '').trim()),
      );

      if (!needsProfile && result.user) {
        await activateAuthenticatedUser(result.user);
      }

      return {
        ...result,
        isNewUser: needsProfile,
      };
    },
    [activateAuthenticatedUser, adapter],
  );

  const completeProfile = useCallback(
    async (profile) => {
      const { phoneE164, lastVerifiedCode, challengeId } = activeChallengeRef.current;

      if (IS_MOCK_AUTH && challengeId && lastVerifiedCode) {
        const result = await adapter.verifyOtp({
          challengeId,
          phoneE164,
          code: lastVerifiedCode,
          profile,
        });
        if (result?.user) {
          await activateAuthenticatedUser(result.user);
        }
        return result;
      }

      const result = await adapter.completeProfile({
        phoneE164,
        ...profile,
      });

      if (result?.user) {
        await activateAuthenticatedUser(result.user);
      }
      return result;
    },
    [activateAuthenticatedUser, adapter],
  );

  const getUnsyncedCount = useCallback(async () => {
    try {
      const pendingCount = await db.syncQueue.where('status').equals('pending').count();
      if (pendingCount > 0) return pendingCount;
      return await db.syncQueue.count();
    } catch {
      return 0;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await adapter.logout();
    } catch (err) {
      console.warn('Logout request error (continuing local cleanup):', err);
    }

    activeChallengeRef.current = {
      challengeId: null,
      phoneE164: null,
      lastVerifiedCode: null,
    };

    await clearUserDatabaseAndCaches();
    setUser(null);
    setStatus('anonymous');
  }, [adapter]);

  const hasRole = useCallback(
    (roleCode) => userHasRole(user, roleCode),
    [user],
  );

  const value = useMemo(
    () => ({
      user,
      status,
      isMock: IS_MOCK_AUTH,
      requestOtp,
      verifyOtp,
      completeProfile,
      logout,
      refreshSession,
      getUnsyncedCount,
      hasRole,
    }),
    [
      user,
      status,
      requestOtp,
      verifyOtp,
      completeProfile,
      logout,
      refreshSession,
      getUnsyncedCount,
      hasRole,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
