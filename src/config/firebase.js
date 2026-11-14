import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getAnalytics, isSupported } from 'firebase/analytics';

// Web app Firebase configuration
export const firebaseConfig = {
  apiKey: "AIzaSyDt_TreQ_ZUCx1AxhBmSHS_Z1nDoSPTC60",
  authDomain: "fieldshift-8778f.firebaseapp.com",
  projectId: "fieldshift-8778f",
  storageBucket: "fieldshift-8778f.firebasestorage.app",
  messagingSenderId: "558567311949",
  appId: "1:558567311949:web:15a7e5ffb64630e7d8ea04",
  measurementId: "G-6XMZ1DTE3E"
};

// Initialize Firebase app singleton
export const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);

// Initialize Firebase Authentication
export const auth = getAuth(app);

// Initialize Firebase Analytics (safe for non-browser / unsupported environments)
export const analyticsPromise = typeof window !== 'undefined'
  ? isSupported().then((supported) => (supported ? getAnalytics(app) : null)).catch(() => null)
  : Promise.resolve(null);

export default app;
