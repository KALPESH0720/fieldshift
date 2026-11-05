/*
 * FieldShift frontend: Application Shell
 * Feature: Coordinates the app-wide routing, authenticated session flow, role switching, theme handling, and bottom navigation for the FieldShift farmer experience.
 * Impact: This is the central orchestration layer that keeps every feature screen connected to the same user context, permissions, and navigation state.
 * Importance: It is the backbone of the frontend and determines how the product feels as a unified experience across dashboards, recommendations, and field management tools.
 */

import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  NavLink,
  useLocation,
  useNavigate,
  Link,
  Navigate,
} from 'react-router-dom';
import PlotList from './components/PlotList';
import GroupDashboard from './components/GroupDashboard';
import Recommender from './components/Recommender';
import Settings from './components/Settings';
import SoilImport from './components/SoilImport';
import MarketInsights from './components/MarketInsights';
import PestScanner from './components/PestScanner';
import NotFound from './components/NotFound';
import SchemesHub from './components/SchemesHub';
import AuthLayout from './layouts/AuthLayout';
import Login from './components/auth/Login';
import InstallPrompt from './components/InstallPrompt';
import {
  Sprout,
  Sparkles,
  FlaskConical,
  TrendingUp,
  Bug,
  Settings as SettingsIcon,
  Sun,
  Moon,
  UsersRound,
  Landmark,
  User,
  UserX,
  LogOut,
} from 'lucide-react';
import { useTheme } from './context/ThemeContext';
import { useTranslation } from './context/LanguageContext';
import { useRole } from './context/RoleContext';
import { useAuth } from './context/AuthContext';
import { maskPhoneE164 } from './utils/phone';
import useVoice, { stopAllSpeech } from './hooks/useVoice';

// Lazy-load LandingPage and MarketCropDetail
const LandingPage = lazy(() => import('./components/LandingPage'));
const MarketCropDetail = lazy(() => import('./components/MarketCropDetail'));

/* ─── Bottom navigation ─────────────────────────────────────── */
const NAV_TABS = [
  { to: '/farm',        key: 'farm',    Icon: Sprout,       active: 'text-emerald-700 bg-emerald-50' },
  { to: '/recommender', key: 'suggest', Icon: Sparkles,     active: 'text-emerald-700 bg-emerald-50' },
  { to: '/soil',        key: 'soil',    Icon: FlaskConical, active: 'text-violet-700 bg-violet-50'   },
  { to: '/market',      key: 'market',  Icon: TrendingUp,   active: 'text-blue-700 bg-blue-50'       },
  { to: '/pest',        key: 'scan',    Icon: Bug,          active: 'text-rose-700 bg-rose-50'       },
  { to: '/schemes',     key: 'schemes', Icon: Landmark,     active: 'text-amber-700 bg-amber-50'     },
];

