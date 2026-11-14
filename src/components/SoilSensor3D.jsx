import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Layers,
  Loader2,
  Maximize2,
  Minimize2,
  RotateCcw,
  Sparkles,
  X,
} from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';

const SPLINE_URL = 'https://my.spline.design/soilsensorcrosssection-hMG2KiNZOh6ws43ealrbxNQp/';

export default function SoilSensor3D() {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const containerRef = useRef(null);

  // Fallback timer: if onLoad doesn't fire within 5s, dismiss loader
  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 5000);
    return () => clearTimeout(timer);
  }, [reloadKey]);

  // Handle ESC key to exit fullscreen
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen]);

  const handleReload = (e) => {
    e.stopPropagation();
    setIsLoading(true);
    setReloadKey((k) => k + 1);
  };

  const toggleFullscreen = () => {
    setIsFullscreen((prev) => !prev);
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm"
      >
        {/* Card Header */}
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 px-4 py-3 sm:px-5">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-sm shadow-emerald-500/20 text-white">
              <Layers size={20} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-sm sm:text-base font-black tracking-tight text-slate-900 dark:text-slate-100 truncate">
                  {t('soil.sensor3dTitle', { defaultValue: 'Soil Sensor Cross-Section' })}
                </h2>
                <span className="hidden sm:inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:border-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  {t('soil.sensor3dBadge', { defaultValue: '3D LIVE' })}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                {t('soil.sensor3dSubtitle', { defaultValue: 'Interactive 3D probe & subsurface root-zone monitor' })}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleReload}
              title={t('soil.reload3d', { defaultValue: 'Reload 3D scene' })}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition"
              aria-label="Reload 3D view"
            >
              <RotateCcw size={15} />
            </button>
            <button
              type="button"
              onClick={toggleFullscreen}
              title={t('soil.fullscreen3d', { defaultValue: 'Maximize 3D view' })}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition"
              aria-label="Toggle Fullscreen"
            >
              <Maximize2 size={15} />
            </button>
          </div>
        </div>

        {/* 3D Canvas / iframe viewport */}
        <div
          ref={containerRef}
          className="relative h-80 sm:h-96 lg:h-[460px] xl:h-[500px] w-full bg-[#0a1730] overflow-hidden select-none"
        >
          {/* Loading Overlay */}
          <AnimatePresence>
            {isLoading && (
              <motion.div
                key="loader"
                initial={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-[#0a1730] text-white"
              >
                <div className="relative flex items-center justify-center">
                  <div className="h-12 w-12 rounded-full border-2 border-emerald-500/20 border-t-emerald-400 animate-spin" />
                  <Sparkles size={18} className="absolute text-emerald-400 animate-pulse" />
                </div>
                <div className="text-center px-4">
                  <p className="text-sm font-semibold text-slate-200">
                    {t('soil.sensor3dLoading', { defaultValue: 'Loading 3D Soil Cross-Section…' })}
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {t('soil.sensor3dPreparing', { defaultValue: 'Rendering sensor probe & soil horizons' })}
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Spline 3D Embed */}
          <iframe
            key={reloadKey}
            src={SPLINE_URL}
            title="Soil Sensor Cross-Section 3D View"
            frameBorder="0"
            width="100%"
            height="100%"
            className="h-full w-full border-0"
            allow="fullscreen"
            loading="lazy"
            onLoad={() => setIsLoading(false)}
          />

          {/* Interactive controls hint pill */}
          <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 rounded-full bg-slate-950/75 px-3 py-1.5 text-[11px] font-medium text-slate-200 backdrop-blur-md shadow-lg border border-white/10">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            <span>{t('soil.sensor3dHint', { defaultValue: 'Drag to rotate • Scroll to zoom' })}</span>
          </div>
        </div>

        {/* Soil Layer Legend */}
        <div className="grid grid-cols-3 divide-x divide-slate-100 dark:divide-slate-800 border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/60 text-center py-2.5 px-2">
          <div className="px-2">
            <p className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400">
              0 – 15 cm
            </p>
            <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 truncate">
              {t('soil.sensor3dTopsoil', { defaultValue: 'Topsoil Horizon' })}
            </p>
          </div>
          <div className="px-2">
            <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              15 – 40 cm
            </p>
            <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 truncate">
              {t('soil.sensor3dRootZone', { defaultValue: 'Active Root Zone' })}
            </p>
          </div>
          <div className="px-2">
            <p className="text-[10px] font-bold uppercase tracking-wider text-sky-600 dark:text-sky-400">
              40+ cm
            </p>
            <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 truncate">
              {t('soil.sensor3dSubsoil', { defaultValue: 'Subsoil & Moisture' })}
            </p>
          </div>
        </div>
      </motion.div>

      {/* Fullscreen Modal View */}
      <AnimatePresence>
        {isFullscreen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex flex-col bg-slate-950/95 backdrop-blur-md p-3 sm:p-6"
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-3 text-white">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-400">
                  <Layers size={18} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">
                    {t('soil.sensor3dTitle', { defaultValue: 'Soil Sensor Cross-Section' })}
                  </h3>
                  <p className="text-xs text-slate-400">
                    {t('soil.sensor3dHint', { defaultValue: 'Drag to rotate • Scroll to zoom' })}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleReload}
                  title="Reload 3D scene"
                  className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-white hover:bg-white/20 transition"
                >
                  <RotateCcw size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => setIsFullscreen(false)}
                  title="Close Fullscreen (Esc)"
                  className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-white hover:bg-red-500 transition"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Modal 3D Body */}
            <div className="relative flex-1 overflow-hidden rounded-2xl border border-white/10 bg-[#0a1730]">
              <iframe
                key={`fullscreen-${reloadKey}`}
                src={SPLINE_URL}
                title="Soil Sensor Cross-Section 3D View (Fullscreen)"
                frameBorder="0"
                width="100%"
                height="100%"
                className="h-full w-full border-0"
                allow="fullscreen"
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

