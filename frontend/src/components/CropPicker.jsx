/*
 * FieldShift frontend: Crop Selection UI
 * Feature: Presents crop options and filters so users can select the crop they want to analyze, compare, or recommend.
 * Impact: This turns the crop catalog into a decision-making tool by making the selection flow fast and understandable.
 * Importance: Crop selection sits at the heart of recommendations, planning, and value insight features.
 */

import { useMemo, useState } from 'react';
import { Check, Search, Sparkles } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import { CROPS } from '../data/crops';
import CropImage from './CropImage';

export default function CropPicker({
  value,
  onChange,
  exclude = [],
  recommendedCrops = [],
  label,
  className = '',
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const normalizedQuery = query.trim().toLocaleLowerCase();

  const recommendedMap = useMemo(
    () => new Map(recommendedCrops.map((rule) => [rule.companionCropId, rule])),
    [recommendedCrops],
  );

  const filtered = useMemo(() => {
    const excluded = new Set(exclude.filter(Boolean));
    const matches = CROPS.filter((crop) => {
      if (excluded.has(crop.id)) return false;
      if (!normalizedQuery) return crop.id !== 'other';
      return `${t(crop.nameKey)} ${t(crop.localNameKey)} ${crop.id}`
        .toLocaleLowerCase()
        .includes(normalizedQuery);
    });

    if (recommendedMap.size === 0) return matches;

    return [...matches].sort((a, b) => {
      const recA = recommendedMap.get(a.id);
      const recB = recommendedMap.get(b.id);
      if (recA && recB) return recB.benefitScore - recA.benefitScore;
      if (recA) return -1;
      if (recB) return 1;
      return 0;
    });
  }, [exclude, normalizedQuery, recommendedMap, t]);

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
          const recommendation = recommendedMap.get(crop.id);

          return (
            <button
              key={crop.id}
              type="button"
              role="option"
              aria-selected={selected}
              onClick={() => onChange(crop.id)}
              className={`relative flex min-h-24 flex-col items-center justify-center gap-1 rounded-xl border p-2 text-center transition focus:outline-none focus:ring-2 focus:ring-emerald-500 ${
                selected
                  ? 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-400 dark:border-emerald-400 dark:bg-emerald-500/15'
                  : recommendation
                    ? 'border-amber-300 bg-amber-50/50 hover:border-amber-400 dark:border-amber-500/40 dark:bg-amber-500/10'
                    : 'border-slate-200 bg-white hover:border-emerald-300 dark:border-slate-700 dark:bg-slate-900'
              }`}
            >
              {recommendation && (
                <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[9px] font-extrabold text-amber-800 dark:bg-amber-500/25 dark:text-amber-200">
                  <Sparkles size={9} aria-hidden="true" />
                  <span>{recommendation.benefitScore}%</span>
                </span>
              )}
              <CropImage cropId={crop.id} size="sm" showName />
              {recommendation && (
                <span className="max-w-full truncate text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
                  {t(recommendation.benefitKey)}
                </span>
              )}
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
