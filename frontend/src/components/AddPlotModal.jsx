/*
 * FieldShift frontend: Plot Creation Modal
 * Feature: Lets users create or edit farm plots with the metadata needed for field planning, recommendation logic, and area calculations.
 * Impact: This turns raw land data into structured operational records that drive crop planning, soil analysis, and reporting.
 * Importance: It is a core user entry point for translating on-ground farm information into app intelligence.
 */

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { area as turfArea } from '@turf/area';
import { polygon as turfPolygon } from '@turf/helpers';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, ChevronDown, Leaf, MapPin, Plus, Sparkles, X } from 'lucide-react';
import CropImage from './CropImage';
import CropPicker from './CropPicker';
import useScrollLock from '../hooks/useScrollLock';
import { useTranslation } from '../context/LanguageContext';
import { getCropDisplayName } from '../data/crops';
import {
  getIntercropPairingRule,
  getRecommendedIntercrops,
} from '../services/intercropRules';

const EMPTY_FORM = {
  fieldName: '',
  area: '',
  areaUnit: 'acres',
  primaryCrop: '',
  intercrop: '',
};

const AREA_FACTORS = {
  acres: 4046.8564,
  hectares: 10000,
  guntha: 101.17,
  bigha: 2529.285,
  sqm: 1,
  sqft: 0.092903,
};

function parseLocaleDecimal(raw) {
  if (raw === '' || raw == null) return NaN;
  const normalized = String(raw).trim().replace(/,/g, '.');
  if (!/^\d*\.?\d+$/.test(normalized)) return NaN;
  return Number(normalized);
}

function areaInUnit(coordinates, unit) {
  if (coordinates.length < 3) return '';
  const factor = AREA_FACTORS[unit] || AREA_FACTORS.acres;
  const closed = [...coordinates, coordinates[0]].map(([latitude, longitude]) => [longitude, latitude]);
  return (turfArea(turfPolygon([closed])) / factor).toFixed(2);
}

