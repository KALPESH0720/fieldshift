/*
 * FieldShift frontend: Group Dashboard
 * Feature: Displays aggregated farmer group activity, collective crop insights, and coordination views for shared agricultural planning.
 * Impact: It supports cooperative or extension-led decision-making at a scale above individual plots.
 * Importance: This widens the value of the product from individual farming to community and advisory-driven productivity.
 */

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  BadgeCheck,
  BarChart3,
  IndianRupee,
  LandPlot,
  Layers,
  Package,
  Sprout,
  Users,
} from 'lucide-react';
import CropImage from './CropImage';
import ListenButton from './ui/ListenButton';
import { useTranslation } from '../context/LanguageContext';
import { getCropDisplayName } from '../data/crops';
import {
  formatSpeakableCurrency,
  formatSpeakableNumber,
  formatSpeakableWeightKg,
} from '../utils/speechText';

const UREA_BAG_WEIGHT_KG = 45;

// Standard agronomic seeding & average Urea requirements per hectare
const CROP_INPUT_RATES = {
  paddy: { seedKgPerHa: 40, ureaKgPerHa: 110, seedCostInrPerKg: 55, ureaCostInrPerKg: 6.5 },
  moong: { seedKgPerHa: 25, ureaKgPerHa: 35, seedCostInrPerKg: 140, ureaCostInrPerKg: 6.5 },
  cowpea: { seedKgPerHa: 25, ureaKgPerHa: 40, seedCostInrPerKg: 120, ureaCostInrPerKg: 6.5 },
  cashew: { seedKgPerHa: 15, ureaKgPerHa: 90, seedCostInrPerKg: 180, ureaCostInrPerKg: 6.5 },
  groundnut: { seedKgPerHa: 100, ureaKgPerHa: 45, seedCostInrPerKg: 95, ureaCostInrPerKg: 6.5 },
  sugarcane: { seedKgPerHa: 60, ureaKgPerHa: 220, seedCostInrPerKg: 45, ureaCostInrPerKg: 6.5 },
};

const DEFAULT_CROP_RATE = {
  seedKgPerHa: 30,
  ureaKgPerHa: 80,
  seedCostInrPerKg: 80,
  ureaCostInrPerKg: 6.5,
};

// Mock dataset of 7 FPO member farmers with multi-plot holdings
const FPO_MEMBERS = [
  {
    id: 'fpo-member-1',
    nameKey: 'group.members.ramesh',
    villageKey: 'group.villages.dicholi',
    status: 'onTrack',
    plots: [
      { id: 'plot-101', areaHectares: 1.4, primaryCrop: 'cashew' },
      { id: 'plot-102', areaHectares: 0.8, primaryCrop: 'moong' },
    ],
  },
  {
    id: 'fpo-member-2',
    nameKey: 'group.members.savitri',
    villageKey: 'group.villages.amona',
    status: 'sowingDelayed',
    plots: [
      { id: 'plot-201', areaHectares: 1.5, primaryCrop: 'paddy' },
      { id: 'plot-202', areaHectares: 0.6, primaryCrop: 'moong' },
    ],
  },
  {
    id: 'fpo-member-3',
    nameKey: 'group.members.mohan',
    villageKey: 'group.villages.sanquelim',
    status: 'onTrack',
    plots: [
      { id: 'plot-301', areaHectares: 2.0, primaryCrop: 'sugarcane' },
      { id: 'plot-302', areaHectares: 0.9, primaryCrop: 'paddy' },
    ],
  },
  {
    id: 'fpo-member-4',
    nameKey: 'group.members.anita',
    villageKey: 'group.villages.mulgao',
    status: 'onTrack',
    plots: [
      { id: 'plot-401', areaHectares: 1.2, primaryCrop: 'cashew' },
      { id: 'plot-402', areaHectares: 0.5, primaryCrop: 'cowpea' },
    ],
  },
  {
    id: 'fpo-member-5',
    nameKey: 'group.members.vishnu',
    villageKey: 'group.villages.honda',
    status: 'sowingDelayed',
    plots: [
      { id: 'plot-501', areaHectares: 1.8, primaryCrop: 'paddy' },
      { id: 'plot-502', areaHectares: 0.7, primaryCrop: 'groundnut' },
    ],
  },
  {
    id: 'fpo-member-6',
    nameKey: 'group.members.laxmi',
    villageKey: 'group.villages.mayem',
    status: 'onTrack',
    plots: [
      { id: 'plot-601', areaHectares: 1.1, primaryCrop: 'moong' },
      { id: 'plot-602', areaHectares: 0.8, primaryCrop: 'paddy' },
    ],
  },
  {
    id: 'fpo-member-7',
    nameKey: 'group.members.prakash',
    villageKey: 'group.villages.narva',
    status: 'inputsPending',
    plots: [
      { id: 'plot-701', areaHectares: 1.3, primaryCrop: 'groundnut' },
    ],
  },
];

