import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Landmark, ShieldCheck, Sprout } from 'lucide-react';
import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../db/db';
import { useTranslation } from '../context/LanguageContext';
import ListenButton from './ui/ListenButton';
import { buildSpeechText, formatSpeakablePriceWithUnit } from '../utils/speechText';

const SCHEMES = [
  {
    id: 'pmKisan',
    nameKey: 'schemes.items.pmKisan.name',
    focusKey: 'schemes.items.pmKisan.focus',
    badgeKey: 'schemes.items.pmKisan.badge',
    benefitKey: 'schemes.items.pmKisan.benefit',
    benefitAmount: 6000,
    benefitUnitKey: 'schemes.perYear',
    descriptionKey: 'schemes.items.pmKisan.description',
    actionKey: 'schemes.items.pmKisan.action',
    isPrimaryAction: false,
    requiresVerification: true,
    icon: Landmark,
    iconClass: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300',
    badgeClass: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
  },
  {
    id: 'pmfby',
    nameKey: 'schemes.items.pmfby.name',
    focusKey: 'schemes.items.pmfby.focus',
    badgeKey: 'schemes.items.pmfby.badge',
    benefitKey: 'schemes.items.pmfby.benefit',
    benefitAmount: null,
    benefitUnitKey: null,
    descriptionKey: 'schemes.items.pmfby.description',
    actionKey: 'schemes.items.pmfby.action',
    isPrimaryAction: false,
    requiresVerification: true,
    icon: ShieldCheck,
    iconClass: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-300',
    badgeClass: 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300',
  },
  {
    id: 'pkvy',
    nameKey: 'schemes.items.pkvy.name',
    focusKey: 'schemes.items.pkvy.focus',
    badgeKey: 'schemes.items.pkvy.badge',
    benefitKey: 'schemes.items.pkvy.benefit',
    benefitAmount: 50000,
    benefitUnitKey: 'schemes.perHectare',
    descriptionKey: 'schemes.items.pkvy.description',
    actionKey: 'schemes.items.pkvy.action',
    isPrimaryAction: true,
    requiresVerification: false,
    icon: Sprout,
    iconClass: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300',
    badgeClass: 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
  },
];

const cardVariants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

export default function SchemesHub() {
  const { t, languageInfo } = useTranslation();
  const locale = languageInfo.speechLang;
  const rawPlots = useLiveQuery(() => db.plots.toArray(), []);
  const verifiedCount = useMemo(
    () =>
      (rawPlots || []).filter(
        (plot) => plot.provenance?.verified === true || plot.isVerified === true,
      ).length,
    [rawPlots],
  );

  const overviewSpeech = useMemo(
    () =>
      buildSpeechText([
        t('schemes.title'),
        t('schemes.subtitle'),
        ...SCHEMES.map((s) => {
          const spokenBenefit = s.benefitAmount
            ? formatSpeakablePriceWithUnit(s.benefitAmount, t(s.benefitUnitKey), locale)
            : t(s.benefitKey);
          return `${t(s.nameKey)}: ${t(s.focusKey)}, ${spokenBenefit}`;
        }),
      ]),
    [locale, t],
  );

  return (
    <div className="min-h-screen bg-slate-50 px-4 pb-12 pt-24 dark:bg-slate-950 sm:px-6 lg:px-8">
      <motion.main
        initial="hidden"
        animate="show"
        transition={{ staggerChildren: 0.08 }}
        className="mx-auto flex max-w-7xl flex-col gap-6"
      >
        <motion.header
          variants={cardVariants}
          className="flex flex-wrap items-start justify-between gap-4"
        >
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-400">
              {t('schemes.eyebrow')}
            </p>
            <h1 className="mt-1 text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100">
              {t('schemes.title')}
            </h1>
            <p className="mt-2 text-sm font-medium text-slate-500 dark:text-slate-400">
              {t('schemes.subtitle')}
            </p>
          </div>
          <ListenButton text={overviewSpeech} variant="emerald" size="md" />
        </motion.header>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {SCHEMES.map((scheme) => {
            const Icon = scheme.icon;
            const eligibilityText = scheme.requiresVerification
              ? verifiedCount > 0
                ? t('schemes.eligibleFields', { count: String(verifiedCount) })
                : t('schemes.linkToUnlock')
              : '';
            const spokenBenefit = scheme.benefitAmount
              ? formatSpeakablePriceWithUnit(scheme.benefitAmount, t(scheme.benefitUnitKey), locale)
              : t(scheme.benefitKey);
            const cardSpeech = buildSpeechText([
              t(scheme.nameKey),
              t(scheme.focusKey),
              t(scheme.badgeKey),
              t(scheme.descriptionKey),
              eligibilityText,
              `${t('schemes.financialBenefit')}: ${spokenBenefit}`,
            ]);

            return (
              <motion.article
                key={scheme.id}
                variants={cardVariants}
                className="flex flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${scheme.iconClass}`}>
                    <Icon size={23} />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${scheme.badgeClass}`}>
                      {t(scheme.badgeKey)}
                    </span>
                    <ListenButton text={cardSpeech} variant="emerald" size="xs" />
                  </div>
                </div>
                <div className="mt-5">
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    {t(scheme.focusKey)}
                  </p>
                  <h2 className="mt-1 text-xl font-black tracking-tight text-slate-900 dark:text-slate-100">
                    {t(scheme.nameKey)}
                  </h2>
                  <p className="mt-3 text-sm font-medium leading-6 text-slate-500 dark:text-slate-400">
                    {t(scheme.descriptionKey)}
                  </p>
                  {scheme.requiresVerification && (
                    <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-200">
                      {eligibilityText}
                    </p>
                  )}
                </div>
                <div className="mt-5 rounded-xl bg-slate-50 px-3.5 py-3 dark:bg-slate-950">
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    {t('schemes.financialBenefit')}
                  </p>
                  <p className="mt-1 text-lg font-black text-slate-900 dark:text-slate-100">
                    {t(scheme.benefitKey)}
                  </p>
                </div>
                <button
                  type="button"
                  className={`mt-5 inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold transition focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 ${
                    scheme.isPrimaryAction
                      ? 'bg-emerald-600 text-white shadow-sm hover:bg-emerald-700'
                      : 'border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300'
                  }`}
                >
                  {t(scheme.actionKey)}
                  <ArrowRight size={16} />
                </button>
              </motion.article>
            );
          })}
        </div>
      </motion.main>
    </div>
  );
}
