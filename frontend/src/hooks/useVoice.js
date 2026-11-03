import { useCallback, useEffect, useId, useMemo, useState } from 'react';
import { useTranslation } from '../context/LanguageContext';
import { getLanguage, SPEECH_FALLBACKS } from '../locales/languages';
import { buildSpeechText } from '../utils/speechText';

const VOICE_LOAD_TIMEOUT_MS = 2000;
const CANCEL_DELAY_MS = 55;
const MAX_CHUNK_LENGTH = 175;
const WATCHDOG_INTERVAL_MS = 5000;
const WATCHDOG_STALL_MS = 10000;

/* ─── Browser speech support check ───────────────────────────── */
function getSpeechSynthesis() {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    return null;
  }
  return window.speechSynthesis;
}

function isSpeechSynthesisSupported() {
  return Boolean(
    getSpeechSynthesis() &&
      typeof window !== 'undefined' &&
      typeof window.SpeechSynthesisUtterance !== 'undefined',
  );
}

/* ─── Module-level singleton voice loader & cache ────────────── */
let cachedVoices = [];
let voicesLoaded = false;
let voicesLoadPromise = null;
let watcherAttached = false;
const voiceSubscribers = new Set();

function notifyVoiceSubscribers() {
  voiceSubscribers.forEach((listener) => {
    try {
      listener(cachedVoices, voicesLoaded);
    } catch {
      // ignore subscriber errors
    }
  });
}

function refreshCachedVoices() {
  const synth = getSpeechSynthesis();
  if (!synth) return [];
  const next = synth.getVoices() || [];
  if (next.length > 0) {
    cachedVoices = next;
    voicesLoaded = true;
    notifyVoiceSubscribers();
  }
  return cachedVoices;
}

function attachVoiceWatcherOnce() {
  if (watcherAttached) return;
  const synth = getSpeechSynthesis();
  if (!synth) return;
  watcherAttached = true;

  const handleVoicesChanged = () => {
    refreshCachedVoices();
  };

  if (typeof synth.addEventListener === 'function') {
    synth.addEventListener('voiceschanged', handleVoicesChanged);
  } else {
    synth.onvoiceschanged = handleVoicesChanged;
  }
}

export function ensureVoicesLoaded(timeoutMs = VOICE_LOAD_TIMEOUT_MS) {
  const synth = getSpeechSynthesis();
  if (!synth) {
    voicesLoaded = true;
    return Promise.resolve([]);
  }

  attachVoiceWatcherOnce();
  const immediate = refreshCachedVoices();
  if (immediate.length > 0) {
    return Promise.resolve(immediate);
  }

  if (voicesLoadPromise) {
    return voicesLoadPromise;
  }

  voicesLoadPromise = new Promise((resolve) => {
    let settled = false;
    let pollTimer = null;
    let timeoutTimer = null;

    const finish = () => {
      if (settled) return;
      settled = true;
      if (pollTimer) window.clearInterval(pollTimer);
      if (timeoutTimer) window.clearTimeout(timeoutTimer);
      synth.removeEventListener?.('voiceschanged', onVoices);
      const finalVoices = synth.getVoices() || [];
      cachedVoices = finalVoices;
      voicesLoaded = true;
      voicesLoadPromise = null;
      notifyVoiceSubscribers();
      resolve(cachedVoices);
    };

    const onVoices = () => {
      const list = synth.getVoices() || [];
      if (list.length > 0) {
        finish();
      }
    };

    synth.addEventListener?.('voiceschanged', onVoices);
    pollTimer = window.setInterval(() => {
      const list = synth.getVoices() || [];
      if (list.length > 0) {
        finish();
      }
    }, 100);
    timeoutTimer = window.setTimeout(finish, timeoutMs);
  });

  return voicesLoadPromise;
}

// Kick off voice discovery eagerly at module load in browser environments
if (typeof window !== 'undefined' && isSpeechSynthesisSupported()) {
  void ensureVoicesLoaded();
}

/* ─── BCP-47 voice matching & documented fallbacks ───────────── */
function normalizeTag(tag) {
  return String(tag || '').trim().replace(/_/g, '-').toLowerCase();
}

function getBaseLang(tag) {
  return normalizeTag(tag).split('-')[0] || '';
}

