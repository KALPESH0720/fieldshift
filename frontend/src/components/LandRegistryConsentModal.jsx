/*
 * FieldShift frontend: Land Registry Consent Dialog
 * Feature: Requests explicit consent for land-document verification and registry-linked field services.
 * Impact: It protects user trust while enabling legal and documentation workflows tied to land governance.
 * Importance: This ensures the app can extend into formal land and compliance use cases without undermining consent and transparency.
 */

import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { createPortal } from 'react-dom';
import { Check, Landmark, ShieldCheck, X } from 'lucide-react';
import useScrollLock from '../hooks/useScrollLock';
import { getCountryOptions, getProviderForCountry, getSavedCountry, saveCountry } from '../services/landRegistry/registry';
import Select from './ui/Select';
import { useTranslation } from '../context/LanguageContext';

export default function LandRegistryConsentModal({ isOpen, onClose, onImport }) {
    const { t } = useTranslation();
    const [country, setCountry] = useState(getSavedCountry);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [documentFile, setDocumentFile] = useState(null);
    const provider = getProviderForCountry(country);
    useScrollLock(isOpen);

    const handleAuthorize = async () => {
        setIsLoading(true);
        setError('');
        try {
            saveCountry(country);
            await onImport(provider, documentFile);
            onClose();
        } catch (importError) {
            console.error('Land registry import failed:', importError);
            setError(importError.message || t('landRegistry.syncError'));
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
                    onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
                >
                    <motion.section role="dialog" aria-modal="true" aria-labelledby="land-registry-title" initial={{ opacity: 0, y: 20, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 12, scale: 0.96 }} className="max-h-[90dvh] w-full max-w-lg overflow-y-auto overscroll-contain rounded-2xl bg-white p-6 text-slate-900 shadow-xl dark:bg-slate-900 dark:text-slate-100">
                        <div className="flex items-start justify-between gap-4">
                            <div className="flex items-start gap-3">
                                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600"><ShieldCheck size={24} /></div>
                                <div>
                                    <div className="flex items-center gap-2"><Landmark size={15} className="text-slate-400" /><span className="text-xs font-bold uppercase tracking-wider text-slate-500">{t('landRegistry.consentLabel')}</span></div>
                                    <h2 id="land-registry-title" className="mt-1 text-xl font-bold tracking-tight">{t('landRegistry.importTitle')}</h2>
                                    <p className="mt-1 text-sm font-semibold text-emerald-700 dark:text-emerald-300">{t(provider.name)}</p>
                                </div>
                            </div>
                            <button type="button" onClick={onClose} aria-label={t('common.close')} className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 dark:hover:bg-slate-800"><X size={20} /></button>
                        </div>

                        <label className="mt-5 block text-sm font-semibold">{t('landRegistry.country')}
                            <Select aria-label={t('landRegistry.country')} value={country} onChange={(event) => setCountry(event.target.value)} className="mt-2 h-12">
                                {getCountryOptions().map(([code, label]) => <option key={code} value={code}>{label}</option>)}
                            </Select>
                        </label>

                        <p className="mt-5 text-sm font-medium leading-6 text-slate-600 dark:text-slate-300">{provider.id === 'generic' ? t('landRegistry.genericMessage') : t('landRegistry.authorizeMessage', { agency: t(provider.name) })}</p>
                        {provider.id === 'generic' && (
                            <label className="mt-4 block text-sm font-semibold">
                                {t('landRegistry.uploadDocument')}
                                <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(event) => setDocumentFile(event.target.files?.[0] || null)} className="mt-2 block w-full rounded-xl border border-dashed border-slate-300 p-3 text-sm dark:border-slate-700" />
                            </label>
                        )}
                        {provider.consentScopes.length > 0 && <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-950"><p className="text-xs font-bold uppercase tracking-wider text-slate-500">{t('landRegistry.scopes')}</p><ul className="mt-3 space-y-3">{provider.consentScopes.map((scope) => <li key={scope} className="flex items-center gap-3 text-sm font-semibold"><span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><Check size={13} /></span>{scope}</li>)}</ul></div>}
                        {error && <p className="mt-5 text-sm font-semibold text-rose-600 dark:text-rose-300" role="alert">{error}</p>}
                        <div className="mt-6 grid grid-cols-2 gap-3">
                            <button type="button" onClick={onClose} className="h-12 rounded-xl border border-slate-200 px-4 text-sm font-bold text-slate-600 dark:border-slate-700 dark:text-slate-300">{t('common.cancel')}</button>
                            <button type="button" onClick={handleAuthorize} disabled={isLoading || (provider.id === 'generic' && !documentFile)} className="h-12 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-70">{isLoading ? t('landRegistry.syncing') : error ? t('landRegistry.retry') : t('landRegistry.authorize')}</button>
                        </div>
                    </motion.section>
                </motion.div>
            )}
        </AnimatePresence>,
        document.body,
    );
}
