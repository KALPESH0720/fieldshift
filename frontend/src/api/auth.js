import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  updateProfile,
  signOut,
  sendPasswordResetEmail,
} from 'firebase/auth';
import { auth } from '../config/firebase';
import { setAuthToken, setCsrfToken, apiRequest } from './client';

function formatFarmerUser(firebaseUser, extra = {}) {
  if (!firebaseUser) return null;
  return {
    id: firebaseUser.uid,
    uid: firebaseUser.uid,
    email: firebaseUser.email,
    displayName:
      firebaseUser.displayName ||
      extra.name ||
      (firebaseUser.email ? firebaseUser.email.split('@')[0] : 'Farmer'),
    preferredLocale: extra.language || 'en',
    village: extra.village || '',
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
}

export const realAuthAdapter = {
  async login(email, password) {
    const userCredential = await signInWithEmailAndPassword(auth, email, password);
    const idToken = await userCredential.user.getIdToken();
    setAuthToken(idToken);

    let farmer = null;
    try {
      farmer = await apiRequest('/farmers/me', { method: 'GET' });
    } catch {
      // Backend may be offline or in mock mode; continue with Firebase profile
    }

    return {
      user: formatFarmerUser(userCredential.user, farmer || {}),
      csrfToken: null,
    };
  },

  async signup(email, password, displayName, profileOptions = {}) {
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    if (displayName && displayName.trim()) {
      await updateProfile(userCredential.user, {
        displayName: displayName.trim(),
      });
    }

    const idToken = await userCredential.user.getIdToken();
    setAuthToken(idToken);

    let farmer = null;
    try {
      farmer = await apiRequest('/farmers/me', {
        method: 'POST',
        body: {
          name: String(displayName || '').trim() || (email ? email.split('@')[0] : 'Farmer'),
          language: profileOptions.preferredLocale || 'en',
          village: profileOptions.village || null,
        },
      });
    } catch {
      // Backend may be optional; continue
    }

    return {
      user: formatFarmerUser(
        userCredential.user,
        farmer || { name: displayName, language: profileOptions.preferredLocale },
      ),
      csrfToken: null,
    };
  },

  async resetPassword(email) {
    await sendPasswordResetEmail(auth, email);
    return { success: true };
  },

  async getSession() {
    const currentUser = auth.currentUser;
    if (!currentUser) {
      return { user: null, csrfToken: null };
    }

    const idToken = await currentUser.getIdToken();
    setAuthToken(idToken);

    let farmer = null;
    try {
      farmer = await apiRequest('/farmers/me', { method: 'GET' });
    } catch {
      // Backend optional
    }

    return {
      user: formatFarmerUser(currentUser, farmer || {}),
      csrfToken: null,
    };
  },

  async refreshSession() {
    return this.getSession();
  },

  async logout() {
    try {
      await signOut(auth);
    } catch (err) {
      console.warn('Firebase signOut error:', err);
    }
    setAuthToken(null);
    setCsrfToken(null);
  },
};