function scoreVoice(voice, targetTag) {
  const vTag = normalizeTag(voice.lang);
  const targetNorm = normalizeTag(targetTag);
  let score = 0;
  if (vTag === targetNorm) score += 100;
  else if (vTag.startsWith(`${getBaseLang(targetNorm)}-`)) score += 60;
  else if (vTag === getBaseLang(targetNorm)) score += 50;

  if (/natural|neural|online/i.test(voice.name || '')) score += 25;
  if (voice.localService) score += 15;
  if (voice.default) score += 5;
  return score;
}

function findVoicesForLocale(voices, targetLocale, disallowEnglish = false) {
  const targetNorm = normalizeTag(targetLocale);
  const base = getBaseLang(targetNorm);
  if (!base) return { exact: [], sameBase: [], best: null };

  const eligible = voices.filter((voice) => {
    const vBase = getBaseLang(voice.lang);
    if (!vBase) return false;
    if (disallowEnglish && vBase === 'en') return false;
    return true;
  });

  const exact = eligible.filter((v) => normalizeTag(v.lang) === targetNorm);
  const sameBase = eligible.filter((v) => {
    const vNorm = normalizeTag(v.lang);
    return vNorm === base || vNorm.startsWith(`${base}-`);
  });

  const pool = exact.length > 0 ? exact : sameBase;
  const sorted = [...pool].sort(
    (a, b) => scoreVoice(b, targetNorm) - scoreVoice(a, targetNorm) || (a.name || '').localeCompare(b.name || ''),
  );

  return {
    exact,
    sameBase,
    best: sorted[0] || null,
  };
}

export function selectVoiceForLanguage(voices, languageInfo, loaded = voicesLoaded) {
  const requestedLocale = languageInfo.speechLang || languageInfo.code || 'en-IN';
  const requestedBase = getBaseLang(requestedLocale);
  const isNonEnglish = requestedBase !== 'en';

  // 1. Exact BCP-47 match, 2. Same base language match
  const primary = findVoicesForLocale(voices, requestedLocale, isNonEnglish);
  if (primary.best) {
    const matchedLocale = primary.exact.length > 0 ? requestedLocale : (primary.best.lang || requestedLocale);
    return {
      voice: primary.best,
      utteranceLocale: matchedLocale,
      canSpeak: true,
      usedFallback: false,
      fallbackCode: null,
      availableVoices: primary.sameBase.map((v) => ({
        name: v.name,
        lang: v.lang,
        localService: Boolean(v.localService),
        isFallback: false,
      })),
    };
  }

  // 3. Documented related-language / same-script fallback (never English for non-English)
  const fallbackCandidates = SPEECH_FALLBACKS[languageInfo.code] || SPEECH_FALLBACKS[requestedBase] || [];
  for (const candidateTag of fallbackCandidates) {
    if (isNonEnglish && getBaseLang(candidateTag) === 'en') continue;
    const fb = findVoicesForLocale(voices, candidateTag, isNonEnglish);
    if (fb.best) {
      const fbBase = getBaseLang(fb.best.lang || candidateTag);
      const isCrossLanguageFallback = fbBase !== requestedBase;
      return {
        voice: fb.best,
        utteranceLocale: fb.best.lang || candidateTag,
        canSpeak: true,
        usedFallback: isCrossLanguageFallback,
        fallbackCode: isCrossLanguageFallback ? fbBase : null,
        availableVoices: fb.sameBase.map((v) => ({
          name: v.name,
          lang: v.lang,
          localService: Boolean(v.localService),
          isFallback: isCrossLanguageFallback,
        })),
      };
    }
  }

  // 4. If voices haven't finished loading yet, keep button optimistically enabled so first click awaits loader.
  //    If voices list is completely empty even after timeout (e.g. Android WebView delegating to OS TTS),
  //    continue with default voice (null) and explicit BCP-47 utterance.lang.
  if (!loaded || voices.length === 0) {
    return {
      voice: null,
      utteranceLocale: requestedLocale,
      canSpeak: true,
      usedFallback: false,
      fallbackCode: null,
      availableVoices: [],
    };
  }

  // Voices ARE loaded (voices.length > 0) and no matching or documented fallback voice exists:
  // For English, allow browser default voice; for non-English, NEVER speak with an English voice.
  if (!isNonEnglish) {
    return {
      voice: null,
      utteranceLocale: requestedLocale,
      canSpeak: true,
      usedFallback: false,
      fallbackCode: null,
      availableVoices: [],
    };
  }

  return {
    voice: null,
    utteranceLocale: requestedLocale,
    canSpeak: false,
    usedFallback: false,
    fallbackCode: null,
    availableVoices: [],
  };
}

