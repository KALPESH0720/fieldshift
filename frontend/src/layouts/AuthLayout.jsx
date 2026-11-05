/*
 * FieldShift frontend: Authentication Layout
 * Feature: Provides the shared frame for login and auth-related screens with consistent branding and page structure.
 * Impact: It keeps the auth experience consistent and visually aligned with the rest of the app.
 * Importance: A dedicated auth layout creates a reliable entry experience for every user session.
 */

import { motion, useReducedMotion } from 'framer-motion';
import {
  Leaf,
  ShieldCheck,
  Sprout,
  Wifi,
  BarChart3,
  CloudSun,
  Zap,
} from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';

function useLowEndOrReducedMotion() {
  const prefersReduced = useReducedMotion();
  const lowMemory =
    typeof navigator !== 'undefined' &&
    Number(navigator.deviceMemory) > 0 &&
    Number(navigator.deviceMemory) <= 2;
  return Boolean(prefersReduced || lowMemory);
}

/* ─── Animated floating orb (skipped on low-end / reduced-motion devices) ─── */
function FloatingOrb({ className, delay = 0, reduceMotion = false }) {
  if (reduceMotion) {
    return <div className={className} />;
  }
  return (
    <motion.div
      className={className}
      animate={{ y: [0, -18, 0], opacity: [0.55, 0.95, 0.55] }}
      transition={{ duration: 5 + delay, repeat: Infinity, ease: 'easeInOut', delay }}
    />
  );
}

/* ─── Stat card ──────────────────────────────────────────────── */
function StatTile({ value, label, icon: Icon }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3.5 text-center backdrop-blur-sm">
      <Icon size={18} className="text-emerald-300" />
      <p className="text-xl font-black text-white">{value}</p>
      <p className="text-xs font-medium text-slate-300">{label}</p>
    </div>
  );
}

/* ─── Right branding panel ───────────────────────────────────── */
function BrandPanel({ reduceMotion }) {
  const { t } = useTranslation();

  return (
    <aside className="relative hidden min-h-screen overflow-hidden md:flex md:w-1/2 md:flex-col md:items-center md:justify-center">
      {/* Deep dark base */}
      <div className="absolute inset-0 bg-slate-950" />

      {/* Gradient mesh */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_20%_15%,rgba(16,185,129,0.32),transparent_42%),radial-gradient(ellipse_at_80%_85%,rgba(37,99,235,0.26),transparent_40%)]" />

      {/* Floating orbs */}
      <FloatingOrb
        className="absolute left-8 top-20 h-64 w-64 rounded-full bg-emerald-400/10 blur-3xl"
        delay={0}
        reduceMotion={reduceMotion}
      />
      <FloatingOrb
        className="absolute -right-16 bottom-32 h-72 w-72 rounded-full bg-blue-500/10 blur-3xl"
        delay={1.5}
        reduceMotion={reduceMotion}
      />

      {/* Content */}
      <div className="relative z-10 mx-auto w-full max-w-lg px-10">
        {/* Logo */}
        <div className="mb-10 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 shadow-lg shadow-emerald-500/30">
            <Sprout size={24} className="text-white" />
          </div>
          <div>
            <p className="text-xl font-extrabold tracking-tight text-white">{t('dashboard.brand')}</p>
            <p className="text-xs font-semibold text-emerald-300/90">{t('auth.brandTagline')}</p>
          </div>
        </div>

        {/* Glass card */}
        <div className="rounded-[2rem] border border-white/12 bg-white/[0.07] p-8 shadow-2xl shadow-black/40 backdrop-blur-xl lg:p-10">
          <div className="mb-5 inline-flex">
            <Leaf size={38} className="text-emerald-300" />
          </div>

          <blockquote className="text-2xl font-black leading-tight tracking-tight text-white lg:text-3xl">
            {t('auth.brandQuote')}
          </blockquote>

          <p className="mt-4 text-sm leading-7 text-slate-300">
            {t('auth.brandDescription')}
          </p>

          {/* Stats row */}
          <div className="mt-7 grid grid-cols-3 gap-3">
            <StatTile value="100%" label={t('auth.statOffline')} icon={Wifi} />
            <StatTile value="SMS" label={t('auth.statOneTimeCode')} icon={Zap} />
            <StatTile value="256-bit" label={t('auth.statProtected')} icon={ShieldCheck} />
          </div>

          {/* Feature pills */}
          <div className="mt-6 flex flex-wrap gap-2">
            {[
              { icon: CloudSun, label: t('auth.pillWeather') },
              { icon: BarChart3, label: t('auth.pillCrops') },
              { icon: Leaf, label: t('auth.pillSoil') },
            ].map(({ icon: Icon, label }) => (
              <span
                key={label}
                className="flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-200"
              >
                <Icon size={12} />
                {label}
              </span>
            ))}
          </div>
        </div>

        <p className="mt-7 text-center text-xs font-medium text-slate-400">
          {t('auth.brandFooter')}
        </p>
      </div>
    </aside>
  );
}

/* ─── AuthLayout ─────────────────────────────────────────────── */
export default function AuthLayout({ children }) {
  const reduceMotion = useLowEndOrReducedMotion();

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="flex min-h-screen flex-col md:flex-row">
        {/* Form panel */}
        <section className="flex w-full flex-1 flex-col justify-center bg-white px-4 py-6 dark:bg-slate-900 sm:px-8 sm:py-10 md:w-1/2 md:overflow-y-auto md:px-12 lg:px-16">
          <div className="mx-auto w-full max-w-md">{children}</div>
        </section>

        {/* Branding panel */}
        <BrandPanel reduceMotion={reduceMotion} />
      </div>
    </main>
  );
}
