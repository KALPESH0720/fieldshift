import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Download, X, Smartphone, Wifi } from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
//  InstallPrompt.jsx
//
//  Listens for the browser's native "beforeinstallprompt" event and renders
//  a polished glassmorphism install banner fixed above the bottom nav bar.
//
//  MECHANIC:
//    • The browser fires beforeinstallprompt only when the PWA is installable
//      (manifest OK, service worker registered, not already installed).
//    • We stash the event, prevent its default mini-infobar, then show our
//      premium banner instead.
//    • Dismissal is persisted in localStorage so the banner doesn't reappear
//      until the next browser session.
//
//  PLACEMENT: Render anywhere in the tree (e.g. App.jsx or PlotList.jsx).
//  The component is fixed-position so it works from any route.
// ─────────────────────────────────────────────────────────────────────────────

const DISMISS_KEY = 'fieldshift_installDismissed';

export default function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [isVisible, setIsVisible] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    // Already dismissed this session? bail out.
    if (localStorage.getItem(DISMISS_KEY) === 'true') return;

    // Already installed as a standalone app? bail out.
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true);
      return;
    }

    const handleBeforeInstall = (e) => {
      // Stash the event so we can trigger it later from our button.
      e.preventDefault();
      setDeferredPrompt(e);
      setIsVisible(true);
    };

    const handleAppInstalled = () => {
      setIsInstalled(true);
      setIsVisible(false);
      setDeferredPrompt(null);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstall);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  const handleInstall = useCallback(async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setIsVisible(false);
    }
    setDeferredPrompt(null);
  }, [deferredPrompt]);

  const handleDismiss = useCallback(() => {
    setIsVisible(false);
    localStorage.setItem(DISMISS_KEY, 'true');
  }, []);

  // Don't render anything if already installed or never showed
  if (isInstalled) return null;

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0, y: 80 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 80, transition: { duration: 0.25 } }}
          transition={{ type: 'spring', stiffness: 380, damping: 32, delay: 0.5 }}
          // Fixed just above the 64px bottom nav bar (pb-16 on App shell)
          className="fixed bottom-16 left-0 right-0 z-50 px-3 sm:px-4"
          role="banner"
          aria-label="Install Field Shift as an app"
        >
          <div className="mx-auto max-w-lg">
            {/* Glassmorphism card */}
            <div className="relative overflow-hidden rounded-2xl border border-emerald-500/25 bg-slate-900/90 backdrop-blur-xl shadow-2xl shadow-slate-950/50">

              {/* Animated top accent border */}
              <motion.div
                className="absolute inset-x-0 top-0 h-px"
                style={{
                  background: 'linear-gradient(90deg, transparent, #10b981, #14b8a6, #10b981, transparent)',
                }}
                animate={{ backgroundPosition: ['0% 0%', '100% 0%', '0% 0%'] }}
                transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
              />

              <div className="flex items-center gap-3.5 p-4">
                {/* App icon badge */}
                <div className="shrink-0 h-12 w-12 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-900/40">
                  <Smartphone size={22} className="text-white" />
                </div>

                {/* Text content */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-white tracking-tight leading-tight">
                    Add Field Shift to your phone
                  </p>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Wifi size={11} className="text-emerald-400 shrink-0" />
                    <p className="text-xs text-slate-400 leading-relaxed truncate">
                      Works offline · No app store needed
                    </p>
                  </div>
                </div>

                {/* Install button */}
                <motion.button
                  type="button"
                  id="pwa-install-btn"
                  onClick={handleInstall}
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.95 }}
                  className="shrink-0 flex items-center gap-1.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white text-xs font-bold px-3.5 py-2.5 rounded-xl shadow-md shadow-emerald-900/30 transition-all focus:outline-none focus:ring-2 focus:ring-emerald-400 min-h-[42px]"
                  aria-label="Install the app"
                >
                  <Download size={14} />
                  <span>Install</span>
                </motion.button>

                {/* Dismiss X */}
                <button
                  type="button"
                  onClick={handleDismiss}
                  aria-label="Dismiss install prompt"
                  className="shrink-0 p-1.5 rounded-xl text-slate-500 hover:text-slate-200 hover:bg-slate-700/60 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 ml-0.5"
                >
                  <X size={15} />
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
