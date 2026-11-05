/*
 * FieldShift frontend: Trust and Verification Badge
 * Feature: Displays a verification indicator to show that key actions, entities, or data sources have been validated.
 * Impact: This strengthens trust in recommendations, field records, and user-facing quality indicators.
 * Importance: Confidence in app outputs is essential when decisions affect yields, compliance, and farmer investments.
 */

import { CheckCircle2, Info } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';

export default function VerificationBadge({ isVerified = false, providerName, className = '' }) {
    const { t } = useTranslation();
    const verified = Boolean(isVerified);
    const label = verified ? t('verification.verifiedBy', { agency: providerName || 'land registry' }) : t('verification.unverified');
    const title = verified ? t('verification.verifiedTitle') : t('verification.unverifiedTitle');
    const Icon = verified ? CheckCircle2 : Info;

    return (
        <span
            title={title}
            aria-label={`${label}. ${title}`}
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold leading-4 ${
                verified
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
            } ${className}`}
        >
            <Icon size={12} aria-hidden="true" />
            <span>{label}</span>
        </span>
    );
}