/* ─── Natural sentence chunking (~150-180 chars) ─────────────── */
export function splitIntoSpeechChunks(text) {
  const cleaned = String(text || '').trim();
  if (!cleaned) return [];

  // Split on Latin, Devanagari (।), Arabic/Urdu (؟ ۔), and CJK (。) sentence terminators
  const rawSentences = cleaned
    .split(/(?<=[.!?।؟۔。;\n])\s+/u)
    .map((s) => s.trim())
    .filter(Boolean);

  const chunks = [];
  let current = '';

  const pushLongSegment = (segment) => {
    // Prefer splitting long sentences on commas/clauses first, then words
    const clauses = segment.split(/(?<=[,،、:])\s+/u).filter(Boolean);
    let buf = '';
    for (const clause of clauses) {
      if (clause.length <= MAX_CHUNK_LENGTH) {
        if (buf && buf.length + clause.length + 1 > MAX_CHUNK_LENGTH) {
          chunks.push(buf);
          buf = clause;
        } else {
          buf = buf ? `${buf} ${clause}` : clause;
        }
      } else {
        if (buf) {
          chunks.push(buf);
          buf = '';
        }
        const words = clause.split(/\s+/).filter(Boolean);
        for (const word of words) {
          if (buf && buf.length + word.length + 1 > MAX_CHUNK_LENGTH) {
            chunks.push(buf);
            buf = word;
          } else {
            buf = buf ? `${buf} ${word}` : word;
          }
        }
      }
    }
    if (buf) chunks.push(buf);
  };

  for (const sentence of rawSentences) {
    if (sentence.length <= MAX_CHUNK_LENGTH) {
      if (current && current.length + sentence.length + 1 <= MAX_CHUNK_LENGTH) {
        current = `${current} ${sentence}`;
      } else {
        if (current) chunks.push(current);
        current = sentence;
      }
    } else {
      if (current) {
        chunks.push(current);
        current = '';
      }
      pushLongSegment(sentence);
    }
  }

  if (current) chunks.push(current);
  return chunks;
}

/* ─── Module-level playback coordinator ──────────────────────── */
let activeGeneration = 0;
let activeOwnerId = null;
let activeNotice = null;
let activeError = null;
let cancelDelayTimer = null;
let watchdogTimer = null;
let lastBoundaryAt = 0;
let activeOnComplete = null;
let lastActiveLanguageCode = null;
const playbackSubscribers = new Set();

function notifyPlaybackSubscribers() {
  const snapshot = {
    activeOwnerId,
    notice: activeNotice,
    error: activeError,
  };
  playbackSubscribers.forEach((listener) => {
    try {
      listener(snapshot);
    } catch {
      // ignore subscriber errors
    }
  });
}

function clearTimers() {
  if (cancelDelayTimer) {
    window.clearTimeout(cancelDelayTimer);
    cancelDelayTimer = null;
  }
  if (watchdogTimer) {
    window.clearInterval(watchdogTimer);
    watchdogTimer = null;
  }
}

export function stopAllSpeech({ preserveFeedback = false } = {}) {
  const synth = getSpeechSynthesis();
  activeGeneration += 1;
  clearTimers();
  activeOwnerId = null;
  activeOnComplete = null;
  if (!preserveFeedback) {
    activeError = null;
  }
  try {
    synth?.cancel();
  } catch {
    // ignore speechSynthesis cancel errors
  }
  notifyPlaybackSubscribers();
}

export function clearVoiceFeedback() {
  activeNotice = null;
  activeError = null;
  notifyPlaybackSubscribers();
}