function aggregateFpoDemand(members) {
  const cropMap = new Map();
  const villageSet = new Set();

  let totalAreaHectares = 0;
  let totalPlots = 0;
  let totalSeedKg = 0;
  let totalUreaKg = 0;
  let totalProcurementInr = 0;
  let onTrackFarmers = 0;
  let attentionFarmers = 0;

  const farmerRows = members.map((farmer) => {
    villageSet.add(farmer.villageKey);
    if (farmer.status === 'onTrack') {
      onTrackFarmers += 1;
    } else {
      attentionFarmers += 1;
    }

    let farmerAreaHa = 0;
    let farmerSeedKg = 0;
    let farmerUreaKg = 0;
    const farmerCropIds = [];

    for (const plot of farmer.plots) {
      const areaHa = Number(plot.areaHectares) || 0;
      const cropId = plot.primaryCrop;
      const rates = CROP_INPUT_RATES[cropId] || DEFAULT_CROP_RATE;

      const plotSeedKg = areaHa * rates.seedKgPerHa;
      const plotUreaKg = areaHa * rates.ureaKgPerHa;
      const plotCostInr =
        plotSeedKg * rates.seedCostInrPerKg + plotUreaKg * rates.ureaCostInrPerKg;

      totalPlots += 1;
      totalAreaHectares += areaHa;
      totalSeedKg += plotSeedKg;
      totalUreaKg += plotUreaKg;
      totalProcurementInr += plotCostInr;

      farmerAreaHa += areaHa;
      farmerSeedKg += plotSeedKg;
      farmerUreaKg += plotUreaKg;
      if (!farmerCropIds.includes(cropId)) {
        farmerCropIds.push(cropId);
      }

      const existing = cropMap.get(cropId) || {
        cropId,
        areaHectares: 0,
        seedKg: 0,
        ureaKg: 0,
        seedRateKgPerHa: rates.seedKgPerHa,
        ureaRateKgPerHa: rates.ureaKgPerHa,
      };
      existing.areaHectares += areaHa;
      existing.seedKg += plotSeedKg;
      existing.ureaKg += plotUreaKg;
      cropMap.set(cropId, existing);
    }

    return {
      id: farmer.id,
      nameKey: farmer.nameKey,
      villageKey: farmer.villageKey,
      status: farmer.status,
      plotCount: farmer.plots.length,
      areaHectares: Math.round(farmerAreaHa * 10) / 10,
      cropIds: farmerCropIds,
      seedKg: Math.round(farmerSeedKg),
      ureaKg: Math.round(farmerUreaKg),
    };
  });

  const demandByCrop = [...cropMap.values()]
    .map((entry) => ({
      ...entry,
      areaHectares: Math.round(entry.areaHectares * 10) / 10,
      seedKg: Math.round(entry.seedKg),
      ureaKg: Math.round(entry.ureaKg),
    }))
    .sort((a, b) => b.seedKg - a.seedKg);

  const roundedSeedKg = Math.round(totalSeedKg);
  const roundedUreaKg = Math.round(totalUreaKg);

  return {
    totalFarmers: members.length,
    totalPlots,
    activeVillages: villageSet.size,
    mappedAreaHectares: Math.round(totalAreaHectares * 10) / 10,
    totalSeedKg: roundedSeedKg,
    totalUreaKg: roundedUreaKg,
    ureaBags45Kg: Math.ceil(roundedUreaKg / UREA_BAG_WEIGHT_KG),
    estimatedProcurementInr: Math.round(totalProcurementInr),
    onTrackFarmers,
    attentionFarmers,
    demandByCrop,
    farmerRows,
  };
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
};

const STATUS_BADGE_CLASSES = {
  onTrack:
    'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300',
  sowingDelayed:
    'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300',
  inputsPending:
    'bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300',
};

