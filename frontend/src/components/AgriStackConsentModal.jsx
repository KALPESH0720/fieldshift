/*
 * FieldShift frontend: AgriStack Consent Flow
 * Feature: Captures farmer consent before sharing land, crop, or identity data with government and digital agriculture services.
 * Impact: This ensures compliance and transparency while enabling data-backed agricultural services and scheme integrations.
 * Importance: The consent layer is essential for trust, legal compliance, and wider product adoption in public-sector agricultural workflows.
 */

import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { createPortal } from 'react-dom';
import { Check, Landmark, ShieldCheck, X } from 'lucide-react';
import useScrollLock from '../hooks/useScrollLock';

const REQUESTED_DATA = ['Plot Boundaries', 'Soil Health Card', 'Subsidy Eligibility'];

export default function AgriStackConsentModal({ isOpen, onClose, onImport }) {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    useScrollLock(isOpen);
    const handleAuthorize = async () => {
        setIsLoading(true);
        setError('');
        try {
            await onImport?.();
            onClose();
        } catch (importError) {
            console.error('AgriStack import failed:', importError);
            setError('We could not sync your verified fields. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    return createPortal(
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="app-modal-layer fixed inset-0 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
                    onMouseDown={(event) => {
                        if (event.target === event.currentTarget) onClose();
                    }}
                >
                    <motion.section
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="agristack-consent-title"
                        initial={{ opacity: 0, y: 20, scale: 0.96 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 12, scale: 0.96 }}
                        transition={{ duration: 0.2, ease: 'easeOut' }}
                        className="max-h-[90dvh] w-full max-w-lg overflow-y-auto overscroll-contain rounded-2xl bg-white p-6 text-slate-900 shadow-xl dark:bg-slate-900 dark:text-slate-100"
                    >
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex items-start gap-3">
                                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                                    <ShieldCheck size={24} />
                                </div>
                                <div>
                                    <div className="flex items-center gap-2">
                                        <Landmark size={15} className="text-slate-400" />
                                        <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Government data consent</span>
                                    </div>
                                    <h2 id="agristack-consent-title" className="mt-1 text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Link AgriStack ID</h2>
                                </div>
                            </div>
                            <button
                                type="button"
                                onClick={onClose}
                                aria-label="Close AgriStack consent dialog"
                                className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        <p className="mt-6 text-sm font-medium leading-6 text-slate-600">
                            Authorize Field Shift to securely fetch your verified farm data. You can revoke this permission at any time from Settings.
                        </p>

                        <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-950">
                            <p className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Field Shift will request</p>
                            <ul className="mt-3 space-y-3">
                                {REQUESTED_DATA.map((item) => (
                                    <li key={item} className="flex items-center gap-3 text-sm font-semibold text-slate-700 dark:text-slate-300">
                                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                                            <Check size={13} strokeWidth={3} />
                                        </span>
                                        {item}
                                    </li>
                                ))}
                            </ul>
                        </div>

                        {error && <p className="mt-5 text-sm font-semibold text-rose-600 dark:text-rose-300" role="alert">{error}</p>}
                        <div className="mt-6 grid grid-cols-2 gap-3">
                            <button type="button" onClick={onClose} className="h-12 rounded-xl border border-slate-200 px-4 text-sm font-bold text-slate-600 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-400 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800">
                                Decline
                            </button>
                            <button type="button" onClick={handleAuthorize} disabled={isLoading} className="h-12 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-wait disabled:opacity-70 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2">
                                {isLoading ? 'Syncing…' : error ? 'Retry sync' : 'Authorize & Sync'}
                            </button>
                        </div>
                    </motion.section>
                </motion.div>
            )}
        </AnimatePresence>,
        document.body
    );
}
