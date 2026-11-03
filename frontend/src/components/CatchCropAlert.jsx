import { motion } from 'framer-motion';
import { AlertTriangle, ArrowRight, Sprout, Timer } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import CropImage from './CropImage';
import ListenButton from './ui/ListenButton';

export default function CatchCropAlert({ onDismiss, onUpdatePlan }) {
  const { t } = useTranslation();
  const alertSpeech = [t('alerts.sowingCritical'), t('alerts.actionNeeded'), t('alerts.sowingDetail')];

  return (
    <motion.aside
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      role="alert"
      className="rounded-r-xl border-l-4 border-orange-500 bg-orange-50 p-4 text-orange-900 shadow-sm dark:border-orange-400 dark:bg-orange-500/10 dark:text-orange-100 sm:p-5"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-100 text-orange-600">
          <AlertTriangle size={22} />
        </div>
        <CropImage cropId="paddy" size="sm" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-bold tracking-tight sm:text-lg">{t('alerts.sowingCritical')}</h2>
              <span className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-orange-700 dark:bg-orange-500/20 dark:text-orange-100">
                <Timer size={12} />
                {t('alerts.actionNeeded')}
              </span>
            </div>
            <ListenButton text={alertSpeech} variant="amber" size="xs" />
          </div>
          <p className="mt-2 max-w-3xl text-sm font-medium leading-6 text-orange-800 dark:text-orange-100">
            {t('alerts.sowingDetail')}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onDismiss}
              className="rounded-lg px-3 py-2 text-sm font-bold text-orange-700 transition hover:bg-orange-100 focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              {t('alerts.dismiss')}
            </button>
            <button
              type="button"
              onClick={onUpdatePlan}
              className="inline-flex items-center gap-2 rounded-lg bg-orange-600 px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2"
            >
              <Sprout size={16} />
              {t('alerts.updateCropPlan')}
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </div>
    </motion.aside>
  );
}
