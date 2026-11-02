import { useMemo, useState } from 'react';
import { Check, Search } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import { CROPS } from '../data/crops';
import CropImage from './CropImage';

export default function CropPicker({ value, onChange, exclude = [], label, className = '' }) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const filtered = useMemo(
    () =>
      CROPS.filter((crop) => {
        const excluded = new Set(exclude);
        if (excluded.has(crop.id)) return false;
        if (!normalizedQuery) return crop.id !== 'other';
        return `${t(crop.nameKey)} ${t(crop.localNameKey)} ${crop.id}`
          .toLocaleLowerCase()
          .includes(normalizedQuery);
      }),
    [exclude, normalizedQuery, t],
  );

  return (
    <div className={`space-y-2.5 ${className}`}>
      {label && <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{label}</p>}
      <label className="relative block">
        <span className="sr-only">{t('crops.search')}</span>
        <Search
          size={16}
          aria-hidden="true"
          className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-slate-400"
        />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('crops.search')}
          aria-label={t('crops.search')}
          className="h-11 w-full rounded-xl border border-slate-300 bg-white ps-10 pe-3.5 text-[15px] text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
        />
      </label>
      <div
        role="listbox"
        aria-label={label || t('common.primaryCrop')}
        className="grid max-h-[min(55vh,360px)] grid-cols-3 gap-2 overflow-y-auto overscroll-contain p-1 sm:grid-cols-4"
      >
        {filtered.map((crop) => {
          const selected = value === crop.id;
          return (
            <button
              key={crop.id}
              type="button"
              role="option"
              aria-selected={selected}
              onClick={() => onChange(crop.id)}
              className={`relative flex min-h-24 flex-col items-center justify-center gap-1.5 rounded-xl border p-2 text-center transition focus:outline-none focus:ring-2 focus:ring-emerald-500 ${
                selected
                  ? 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-400 dark:border-emerald-400 dark:bg-emerald-500/15'
                  : 'border-slate-200 bg-white hover:border-emerald-300 dark:border-slate-700 dark:bg-slate-900'
              }`}
            >
              <CropImage cropId={crop.id} size="sm" showName />
              {selected && (
                <Check
                  size={16}
                  aria-hidden="true"
                  className="absolute end-1.5 top-1.5 rounded-full bg-emerald-600 p-0.5 text-white"
                />
              )}
            </button>
          );
        })}
        {filtered.length === 0 && (
          <p className="col-span-full py-4 text-center text-sm text-slate-500 dark:text-slate-400">
            {t('crops.noResults')}
          </p>
        )}
      </div>
    </div>
  );
}
