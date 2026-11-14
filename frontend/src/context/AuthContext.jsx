/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '../config/firebase';
import { db } from '../db/db';
import { realAuthAdapter } from '../api/auth';
import { mockAuthAdapter, SESSION_STORAGE_KEY } from '../services/auth/mockAuthAdapter';
import { saveCountry } from '../services/landRegistry/registry';
import { setAuthToken } from '../api/client';
import { drainSyncQueue } from '../api/sync';
import { syncPlotsWithServer } from '../api/plots';

const AuthContext = createContext(null);

const DATA_OWNER_KEY = 'fieldshift-data-owner';
const AUTH_COUNTRY_STORAGE_KEY = 'fieldshift-auth-country';
const USER_SCOPED_LOCAL_KEYS = [
  SESSION_STORAGE_KEY,
  'fieldshift-role',
  'fieldshift-land-document',
  'fieldshift-weather-units',
  'fieldshift-reminders',
  DATA_OWNER_KEY,
];

export const IS_MOCK_AUTH = String(import.meta.env.VITE_USE_MOCKS ?? 'false').toLowerCase() === 'true';

function getAdapter() {
  return IS_MOCK_AUTH ? mockAuthAdapter : realAuthAdapter;
}

function readCachedSessionUser() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && (parsed.email || parsed.uid || parsed.phoneE164) && parsed.displayName) {
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
    if (user && (user.email || user.uid) && user.displayName) {
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

  const adapter = getAdapter();

  const activateAuthenticatedUser = useCallback(async (authenticatedUser) => {
    if (!authenticatedUser) {
      setUser(null);
      setStatus('anonymous');
      return;
    }

    const ownerId = authenticatedUser.uid || authenticatedUser.email || authenticatedUser.id;

    if (typeof window !== 'undefined') {
      try {
        const previousOwner = window.localStorage.getItem(DATA_OWNER_KEY);
        if (previousOwner && previousOwner !== ownerId) {
          await clearUserDatabaseAndCaches();
        }
        if (ownerId) {
          window.localStorage.setItem(DATA_OWNER_KEY, ownerId);
        }
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

    if (typeof navigator !== 'undefined' && navigator.onLine) {
      Promise.all([drainSyncQueue(), syncPlotsWithServer()]).catch((err) => {
        console.warn('Background sync on login failed:', err);
      });
    }
  }, []);

  // Listen to Firebase auth state changes in production & non-mock mode
  useEffect(() => {
    if (IS_MOCK_AUTH) {
      return undefined;
    }

    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        const token = await firebaseUser.getIdToken();
        setAuthToken(token);
        const authUser = {
          id: firebaseUser.uid,
          uid: firebaseUser.uid,
          email: firebaseUser.email,
          displayName:
            firebaseUser.displayName ||
            (firebaseUser.email ? firebaseUser.email.split('@')[0] : 'Farmer'),
          preferredLocale:
            (typeof window !== 'undefined' && window.localStorage.getItem('fieldshift-language')) ||
            'en',
          village: '',
          countryCode: 'IN',
          profileComplete: true,
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
        await activateAuthenticatedUser(authUser);
      } else {
        const cached = readCachedSessionUser();
        // If offline, preserve cached user so offline farm data remains accessible
        if (cached && typeof navigator !== 'undefined' && navigator.onLine === false) {
          setUser(cached);
          setStatus('authenticated');
        } else if (cached?.isDemo) {
          setUser(cached);
          setStatus('authenticated');
        } else {
          writeCachedSessionUser(null);
          setUser(null);
          setStatus('anonymous');
        }
      }
    });

    return () => {
      unsubscribe();
    };
  }, [activateAuthenticatedUser]);

  const login = useCallback(
    async (email, password) => {
      const result = await adapter.login(email, password);
      if (result?.user) {
        await activateAuthenticatedUser(result.user);
      }
      return result;
    },
    [activateAuthenticatedUser, adapter],
  );

  const signup = useCallback(
    async (email, password, displayName, profileOptions = {}) => {
      const result = await adapter.signup(email, password, displayName, profileOptions);
      if (result?.user) {
        await activateAuthenticatedUser(result.user);
      }
      return result;
    },
    [activateAuthenticatedUser, adapter],
  );

  const resetPassword = useCallback(
    async (email) => {
      return adapter.resetPassword(email);
    },
    [adapter],
  );

  const loginWithDemo = useCallback(async () => {
    const result = await mockAuthAdapter.login('demo@fieldshift.org', 'demo1234');
    if (result?.user) {
      await activateAuthenticatedUser(result.user);
    }
    return result;
  }, [activateAuthenticatedUser]);

  const logout = useCallback(async () => {
    try {
      await adapter.logout();
    } catch (err) {
      console.warn('Logout request error (continuing local cleanup):', err);
    }

    await clearUserDatabaseAndCaches();
    setUser(null);
    setStatus('anonymous');
  }, [adapter]);

  const refreshSession = useCallback(async () => {
    try {
      const cachedUser = readCachedSessionUser();
      if (cachedUser) {
        setUser(cachedUser);
        setStatus('authenticated');
      } else {
        setUser(null);
        setStatus('anonymous');
      }
    } catch {
      setUser(null);
      setStatus('anonymous');
    }
  }, []);

  const getUnsyncedCount = useCallback(async () => {
    try {
      const pendingCount = await db.syncQueue.where('status').equals('pending').count();
      if (pendingCount > 0) return pendingCount;
      return await db.syncQueue.count();
    } catch {
      return 0;
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const handleOnline = () => {
      if (status === 'authenticated') {
        Promise.all([drainSyncQueue(), syncPlotsWithServer()]).catch((err) => {
          console.warn('Online sync failed:', err);
        });
      }
    };

    window.addEventListener('online', handleOnline);
    return () => {
      window.removeEventListener('online', handleOnline);
    };
  }, [status]);

  const syncNow = useCallback(async () => {
    if (IS_MOCK_AUTH) return { synced: 0, failed: 0, skipped: 0 };
    const [syncStats] = await Promise.all([drainSyncQueue(), syncPlotsWithServer()]);
    return syncStats;
  }, []);

  const hasRole = useCallback(
    (roleCode) => userHasRole(user, roleCode),
    [user],
  );

  const value = useMemo(
    () => ({
      user,
      status,
      isMock: IS_MOCK_AUTH,
      login,
      signup,
      resetPassword,
      loginWithDemo,
      logout,
      refreshSession,
      getUnsyncedCount,
      syncNow,
      hasRole,
    }),
    [
      user,
      status,
      login,
      signup,
      resetPassword,
      loginWithDemo,
      logout,
      refreshSession,
      getUnsyncedCount,
      syncNow,
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
