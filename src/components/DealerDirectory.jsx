import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { MapPin, Navigation, Phone, Search } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import ListenButton from './ui/ListenButton';
import { buildSpeechText, formatSpeakableNumber } from '../utils/speechText';

const DEALERS = [
  {
    id: 'mapusa-kendra',
    nameKey: 'dealers.items.mapusaKendra.name',
    locationKey: 'dealers.items.mapusaKendra.location',
    distanceKm: 8,
    stock: [
      { labelKey: 'dealers.stock.inStockRagi', tone: 'green' },
      { labelKey: 'dealers.stock.outOfStockUrea', tone: 'red' },
      { labelKey: 'dealers.stock.lowStockNeem', tone: 'yellow' },
    ],
  },
  {
    id: 'dicholi-agro',
    nameKey: 'dealers.items.dicholiAgro.name',
    locationKey: 'dealers.items.dicholiAgro.location',
    distanceKm: 2,
    stock: [
      { labelKey: 'dealers.stock.inStockRagi', tone: 'green' },
      { labelKey: 'dealers.stock.lowStockNeem', tone: 'yellow' },
      { labelKey: 'dealers.stock.outOfStockUrea', tone: 'red' },
    ],
  },
  {
    id: 'goa-seed-coop',
    nameKey: 'dealers.items.goaSeedCoop.name',
    locationKey: 'dealers.items.goaSeedCoop.location',
    distanceKm: 12,
    stock: [
      { labelKey: 'dealers.stock.inStockRagi', tone: 'green' },
      { labelKey: 'dealers.stock.inStockUrea', tone: 'green' },
      { labelKey: 'dealers.stock.lowStockNeem', tone: 'yellow' },
    ],
  },
];

const BADGE_STYLES = {
  green: 'bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-500/15 dark:text-emerald-200 dark:border-emerald-700/60',
  red: 'bg-red-50 text-red-700 border-red-100 dark:bg-red-500/15 dark:text-red-200 dark:border-red-700/60',
  yellow: 'bg-amber-50 text-amber-700 border-amber-100 dark:bg-amber-500/15 dark:text-amber-200 dark:border-amber-700/60',
};

const cardVariants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
};

export default function DealerDirectory() {
  const { t, languageInfo } = useTranslation();
  const locale = languageInfo.speechLang;
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim().toLowerCase();

  const resolvedDealers = useMemo(
    () =>
      DEALERS.map((dealer) => {
        const name = t(dealer.nameKey);
        const location = t(dealer.locationKey);
        const distanceLabel = t('dealers.distanceAway', {
          km: formatSpeakableNumber(dealer.distanceKm, locale),
        });
        const stockItems = dealer.stock.map((item) => ({
          ...item,
          label: t(item.labelKey),
        }));
        const speechText = buildSpeechText([
          name,
          distanceLabel,
          location,
          ...stockItems.map((item) => item.label),
        ]);
        return {
          ...dealer,
          name,
          location,
          distanceLabel,
          stockItems,
          speechText,
        };
      }),
    [locale, t],
  );

  const filteredDealers = useMemo(
    () =>
      resolvedDealers.filter((dealer) => {
        if (!normalizedQuery) return true;
        return [
          dealer.name,
          dealer.location,
          ...dealer.stockItems.map(({ label }) => label),
        ].some((value) => value.toLowerCase().includes(normalizedQuery));
      }),
    [normalizedQuery, resolvedDealers],
  );

  const directorySpeech = useMemo(
    () =>
      buildSpeechText([
        t('dealers.title'),
        t('dealers.subtitle'),
        ...filteredDealers.map((d) => d.speechText),
      ]),
    [filteredDealers, t],
  );

  return (
    <motion.section
      variants={cardVariants}
      className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/50 sm:p-5"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-300">
            <MapPin size={21} />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                {t('dealers.title')}
              </h2>
              <ListenButton text={directorySpeech} variant="emerald" size="xs" />
            </div>
            <p className="mt-1 text-sm font-medium text-slate-500 dark:text-slate-400">
              {t('dealers.subtitle')}
            </p>
          </div>
        </div>
        <label className="relative block w-full sm:max-w-xs">
          <span className="sr-only">{t('dealers.searchAria')}</span>
          <Search
            size={16}
            className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('dealers.searchPlaceholder')}
            className="h-10 w-full rounded-lg border border-slate-200 bg-white ps-9 pe-3 text-sm font-medium text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:ring-emerald-950"
          />
        </label>
      </div>

      <motion.div
        initial="hidden"
        animate="show"
        transition={{ staggerChildren: 0.08 }}
        className="mt-5"
      >
        {filteredDealers.map((dealer) => (
          <motion.article
            key={dealer.id}
            variants={cardVariants}
            className="mb-3 rounded-xl border border-slate-200 bg-white p-4 last:mb-0 dark:border-slate-800 dark:bg-slate-900"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-bold text-slate-900 dark:text-white">
                    {dealer.name}
                  </h3>
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {dealer.distanceLabel}
                  </span>
                  <ListenButton text={dealer.speechText} variant="emerald" size="xs" />
                </div>
                <p className="mt-1 flex items-center gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
                  <MapPin size={13} />
                  {dealer.location}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {dealer.stockItems.map(({ labelKey, label, tone }) => (
                  <span
                    key={labelKey}
                    className={`rounded-full border px-2.5 py-1 text-[11px] font-bold ${BADGE_STYLES[tone]}`}
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
              <a
                href="tel:+919876543210"
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                <Phone size={14} /> {t('dealers.callDealer')}
              </a>
              <a
                href="https://maps.google.com/?q=agriculture+store"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-bold text-emerald-700 transition hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:text-emerald-400 dark:hover:bg-emerald-950"
              >
                <Navigation size={14} /> {t('dealers.getDirections')}
              </a>
            </div>
          </motion.article>
        ))}
        {filteredDealers.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm font-medium text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
            {t('dealers.noResults', { query })}
          </div>
        )}
      </motion.div>
    </motion.section>
  );
}