export default function AddPlotModal({
  isOpen,
  onClose,
  onSubmit,
  showMap = false,
  onShowMap,
  mapResult,
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState(EMPTY_FORM);
  const [areaError, setAreaError] = useState('');
  const [showIntercrop, setShowIntercrop] = useState(false);
  const [coordinates, setCoordinates] = useState([]);
  useScrollLock(isOpen);

  const areaUnits = useMemo(
    () => [
      { value: 'acres', shortLabel: t('addField.unitShortAc'), fullLabel: t('addField.unitFullAcres') },
      { value: 'hectares', shortLabel: t('addField.unitShortHa'), fullLabel: t('addField.unitFullHectares') },
      { value: 'guntha', shortLabel: t('addField.unitShortGuntha'), fullLabel: t('addField.unitFullGuntha') },
      { value: 'bigha', shortLabel: t('addField.unitShortBigha'), fullLabel: t('addField.unitFullBigha') },
      { value: 'sqm', shortLabel: t('addField.unitShortSqm'), fullLabel: t('addField.unitFullSqm') },
      { value: 'sqft', shortLabel: t('addField.unitShortSqft'), fullLabel: t('addField.unitFullSqft') },
    ],
    [t],
  );

  const activeUnit = useMemo(
    () => areaUnits.find((u) => u.value === form.areaUnit) || areaUnits[0],
    [areaUnits, form.areaUnit],
  );

  const recommendedIntercrops = useMemo(
    () => getRecommendedIntercrops(form.primaryCrop),
    [form.primaryCrop],
  );

  const activePairingRule = useMemo(
    () =>
      showIntercrop && form.primaryCrop && form.intercrop
        ? getIntercropPairingRule(form.primaryCrop, form.intercrop)
        : null,
    [form.intercrop, form.primaryCrop, showIntercrop],
  );

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        if (showMap) {
          onShowMap?.(false);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose, showMap, onShowMap]);

  useEffect(() => {
    if (!mapResult) return undefined;
    const timeout = setTimeout(() => {
      setCoordinates(mapResult.coordinates);
      setForm((current) => ({ ...current, area: mapResult.area, areaUnit: mapResult.unit || current.areaUnit }));
      setAreaError('');
    }, 0);
    return () => clearTimeout(timeout);
  }, [mapResult]);

  const handleFieldNameChange = (event) => {
    setForm((current) => ({ ...current, fieldName: event.target.value }));
  };

  const handleAreaChange = (event) => {
    const raw = event.target.value;
    // Allow digits, a single dot or comma for locale decimal input
    if (raw !== '' && !/^[0-9]*[.,]?[0-9]*$/.test(raw)) return;
    setForm((current) => ({ ...current, area: raw }));
    if (areaError) {
      const numeric = parseLocaleDecimal(raw);
      if (Number.isFinite(numeric) && numeric > 0) {
        setAreaError('');
      }
    }
  };

  const handleUnitChange = (event) => {
    const nextUnit = event.target.value;
    setForm((current) => ({
      ...current,
      areaUnit: nextUnit,
      area: coordinates.length >= 3 ? areaInUnit(coordinates, nextUnit) : current.area,
    }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    const numericArea = parseLocaleDecimal(form.area);
    if (!Number.isFinite(numericArea) || numericArea <= 0) {
      setAreaError(t('addField.areaInvalid'));
      return;
    }
    setAreaError('');
    onSubmit({
      ...form,
      area: String(numericArea),
      intercrop: showIntercrop ? form.intercrop : '',
      coordinates,
    });
    setForm(EMPTY_FORM);
    setShowIntercrop(false);
    setCoordinates([]);
    onClose();
  };

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="app-modal-layer fixed inset-0 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !showMap) onClose();
          }}
        >
          <motion.form
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-plot-title"
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.96 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            onSubmit={handleSubmit}
            className="max-h-[90dvh] w-full max-w-md overflow-y-auto overscroll-contain rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-xl dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300">
                  <Leaf size={21} />
                </div>
                <div>
                  <h2 id="add-plot-title" className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                    {t('addField.title')}
                  </h2>
                  <p className="mt-0.5 text-sm font-medium text-slate-500 dark:text-slate-400">
                    {t('addField.subtitle')}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label={t('addField.closeDialog')}
                className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:hover:bg-slate-800 dark:hover:text-slate-200"
              >
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300">
                {t('addField.fieldNameLabel')}
                <input
                  required
                  type="text"
                  value={form.fieldName}
                  onChange={handleFieldNameChange}
                  placeholder={t('addField.fieldNamePlaceholder')}
                  className="mt-1.5 h-11 w-full rounded-xl border border-slate-300 bg-white px-3.5 text-[15px] font-medium text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500"
                />
              </label>

              <button
                type="button"
                onClick={() => onShowMap?.(true, form.areaUnit)}
                className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 text-[15px] font-bold text-emerald-700 transition hover:bg-emerald-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-emerald-800/70 dark:bg-emerald-500/15 dark:text-emerald-300 dark:hover:bg-emerald-500/25"
              >
                <MapPin size={17} />
                <span>{t('addField.drawAreaOnMap')}</span>
              </button>

              {coordinates.length >= 3 && (
                <span className="inline-flex rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                  {t('addField.boundaryCaptured', { count: coordinates.length })}
                </span>
              )}

              <div>
                <label
                  htmlFor="add-plot-area-input"
                  className="block text-sm font-semibold text-slate-700 dark:text-slate-300"
                >
                  {t('addField.areaSizeLabel')}
                </label>
                <div
                  className={`mt-1.5 flex h-11 w-full items-stretch overflow-hidden rounded-xl border bg-white transition focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-500/30 dark:bg-slate-950 ${
                    areaError
                      ? 'border-rose-400 dark:border-rose-500'
                      : 'border-slate-300 dark:border-slate-700'
                  }`}
                >
                  <input
                    id="add-plot-area-input"
                    required
                    type="text"
                    inputMode="decimal"
                    dir="ltr"
                    value={form.area}
                    onChange={handleAreaChange}
                    aria-invalid={Boolean(areaError)}
                    placeholder={t('addField.areaPlaceholder')}
                    className="h-full min-w-0 flex-1 bg-transparent px-3.5 text-[15px] font-medium text-slate-900 outline-none placeholder:text-slate-400 dark:text-slate-100 dark:placeholder:text-slate-500"
                  />
                  <div className="relative flex h-full w-[108px] shrink-0 items-center border-s border-slate-300 bg-slate-50/90 dark:border-slate-700 dark:bg-slate-900">
                    <span
                      aria-hidden="true"
                      className="pointer-events-none flex h-full w-full items-center justify-between ps-3 pe-2.5 text-[15px] font-semibold text-slate-800 dark:text-slate-100"
                    >
                      <span className="truncate">{activeUnit.shortLabel}</span>
                      <ChevronDown size={16} className="shrink-0 text-slate-500 dark:text-slate-400" />
                    </span>
                    <select
                      aria-label={t('common.areaUnit')}
                      value={form.areaUnit}
                      onChange={handleUnitChange}
                      className="absolute inset-0 h-full w-full cursor-pointer appearance-none bg-white text-[15px] font-medium text-slate-900 opacity-0 dark:bg-slate-900 dark:text-slate-100 [&>option]:bg-white [&>option]:text-slate-900 dark:[&>option]:bg-slate-900 dark:[&>option]:text-slate-100"
                    >
                      {areaUnits.map((unit) => (
                        <option
                          key={unit.value}
                          value={unit.value}
                          className="bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100"
                        >
                          {unit.shortLabel} — {unit.fullLabel}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                {areaError && (
                  <p role="alert" className="mt-1.5 text-xs font-medium text-rose-600 dark:text-rose-400">
                    {areaError}
                  </p>
                )}
              </div>

              <CropPicker
                value={form.primaryCrop}
                onChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    primaryCrop: value,
                    intercrop: current.intercrop === value ? '' : current.intercrop,
                  }))
                }
                label={t('common.primaryCrop')}
              />

              {recommendedIntercrops.length > 0 && (
                <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/50 p-3 dark:border-emerald-800/60 dark:bg-slate-800/70">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-800 dark:text-emerald-300">
                    <Sparkles size={14} className="shrink-0 text-amber-500" />
                    <span>{t('addField.recommendedCompanions')}</span>
                  </div>
                  <p className="mt-0.5 text-[11px] font-medium text-slate-600 dark:text-slate-400">
                    {t('addField.recommendedCompanionsHint', {
                      crop: getCropDisplayName(form.primaryCrop, t),
                    })}
                  </p>
                  <div className="mt-2.5 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {recommendedIntercrops.map((rule) => {
                      const isCompanionSelected =
                        showIntercrop && form.intercrop === rule.companionCropId;
                      const companionName = getCropDisplayName(rule.companionCropId, t);
                      const benefitBadgeClass =
                        rule.accent === 'amber'
                          ? 'bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200'
                          : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200';

                      return (
                        <button
                          key={rule.companionCropId}
                          type="button"
                          onClick={() => {
                            if (isCompanionSelected) {
                              setForm((current) => ({ ...current, intercrop: '' }));
                            } else {
                              setShowIntercrop(true);
                              setForm((current) => ({
                                ...current,
                                intercrop: rule.companionCropId,
                              }));
                            }
                          }}
                          className={`flex items-center gap-2.5 rounded-xl border p-2 text-start transition focus:outline-none focus:ring-2 focus:ring-emerald-500 ${
                            isCompanionSelected
                              ? 'border-emerald-500 bg-white ring-2 ring-emerald-400/50 dark:border-emerald-400 dark:bg-slate-900'
                              : 'border-slate-200 bg-white/90 hover:border-emerald-300 dark:border-slate-700 dark:bg-slate-900/90'
                          }`}
                        >
                          <CropImage cropId={rule.companionCropId} size="xs" />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-1">
                              <span className="truncate text-xs font-bold text-slate-900 dark:text-slate-100">
                                {companionName}
                              </span>
                              <span className="shrink-0 text-[10px] font-extrabold text-emerald-700 dark:text-emerald-300">
                                {t('addField.matchScore', { score: rule.benefitScore })}
                              </span>
                            </div>
                            <span
                              className={`mt-1 inline-block max-w-full truncate rounded-full px-2 py-0.5 text-[10px] font-bold ${benefitBadgeClass}`}
                            >
                              {t(rule.benefitKey)}
                            </span>
                          </div>
                          {isCompanionSelected && (
                            <Check
                              size={14}
                              aria-hidden="true"
                              className="shrink-0 rounded-full bg-emerald-600 p-0.5 text-white"
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {!showIntercrop ? (
                <button
                  type="button"
                  onClick={() => setShowIntercrop(true)}
                  className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-dashed border-emerald-300 bg-emerald-50/60 px-4 text-[15px] font-bold text-emerald-700 transition hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:border-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300 dark:hover:bg-emerald-500/20"
                >
                  <Plus size={17} />
                  <span>{t('addField.addIntercrop')}</span>
                </button>
              ) : (
                <div className="space-y-2.5 rounded-xl border border-slate-200 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-950/60">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                      {t('common.selectIntercrop')}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setShowIntercrop(false);
                        setForm((current) => ({ ...current, intercrop: '' }));
                      }}
                      className="text-xs font-bold text-slate-500 underline underline-offset-2 transition hover:text-rose-600 dark:text-slate-400 dark:hover:text-rose-400"
                    >
                      {t('addField.removeIntercrop')}
                    </button>
                  </div>

                  {activePairingRule && (
                    <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-800 dark:border-emerald-500/30 dark:bg-emerald-500/15 dark:text-emerald-200">
                      <Sparkles size={14} className="shrink-0 text-amber-500" />
                      <span className="min-w-0 break-words">
                        {t('addField.selectedPairingBenefit', {
                          primary: getCropDisplayName(form.primaryCrop, t),
                          companion: getCropDisplayName(form.intercrop, t),
                          benefit: t(activePairingRule.benefitKey),
                          score: activePairingRule.benefitScore,
                        })}
                      </span>
                    </div>
                  )}

                  <CropPicker
                    value={form.intercrop}
                    onChange={(value) => setForm((current) => ({ ...current, intercrop: value }))}
                    exclude={[form.primaryCrop]}
                    recommendedCrops={recommendedIntercrops}
                  />
                </div>
              )}
            </div>

            <button
              type="submit"
              className="mt-6 h-11 w-full rounded-xl bg-emerald-600 px-4 text-[15px] font-bold text-white shadow-sm transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
            >
              {t('addField.saveField')}
            </button>
          </motion.form>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