export default function GroupDashboard() {
  const { t, languageInfo } = useTranslation();
  const locale = languageInfo.speechLang || 'en-IN';

  const summary = useMemo(() => aggregateFpoDemand(FPO_MEMBERS), []);

  const formatNum = (value, maxDecimals = 0) =>
    formatSpeakableNumber(value, locale, maxDecimals);

  const formatInrDisplay = (amount) => {
    try {
      return new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0,
      }).format(amount);
    } catch {
      return `₹${Math.round(amount).toLocaleString('en-IN')}`;
    }
  };

  const topSeedCrops = summary.demandByCrop;
  const firstSeedCrop = topSeedCrops[0];
  const secondSeedCrop = topSeedCrops[1];

  const seedDetailText =
    firstSeedCrop && secondSeedCrop
      ? t('group.topSeedDetail', {
          firstCrop: getCropDisplayName(firstSeedCrop.cropId, t),
          firstKg: formatNum(firstSeedCrop.seedKg),
          secondCrop: getCropDisplayName(secondSeedCrop.cropId, t),
          secondKg: formatNum(secondSeedCrop.seedKg),
        })
      : firstSeedCrop
        ? t('group.singleSeedDetail', {
            firstCrop: getCropDisplayName(firstSeedCrop.cropId, t),
            firstKg: formatNum(firstSeedCrop.seedKg),
          })
        : '';

  const kpiCards = [
    {
      id: 'total-farmers',
      label: t('group.totalFarmers'),
      value: formatNum(summary.totalFarmers),
      detail: t('group.totalFarmersDetail', {
        plots: formatNum(summary.totalPlots),
        villages: formatNum(summary.activeVillages),
      }),
      icon: Users,
      iconClass:
        'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300',
    },
    {
      id: 'mapped-area',
      label: t('group.mappedArea'),
      value: formatNum(summary.mappedAreaHectares, 1),
      suffix: t('group.hectaresUnit'),
      detail: t('group.mappedAreaDetail', {
        plots: formatNum(summary.totalPlots),
      }),
      icon: LandPlot,
      iconClass:
        'bg-sky-50 text-sky-600 dark:bg-sky-500/10 dark:text-sky-300',
    },
    {
      id: 'bulk-seed',
      label: t('group.bulkSeedDemand'),
      value: formatNum(summary.totalSeedKg),
      suffix: t('group.kgUnit'),
      detail: seedDetailText,
      icon: Sprout,
      iconClass:
        'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300',
    },
    {
      id: 'bulk-urea',
      label: t('group.bulkUreaDemand'),
      value: formatNum(summary.totalUreaKg),
      suffix: t('group.kgUnit'),
      detail: t('group.ureaBagsDetail', {
        bags: formatNum(summary.ureaBags45Kg),
      }),
      icon: Package,
      iconClass:
        'bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-300',
    },
  ];

  const headerSpeechText = useMemo(() => {
    const topCropName = firstSeedCrop
      ? getCropDisplayName(firstSeedCrop.cropId, t)
      : '';
    const topCropSeedSpoken = firstSeedCrop
      ? formatSpeakableWeightKg(firstSeedCrop.seedKg, locale)
      : '';

    return t('group.summarySpeech', {
      title: t('group.title'),
      coop: t('group.coopName'),
      farmers: formatSpeakableNumber(summary.totalFarmers, locale, 0),
      villages: formatSpeakableNumber(summary.activeVillages, locale, 0),
      area: formatSpeakableNumber(summary.mappedAreaHectares, locale, 1),
      areaUnit: t('group.hectaresSpoken'),
      plots: formatSpeakableNumber(summary.totalPlots, locale, 0),
      seed: formatSpeakableWeightKg(summary.totalSeedKg, locale),
      topCrop: topCropName,
      topCropSeed: topCropSeedSpoken,
      urea: formatSpeakableWeightKg(summary.totalUreaKg, locale),
      bags: formatSpeakableNumber(summary.ureaBags45Kg, locale, 0),
      procurement: formatSpeakableCurrency(
        summary.estimatedProcurementInr,
        locale,
        'INR',
      ),
    });
  }, [firstSeedCrop, locale, summary, t]);

  return (
    <div className="min-h-screen bg-slate-50 px-4 pb-24 pt-6 transition-colors duration-300 dark:bg-slate-950 sm:px-6 sm:pt-8 lg:px-8">
      <motion.main
        initial="hidden"
        animate="show"
        transition={{ staggerChildren: 0.07 }}
        className="mx-auto flex max-w-7xl flex-col gap-6"
      >
        {/* Header with Role Badge & ListenButton */}
        <motion.header
          variants={itemVariants}
          className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"
        >
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-400">
              {t('group.eyebrow')}
            </p>
            <h1 className="mt-1 text-2xl font-black tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
              {t('group.title')}
            </h1>
            <p className="mt-1 text-sm font-medium text-slate-500 dark:text-slate-400">
              {t('group.coopName')}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <ListenButton
              id="group-dashboard-listen-btn"
              text={headerSpeechText}
              ariaLabelKey="group.listenSummaryAria"
              variant="emerald"
              size="sm"
            />
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3.5 py-2 text-xs font-bold text-emerald-800 dark:border-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200 sm:text-sm">
              <BadgeCheck size={17} />
              <span>{t('group.roleBadge')}</span>
            </div>
          </div>
        </motion.header>

        {/* Dynamically Aggregated Top KPI Cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpiCards.map(({ id, label, value, suffix, detail, icon: Icon, iconClass }) => (
            <motion.section
              key={id}
              variants={itemVariants}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
                    {label}
                  </p>
                  <p className="mt-3 text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100">
                    {value}
                    {suffix && (
                      <span className="ms-1.5 text-base font-bold text-slate-500 dark:text-slate-400">
                        {suffix}
                      </span>
                    )}
                  </p>
                </div>
                <div className={`rounded-xl p-3 ${iconClass}`}>
                  <Icon size={21} />
                </div>
              </div>
              <p className="mt-4 text-xs font-medium text-slate-500 dark:text-slate-400">
                {detail}
              </p>
            </motion.section>
          ))}
        </div>

        {/* Crop-Wise Bulk Seed & Urea Demand Breakdown */}
        <motion.section
          variants={itemVariants}
          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900 sm:px-6"
        >
          <div className="flex items-center gap-2">
            <Layers size={19} className="text-emerald-600 dark:text-emerald-400" />
            <h2 className="text-base font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-lg">
              {t('group.cropDemandTitle')}
            </h2>
          </div>
          <p className="mt-1 text-xs font-medium text-slate-500 dark:text-slate-400 sm:text-sm">
            {t('group.cropDemandSubtitle')}
          </p>

          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {summary.demandByCrop.map(
              ({ cropId, areaHectares, seedKg, ureaKg, seedRateKgPerHa, ureaRateKgPerHa }) => {
                const cropName = getCropDisplayName(cropId, t);
                return (
                  <div
                    key={cropId}
                    className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50/80 p-3.5 dark:border-slate-800 dark:bg-slate-950/60"
                  >
                    <CropImage cropId={cropId} size="md" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-sm font-bold text-slate-900 dark:text-slate-100">
                          {cropName}
                        </p>
                        <span className="shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
                          {t('group.cropAreaLabel', { ha: formatNum(areaHectares, 1) })}
                        </span>
                      </div>
                      <p className="mt-1 text-xs font-semibold text-amber-700 dark:text-amber-300">
                        {t('group.cropSeedRate', {
                          kg: formatNum(seedKg),
                          rate: formatNum(seedRateKgPerHa),
                        })}
                      </p>
                      <p className="mt-0.5 text-xs font-medium text-violet-700 dark:text-violet-300">
                        {t('group.cropUreaRate', {
                          kg: formatNum(ureaKg),
                          rate: formatNum(ureaRateKgPerHa),
                        })}
                      </p>
                    </div>
                  </div>
                );
              },
            )}
          </div>
        </motion.section>

        {/* FPO Member Farmers Directory Table */}
        <motion.section
          variants={itemVariants}
          className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900"
        >
          <div className="flex flex-col gap-3 border-b border-slate-100 p-5 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <div className="flex items-center gap-2">
                <BarChart3 size={20} className="text-emerald-600 dark:text-emerald-400" />
                <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100">
                  {t('group.directoryTitle')}
                </h2>
              </div>
              <p className="mt-1 text-sm font-medium text-slate-500 dark:text-slate-400">
                {t('group.directorySubtitle')}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-slate-500 dark:text-slate-400">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <span>
                  {t('group.onTrackCount', { count: formatNum(summary.onTrackFarmers) })}
                </span>
              </span>
              <span className="ms-2 inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-amber-400" />
                <span>
                  {t('group.attentionCount', { count: formatNum(summary.attentionFarmers) })}
                </span>
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[740px] text-start">
              <thead className="bg-slate-50 dark:bg-slate-950">
                <tr className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  <th className="px-6 py-3.5 text-start">{t('group.colFarmerName')}</th>
                  <th className="px-6 py-3.5 text-start">{t('group.colVillage')}</th>
                  <th className="px-6 py-3.5 text-start">{t('group.colPrimaryCrops')}</th>
                  <th className="px-6 py-3.5 text-start">{t('group.colMappedArea')}</th>
                  <th className="px-6 py-3.5 text-start">{t('group.colInputDemand')}</th>
                  <th className="px-6 py-3.5 text-start">{t('group.colStatus')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {summary.farmerRows.map(
                  ({
                    id,
                    nameKey,
                    villageKey,
                    status,
                    plotCount,
                    areaHectares,
                    cropIds,
                    seedKg,
                    ureaKg,
                  }) => {
                    const farmerName = t(nameKey);
                    const initial = Array.from(farmerName)[0] || 'F';
                    const plotCountLabel =
                      plotCount === 1
                        ? t('group.plotCountSingle', { count: formatNum(plotCount) })
                        : t('group.plotCountPlural', { count: formatNum(plotCount) });

                    return (
                      <tr
                        key={id}
                        className="transition hover:bg-slate-50 dark:hover:bg-slate-800/60"
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-sm font-bold text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                              {initial}
                            </div>
                            <span className="font-bold text-slate-900 dark:text-slate-100">
                              {farmerName}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm font-medium text-slate-600 dark:text-slate-400">
                          {t(villageKey)}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex flex-wrap items-center gap-2">
                            {cropIds.map((cropId) => (
                              <span
                                key={cropId}
                                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200/80 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                              >
                                <CropImage cropId={cropId} size="sm" />
                                <span>{getCropDisplayName(cropId, t)}</span>
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="text-sm font-bold text-slate-800 dark:text-slate-200">
                            {formatNum(areaHectares, 1)} {t('group.hectaresUnit')}
                          </div>
                          <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
                            {plotCountLabel}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-xs font-semibold text-slate-700 dark:text-slate-300">
                          {t('group.rowSeedUrea', {
                            seed: formatNum(seedKg),
                            urea: formatNum(ureaKg),
                          })}
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${
                              STATUS_BADGE_CLASSES[status] || STATUS_BADGE_CLASSES.onTrack
                            }`}
                          >
                            {t(`group.status.${status}`)}
                          </span>
                        </td>
                      </tr>
                    );
                  },
                )}
              </tbody>
            </table>
          </div>
        </motion.section>

        {/* Bottom Dynamic Summary Strip */}
        <motion.div variants={itemVariants} className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-300">
              <IndianRupee size={17} className="text-emerald-600 dark:text-emerald-400" />
              <span>{t('group.procurementTitle')}</span>
            </div>
            <p className="mt-2 text-2xl font-black text-slate-900 dark:text-slate-100">
              {formatInrDisplay(summary.estimatedProcurementInr)}
            </p>
            <p className="mt-1 text-xs font-medium text-slate-500 dark:text-slate-400">
              {t('group.procurementDetail')}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-300">
              <Package size={17} className="text-violet-600 dark:text-violet-400" />
              <span>{t('group.attentionPlotsTitle')}</span>
            </div>
            <p className="mt-2 text-2xl font-black text-slate-900 dark:text-slate-100">
              {formatNum(summary.attentionFarmers)}
            </p>
            <p className="mt-1 text-xs font-medium text-slate-500 dark:text-slate-400">
              {t('group.attentionPlotsDetail')}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-300">
              <Users size={17} className="text-sky-600 dark:text-sky-400" />
              <span>{t('group.activeVillagesTitle')}</span>
            </div>
            <p className="mt-2 text-2xl font-black text-slate-900 dark:text-slate-100">
              {formatNum(summary.activeVillages)}
            </p>
            <p className="mt-1 text-xs font-medium text-slate-500 dark:text-slate-400">
              {t('group.activeVillagesDetail')}
            </p>
          </div>
        </motion.div>
      </motion.main>
    </div>
  );
}