function NavigationBar() {
  const { t } = useTranslation();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200/90 bg-white/95 px-2 py-1.5 shadow-lg backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/95">
      <div className="mx-auto flex max-w-lg items-center justify-around">
        {NAV_TABS.map(({ to, key, Icon, active }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 py-1.5 px-3 rounded-2xl transition-all duration-150 min-h-[48px] justify-center ${
                isActive
                  ? `${active} font-bold dark:text-emerald-300 dark:bg-emerald-950`
                  : 'font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'
              }`
            }
          >
            <Icon size={20} />
            <span className="min-w-0 max-w-20 truncate text-[10px] leading-tight">
              {t(`nav.${key}`)}
            </span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

/* ─── Skeleton shown while session is bootstrapping ─────────── */
function SessionSkeleton() {
  const { t } = useTranslation();
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label={t('auth.sessionLoading')}
      className="min-h-screen bg-slate-50 p-4 dark:bg-slate-950 sm:p-6"
    >
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex items-center justify-between border-b border-slate-200 pb-4 dark:border-slate-800">
          <div className="h-6 w-36 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
          <div className="flex gap-2">
            <div className="h-9 w-28 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
            <div className="h-9 w-9 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((idx) => (
            <div
              key={idx}
              className="h-28 animate-pulse rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
            />
          ))}
        </div>
        <div className="h-72 animate-pulse rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900" />
      </div>
    </div>
  );
}

/* ─── Shared app header with masked phone menu & Settings gear ─ */
function AppHeader({
  title,
  isDarkMode,
  onToggleTheme,
  userRole,
  onToggleRole,
  canSwitchToExtension,
}) {
  const { t } = useTranslation();
  const { user, logout, getUnsyncedCount, isMock } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [unsyncedCount, setUnsyncedCount] = useState(0);
  const menuRef = useRef(null);

  const maskedPhone = maskPhoneE164(user?.phoneE164);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const handleOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
        setUnsyncedCount(0);
      }
    };
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        setUnsyncedCount(0);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    window.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      window.removeEventListener('keydown', handleEscape);
    };
  }, [menuOpen]);

  const handleSwitchOrLogout = async (force = false) => {
    if (!force) {
      const pending = await getUnsyncedCount();
      if (pending > 0) {
        setUnsyncedCount(pending);
        return;
      }
    }
    setUnsyncedCount(0);
    setMenuOpen(false);
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="sticky top-0 z-50 flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] dark:border-slate-800 dark:bg-slate-900 sm:px-6">
      <div className="flex min-w-0 items-center gap-1.5 sm:gap-2">
        <span className="truncate text-sm font-black tracking-tight text-slate-900 dark:text-white sm:text-base">
          {title}
        </span>
        {isMock && (
          <span className="shrink-0 rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider text-amber-900 dark:border-amber-500/40 dark:bg-amber-950 dark:text-amber-200">
            {t('auth.demoBadge')}
          </span>
        )}
      </div>

      <div className="flex items-center gap-1.5 sm:gap-2">
        {/* Farmer / Extension toggle — visible on mobile & desktop when user has extension role */}
        {canSwitchToExtension && (
          <div
            className="flex items-center rounded-xl border border-slate-200 bg-slate-50 p-1 dark:border-slate-700 dark:bg-slate-800"
            role="group"
            aria-label={t('header.demoRole')}
          >
            <button
              type="button"
              onClick={() => onToggleRole('farmer')}
              aria-pressed={userRole === 'farmer'}
              className={`rounded-lg px-2 py-1 text-[11px] font-bold transition sm:px-2.5 sm:py-1.5 sm:text-xs ${
                userRole === 'farmer'
                  ? 'bg-white text-emerald-700 shadow-sm dark:bg-slate-700 dark:text-emerald-300'
                  : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              {t('header.farmer')}
            </button>
            <button
              type="button"
              onClick={() => onToggleRole('extension')}
              aria-pressed={userRole === 'extension'}
              className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-bold transition sm:px-2.5 sm:py-1.5 sm:text-xs ${
                userRole === 'extension'
                  ? 'bg-white text-emerald-700 shadow-sm dark:bg-slate-700 dark:text-emerald-300'
                  : 'text-slate-500 dark:text-slate-400'
              }`}
            >
              <UsersRound size={13} />
              {t('header.extension')}
            </button>
          </div>
        )}

        {/* Header Account Menu showing Masked Phone Number */}
        {user && (
          <div ref={menuRef} className="relative">
            <button
              type="button"
              id="header-account-menu-btn"
              onClick={() => {
                setMenuOpen((prev) => !prev);
                setUnsyncedCount(0);
              }}
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-2.5 text-xs font-bold text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              <User size={14} className="text-emerald-600 dark:text-emerald-400" />
              <span dir="ltr" className="hidden xs:inline sm:inline">
                {maskedPhone}
              </span>
            </button>

            {menuOpen && (
              <div
                role="menu"
                className="absolute end-0 top-full z-50 mt-2 w-64 rounded-2xl border border-slate-200 bg-white p-3 shadow-xl dark:border-slate-700 dark:bg-slate-900"
              >
                <div className="border-b border-slate-100 pb-2.5 dark:border-slate-800">
                  <p className="truncate text-sm font-extrabold text-slate-900 dark:text-white">
                    {user.displayName}
                  </p>
                  <p
                    dir="ltr"
                    className="mt-0.5 text-xs font-semibold text-slate-500 dark:text-slate-400"
                  >
                    {maskedPhone}
                  </p>
                </div>

                {unsyncedCount > 0 ? (
                  <div
                    role="alert"
                    className="mt-2.5 rounded-xl border border-red-200 bg-red-50 p-2.5 text-xs font-semibold text-red-900 dark:border-red-800 dark:bg-red-950/60 dark:text-red-200"
                  >
                    <p>{t('settings.unsyncedLogoutWarning', { count: unsyncedCount })}</p>
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        onClick={() => handleSwitchOrLogout(true)}
                        className="rounded-lg bg-red-600 px-2.5 py-1.5 text-xs font-bold text-white hover:bg-red-500"
                      >
                        {t('settings.confirmLogout')}
                      </button>
                      <button
                        type="button"
                        onClick={() => setUnsyncedCount(0)}
                        className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-bold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                      >
                        {t('common.cancel')}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-2 space-y-1">
                    <Link
                      to="/settings"
                      role="menuitem"
                      onClick={() => setMenuOpen(false)}
                      className="flex min-h-10 w-full items-center gap-2 rounded-xl px-2.5 py-2 text-xs font-bold text-slate-700 transition hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                      <SettingsIcon size={15} />
                      <span>{t('header.settings')}</span>
                    </Link>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => handleSwitchOrLogout(false)}
                      className="flex min-h-10 w-full items-center gap-2 rounded-xl px-2.5 py-2 text-xs font-bold text-amber-700 transition hover:bg-amber-50 dark:text-amber-300 dark:hover:bg-amber-950/40"
                    >
                      <UserX size={15} />
                      <span>{t('auth.notYouSwitch')}</span>
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => handleSwitchOrLogout(false)}
                      className="flex min-h-10 w-full items-center gap-2 rounded-xl px-2.5 py-2 text-xs font-bold text-red-600 transition hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/40"
                    >
                      <LogOut size={15} />
                      <span>{t('settings.logOut')}</span>
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <button
          type="button"
          onClick={onToggleTheme}
          aria-label={isDarkMode ? t('header.lightMode') : t('header.darkMode')}
          title={isDarkMode ? t('header.lightMode') : t('header.darkMode')}
          className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white"
        >
          {isDarkMode ? <Sun size={19} /> : <Moon size={19} />}
        </button>

        <Link
          to="/settings"
          aria-label={t('header.settings')}
          className="flex h-9 w-9 items-center justify-center rounded-xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white"
        >
          <SettingsIcon size={20} />
        </Link>
      </div>
    </header>
  );
}

function DashboardFrame({
  title,
  children,
  isDarkMode,
  onToggleTheme,
  userRole,
  onToggleRole,
  canSwitchToExtension,
}) {
  return (
    <div className="min-h-screen">
      <AppHeader
        title={title}
        isDarkMode={isDarkMode}
        onToggleTheme={onToggleTheme}
        userRole={userRole}
        onToggleRole={onToggleRole}
        canSwitchToExtension={canSwitchToExtension}
      />
      {children}
    </div>
  );
}

/* ─── Route Guard for all authenticated screens ─────────────── */
function ProtectedRoute({ children }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return <SessionSkeleton />;
  }

  if (status !== 'authenticated') {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

function App() {
  return (
    <Router>
      <AppShell />
    </Router>
  );
}

function VoiceNoticeBanner() {
  const { t } = useTranslation();
  const { notice, clearNotice } = useVoice();
  if (!notice) return null;

  return (
    <div
      className="fixed bottom-24 left-1/2 z-[100] w-[min(92vw,32rem)] -translate-x-1/2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950 shadow-lg dark:border-amber-700/70 dark:bg-slate-900 dark:text-amber-100"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="leading-relaxed">{notice}</span>
        <button
          type="button"
          onClick={clearNotice}
          className="shrink-0 font-bold text-amber-900 underline underline-offset-2 dark:text-amber-200"
        >
          {t('voice.dismiss')}
        </button>
      </div>
    </div>
  );
}

function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { resolvedTheme, toggleTheme } = useTheme();
  const { t, isLoading, languageError } = useTranslation();
  const { status } = useAuth();
  const isDarkMode = resolvedTheme === 'dark';
  const { role: userRole, setRole: setUserRole, canSwitchToExtension } = useRole();

  useEffect(() => {
    stopAllSpeech();
  }, [location.pathname]);

  const isAuthRoute = ['/', '/login', '/signup', '/forgot-password'].includes(location.pathname);

  const handleRoleChange = (role) => {
    setUserRole(role);
    if (location.pathname === '/farm' || location.pathname === '/group') {
      navigate(role === 'extension' ? '/group' : '/farm');
    }
  };

  return (
    <div
      className={`${
        isAuthRoute
          ? 'min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100'
          : 'min-h-screen bg-slate-50 pb-16 dark:bg-slate-950'
      } transition-colors duration-300`}
    >
      {isLoading && (
        <div
          className="fixed inset-x-0 top-0 z-[70] h-0.5 animate-pulse bg-emerald-500"
          role="status"
          aria-label={t('common.loading')}
        />
      )}
      {languageError && (
        <div
          className="fixed inset-x-3 top-3 z-[70] mx-auto max-w-md rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900 shadow-lg dark:border-amber-500/60 dark:bg-amber-950 dark:text-amber-100"
          role="status"
        >
          {t('common.languageLoadError')}
        </div>
      )}

      <Routes>
        {/* Landing Page (lazy-loaded so 3D/Spline assets never load on /login) */}
        <Route
          path="/"
          element={
            <Suspense fallback={<SessionSkeleton />}>
              <LandingPage />
            </Suspense>
          }
        />

        {/* Protected App Screens */}
        <Route
          path="/farm"
          element={
            <ProtectedRoute>
              <DashboardFrame
                title={userRole === 'farmer' ? t('screenTitles.farm') : t('screenTitles.group')}
                isDarkMode={isDarkMode}
                userRole={userRole}
                onToggleRole={handleRoleChange}
                onToggleTheme={toggleTheme}
                canSwitchToExtension={canSwitchToExtension}
              >
                {userRole === 'farmer' ? <PlotList /> : <GroupDashboard />}
              </DashboardFrame>
            </ProtectedRoute>
          }
        />
        <Route
          path="/group"
          element={
            <ProtectedRoute>
              {canSwitchToExtension ? (
                <DashboardFrame
                  title={t('screenTitles.group')}
                  isDarkMode={isDarkMode}
                  userRole={userRole}
                  onToggleRole={handleRoleChange}
                  onToggleTheme={toggleTheme}
                  canSwitchToExtension={canSwitchToExtension}
                >
                  <GroupDashboard />
                </DashboardFrame>
              ) : (
                <Navigate to="/farm" replace />
              )}
            </ProtectedRoute>
          }
        />
        <Route
          path="/recommender"
          element={
            <ProtectedRoute>
              <Recommender />
            </ProtectedRoute>
          }
        />
        <Route
          path="/soil"
          element={
            <ProtectedRoute>
              <SoilImport />
            </ProtectedRoute>
          }
        />
        <Route
          path="/market"
          element={
            <ProtectedRoute>
              <MarketInsights />
            </ProtectedRoute>
          }
        />
        <Route
          path="/market/:cropId"
          element={
            <ProtectedRoute>
              <Suspense fallback={<SessionSkeleton />}>
                <MarketCropDetail />
              </Suspense>
            </ProtectedRoute>
          }
        />
        <Route
          path="/pest"
          element={
            <ProtectedRoute>
              <PestScanner />
            </ProtectedRoute>
          }
        />
        <Route
          path="/schemes"
          element={
            <ProtectedRoute>
              <SchemesHub />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Settings />
            </ProtectedRoute>
          }
        />

        {/* Single Auth Entry (/login) + Redirects from legacy routes */}
        <Route
          path="/login"
          element={
            <AuthLayout>
              <Login />
            </AuthLayout>
          }
        />
        <Route path="/signup" element={<Navigate to="/login" replace />} />
        <Route path="/forgot-password" element={<Navigate to="/login" replace />} />

        <Route path="*" element={<NotFound />} />
      </Routes>

      {/* Global non-blocking voice fallback / missing-voice notice */}
      <VoiceNoticeBanner />

      {/* PWA Install Prompt & Bottom Nav — rendered on authenticated app routes */}
      {!isAuthRoute && status === 'authenticated' && <InstallPrompt />}
      {!isAuthRoute && status === 'authenticated' && <NavigationBar />}
    </div>
  );
}

export default App;
