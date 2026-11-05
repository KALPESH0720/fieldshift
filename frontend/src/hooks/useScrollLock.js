/*
 * FieldShift frontend: Scroll Lock Hook
 * Feature: Prevents background page scrolling when modal overlays or onboarding drawers are open.
 * Impact: This keeps the mobile experience focused and avoids visual jank while important flows are active.
 * Importance: Modal focus control is necessary for clear, accessible interaction patterns.
 */

import { useEffect } from 'react';

let lockCount = 0;
let originalOverflow = '';
let originalPaddingRight = '';

export default function useScrollLock(locked) {
    useEffect(() => {
        if (!locked || typeof document === 'undefined') return undefined;

        if (lockCount === 0) {
            originalOverflow = document.body.style.overflow;
            originalPaddingRight = document.body.style.paddingRight;
            const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
            document.body.style.overflow = 'hidden';
            if (scrollbarWidth > 0) {
                document.body.style.paddingRight = `${scrollbarWidth}px`;
            }
        }
        lockCount += 1;

        return () => {
            lockCount = Math.max(0, lockCount - 1);
            if (lockCount === 0) {
                document.body.style.overflow = originalOverflow;
                document.body.style.paddingRight = originalPaddingRight;
                originalOverflow = '';
                originalPaddingRight = '';
            }
        };
    }, [locked]);
}