function startWatchdog(generation) {
  if (watchdogTimer || typeof window === 'undefined') return;
  const isChromium = /Chrome|Edg/i.test(window.navigator?.userAgent || '');
  if (!isChromium) return;

  watchdogTimer = window.setInterval(() => {
    const synth = getSpeechSynthesis();
    if (!synth || generation !== activeGeneration || !activeOwnerId) {
      clearTimers();
      return;
    }
    // Only nudge pause/resume if Chrome appears stalled mid-utterance
    if (synth.speaking && !synth.paused && Date.now() - lastBoundaryAt > WATCHDOG_STALL_MS) {
      try {
        synth.pause();
        synth.resume();
        lastBoundaryAt = Date.now();
      } catch {
        // ignore pause/resume errors
      }
    }
  }, WATCHDOG_INTERVAL_MS);
}

/* ─── Main useVoice() Hook (Single Source of Truth) ──────────── */
export default function useVoice() {
  const instanceId = useId();
  const { language, languageInfo, t } = useTranslation();

  const [voicesState, setVoicesState] = useState(() => ({
    voices: cachedVoices,
    loaded: voicesLoaded,
  }));

  const [playback, setPlayback] = useState(() => ({
    activeOwnerId,
    notice: activeNotice,
    error: activeError,
  }));

  const isSupported = useMemo(() => isSpeechSynthesisSupported(), []);

  // Subscribe to shared module-level voice list updates
  useEffect(() => {
    if (!isSupported) return undefined;
    const handleVoiceUpdate = (nextVoices, nextLoaded) => {
      setVoicesState({ voices: nextVoices, loaded: nextLoaded });
    };
    voiceSubscribers.add(handleVoiceUpdate);
    void ensureVoicesLoaded();
    return () => {
      voiceSubscribers.delete(handleVoiceUpdate);
    };
  }, [isSupported]);

  // Subscribe to shared module-level playback updates
  useEffect(() => {
    const handlePlaybackUpdate = (snapshot) => {
      setPlayback(snapshot);
    };
    playbackSubscribers.add(handlePlaybackUpdate);
    return () => {
      playbackSubscribers.delete(handlePlaybackUpdate);
    };
  }, []);

  // Stop ongoing speech immediately whenever the active language changes
  useEffect(() => {
    if (lastActiveLanguageCode === null) {
      lastActiveLanguageCode = language;
      return;
    }
    if (lastActiveLanguageCode !== language) {
      lastActiveLanguageCode = language;
      activeNotice = null;
      stopAllSpeech();
    }
  }, [language]);

  // Stop speech if the component that initiated the current utterance unmounts
  useEffect(() => {
    return () => {
      if (activeOwnerId === instanceId) {
        stopAllSpeech();
      }
    };
  }, [instanceId]);

  const selection = useMemo(
    () => selectVoiceForLanguage(voicesState.voices, languageInfo, voicesState.loaded),
    [voicesState.voices, voicesState.loaded, languageInfo],
  );

  const voiceInfo = useMemo(
    () => ({
      languageCode: languageInfo.code,
      languageName: languageInfo.nativeName,
      speechLang: languageInfo.speechLang,
      utteranceLocale: selection.utteranceLocale,
      voiceName: selection.voice?.name || null,
      voiceLang: selection.voice?.lang || null,
      hasVoice: isSupported && selection.canSpeak,
      voicesLoaded: voicesState.loaded,
      usedFallback: selection.usedFallback,
      fallbackLanguageCode: selection.fallbackCode,
      availableVoices: selection.availableVoices,
    }),
    [isSupported, languageInfo, selection, voicesState.loaded],
  );

  const stop = useCallback(() => {
    stopAllSpeech();
  }, []);

  const resolveInputText = useCallback(
    (input) => {
      if (!input) return '';
      if (typeof input === 'string') return buildSpeechText(input);
      if (Array.isArray(input)) return buildSpeechText(input);
      if (typeof input === 'object' && input.key) {
        return buildSpeechText(t(input.key, input.params || {}));
      }
      return buildSpeechText(String(input));
    },
    [t],
  );

  const speak = useCallback(
    async (input, optionsOrCallback) => {
      const onComplete =
        typeof optionsOrCallback === 'function'
          ? optionsOrCallback
          : optionsOrCallback?.onComplete || null;
      const ownerId =
        (typeof optionsOrCallback === 'object' && optionsOrCallback?.ownerId) || instanceId;

      const cleanText = resolveInputText(input);
      if (!cleanText) return false;

      const synth = getSpeechSynthesis();
      if (!synth || !isSpeechSynthesisSupported()) {
        activeError = t('voice.unsupported');
        notifyPlaybackSubscribers();
        return false;
      }

      // Cancel any ongoing speech first
      stopAllSpeech({ preserveFeedback: false });
      const generation = activeGeneration;

      // Ensure voices have loaded before selecting the voice (max ~2s wait on cold start)
      const loadedVoices = await ensureVoicesLoaded();
      if (generation !== activeGeneration) {
        return false;
      }

      const freshSelection = selectVoiceForLanguage(loadedVoices, languageInfo, true);

      if (import.meta.env.DEV) {
        console.debug('[Field Shift Voice] speak', {
          lang: freshSelection.utteranceLocale,
          requestedLang: languageInfo.speechLang,
          voice: freshSelection.voice?.name || null,
          textLength: cleanText.length,
        });
      }

      if (!freshSelection.canSpeak) {
        activeNotice = t('voice.noVoiceForLanguage', {
          language: languageInfo.nativeName || languageInfo.englishName,
        });
        activeError = activeNotice;
        notifyPlaybackSubscribers();
        return false;
      }

      if (freshSelection.usedFallback) {
        const fbLang = getLanguage(freshSelection.fallbackCode || 'hi');
        activeNotice =
          languageInfo.code === 'mr'
            ? t('voice.marathiFallback')
            : t('voice.fallbackVoiceNotice', {
                requested: languageInfo.nativeName,
                fallback: fbLang.nativeName,
              });
      } else {
        activeNotice = null;
      }
      activeError = null;

      const chunks = splitIntoSpeechChunks(cleanText);
      if (chunks.length === 0) return false;

      const queue = [...chunks];
      activeOwnerId = ownerId;
      activeOnComplete = onComplete;
      lastBoundaryAt = Date.now();
      notifyPlaybackSubscribers();

      const finishPlayback = () => {
        if (generation !== activeGeneration) return;
        clearTimers();
        activeOwnerId = null;
        const cb = activeOnComplete;
        activeOnComplete = null;
        notifyPlaybackSubscribers();
        cb?.();
      };

      const speakNextChunk = () => {
        if (generation !== activeGeneration) return;
        if (queue.length === 0) {
          finishPlayback();
          return;
        }

        const nextText = queue.shift();
        const utterance = new window.SpeechSynthesisUtterance(nextText);
        utterance.lang = freshSelection.utteranceLocale;
        if (freshSelection.voice) {
          utterance.voice = freshSelection.voice;
        }
        utterance.rate = 0.92;
        utterance.pitch = 1;

        utterance.onboundary = () => {
          lastBoundaryAt = Date.now();
        };

        utterance.onend = () => {
          lastBoundaryAt = Date.now();
          speakNextChunk();
        };

        utterance.onerror = (event) => {
          if (generation !== activeGeneration) return;
          // 'canceled' and 'interrupted' are expected when user stops or switches utterances
          if (event?.error === 'canceled' || event?.error === 'interrupted') {
            return;
          }
          clearTimers();
          activeOwnerId = null;
          const cb = activeOnComplete;
          activeOnComplete = null;
          activeError = t('voice.playbackError');
          notifyPlaybackSubscribers();
          cb?.();
        };

        lastBoundaryAt = Date.now();
        synth.speak(utterance);
      };

      // ~55 ms delay after speechSynthesis.cancel() avoids the Chromium bug that drops the next utterance
      cancelDelayTimer = window.setTimeout(() => {
        cancelDelayTimer = null;
        if (generation !== activeGeneration) return;
        startWatchdog(generation);
        speakNextChunk();
      }, CANCEL_DELAY_MS);

      return true;
    },
    [instanceId, languageInfo, resolveInputText, t],
  );

  const isSpeaking = playback.activeOwnerId === instanceId;
  const isAnySpeaking = playback.activeOwnerId !== null;

  return {
    speak,
    stop,
    isSpeaking,
    isAnySpeaking,
    isSupported,
    voiceInfo,
    notice: playback.notice,
    error: playback.error,
    clearNotice: clearVoiceFeedback,
    // Backward-compatible aliases
    supported: isSupported,
    locale: voiceInfo.utteranceLocale,
    voiceName: voiceInfo.voiceName,
    usedFallback: voiceInfo.usedFallback,
  };
}
