import { useEffect, useMemo, useState } from 'react';
import { LandPlot, Leaf, Volume2 } from 'lucide-react';
import useVoice from '../hooks/useVoice';
import { useTranslation } from '../context/LanguageContext';
import {
    getCropDisplayName,
    getCropLocalName,
    logMissingCropPhotosWarning,
    reportFailedCropImage,
    resolveKnownCrop,
} from '../data/crops';

const SIZES = {
    xs: { box: 'h-9 w-9', px: 36, icon: 14, text: 'text-[10px]' },
    sm: { box: 'h-12 w-12', px: 48, icon: 16, text: 'text-xs' },
    md: { box: 'h-20 w-20', px: 80, icon: 22, text: 'text-sm' },
    lg: { box: 'h-32 w-32 sm:h-40 sm:w-40', px: 160, icon: 32, text: 'text-base' },
    hero: { box: 'h-44 w-44 sm:h-52 sm:w-52', px: 208, icon: 40, text: 'text-lg' },
};

function getInitials(label) {
    const cleaned = String(label || '').trim();
    if (!cleaned) return '';
    const parts = cleaned.split(/[\s-]+/).filter(Boolean);
    if (parts.length >= 2) {
        return `${parts[0][0] || ''}${parts[1][0] || ''}`.toUpperCase();
    }
    return cleaned.slice(0, 2).toUpperCase();
}

export default function CropImage({
    cropId,
    crop: cropProp,
    size = 'md',
    showName = false,
    speakOnTap = false,
    className = '',
    imgClassName = '',
}) {
    const { t } = useTranslation();
    const { speak } = useVoice();
    const crop = resolveKnownCrop(cropId || cropProp?.id);
    const [failedSrc, setFailedSrc] = useState(null);
    const [loadedSrc, setLoadedSrc] = useState(null);

    const dimensions = SIZES[size] || SIZES.md;
    const targetSrc = crop && crop.hasPhoto
        ? (size === 'lg' || size === 'hero' ? crop.card : crop.thumb)
        : null;
    const failed = !targetSrc || failedSrc === targetSrc;
    const loaded = Boolean(targetSrc) && loadedSrc === targetSrc;

    const name = useMemo(() => {
        if (crop) return getCropDisplayName(crop, t);
        if (typeof cropId === 'string' && cropId.trim()) return cropId.trim();
        return t('crops.other.name');
    }, [crop, cropId, t]);

    const localName = useMemo(() => (crop ? getCropLocalName(crop, t) : ''), [crop, t]);
    const alt = useMemo(() => name || crop?.id || 'crop', [name, crop]);
    const initials = useMemo(() => getInitials(name || crop?.id), [name, crop]);
    const isMissingKnownPhoto = Boolean(crop) && failed;

    useEffect(() => {
        logMissingCropPhotosWarning();
        if (crop && !crop.hasPhoto) {
            reportFailedCropImage(crop.id);
        }
    }, [crop]);

    const handleSpeak = () => {
        if (speakOnTap && name) speak(name);
    };

    const handleError = () => {
        if (targetSrc) {
            setFailedSrc(targetSrc);
        }
        if (crop?.id) {
            reportFailedCropImage(crop.id);
        }
    };

    return (
        <div
            data-crop-id={crop?.id || 'unmapped'}
            className={`flex shrink-0 flex-col items-center gap-1 ${className}`}
        >
            <div
                role={speakOnTap ? 'button' : undefined}
                tabIndex={speakOnTap ? 0 : undefined}
                onClick={speakOnTap ? handleSpeak : undefined}
                onKeyDown={speakOnTap ? (event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        handleSpeak();
                    }
                } : undefined}
                aria-label={speakOnTap ? t('crops.listenTo', { name }) : undefined}
                style={{ width: dimensions.px, height: dimensions.px }}
                className={`relative shrink-0 overflow-hidden rounded-2xl bg-slate-100 ring-1 ring-slate-200/90 dark:bg-slate-800/90 dark:ring-slate-700/80 ${dimensions.box} ${speakOnTap ? 'cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500' : 'cursor-default'} ${import.meta.env?.DEV && isMissingKnownPhoto ? 'ring-2 ring-amber-500/80' : ''}`}
            >
                {!failed ? (
                    <>
                        {!loaded && (
                            <span
                                aria-hidden="true"
                                className="absolute inset-0 animate-pulse bg-slate-200/90 dark:bg-slate-800"
                            />
                        )}
                        <img
                            src={targetSrc}
                            alt={alt}
                            width={dimensions.px}
                            height={dimensions.px}
                            loading={size === 'hero' ? 'eager' : 'lazy'}
                            decoding="async"
                            onLoad={() => setLoadedSrc(targetSrc)}
                            onError={handleError}
                            className={`relative block h-full w-full object-cover transition-opacity duration-200 ${loaded ? 'opacity-100' : 'opacity-0'} ${imgClassName}`}
                        />
                    </>
                ) : (
                    <span
                        aria-hidden="true"
                        title={name}
                        className="flex h-full w-full flex-col items-center justify-center gap-0.5 bg-slate-100 text-slate-500 dark:bg-slate-800/80 dark:text-slate-400"
                    >
                        {crop || (typeof cropId === 'string' && cropId.trim()) ? (
                            <Leaf size={dimensions.icon} className="stroke-[1.75] opacity-75" />
                        ) : (
                            <LandPlot size={dimensions.icon} className="stroke-[1.75] opacity-75" />
                        )}
                        {initials && (
                            <span className={`${dimensions.text} select-none font-bold uppercase tracking-wider leading-none opacity-80`}>
                                {initials}
                            </span>
                        )}
                        {import.meta.env?.DEV && isMissingKnownPhoto && (
                            <span className="absolute inset-x-0 bottom-0 bg-amber-500/95 px-1 py-0.5 text-center text-[8px] font-extrabold uppercase leading-none text-slate-950">
                                !img
                            </span>
                        )}
                    </span>
                )}
                {speakOnTap && (
                    <Volume2
                        size={14}
                        className="absolute bottom-1 end-1 rounded-full bg-slate-950/75 p-0.5 text-white shadow-sm"
                    />
                )}
            </div>
            {showName && (
                <span className="max-w-[9rem] text-center text-sm font-semibold leading-tight text-slate-800 dark:text-slate-100">
                    {name}
                </span>
            )}
            {showName && localName && localName !== name && (
                <span className="max-w-[9rem] text-center text-xs text-slate-500 dark:text-slate-400">
                    {localName}
                </span>
            )}
        </div>
    );
}
