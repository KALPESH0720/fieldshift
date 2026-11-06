/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'fieldshift-theme';
const ThemeContext = createContext(null);

function getStoredTheme() {
    const stored = window.localStorage.getItem(STORAGE_KEY) || window.localStorage.getItem('field-shift-theme');
    return stored === 'dark' || stored === 'light' || stored === 'system' ? stored : 'system';
}

function getSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeProvider({ children }) {
    const [theme, setTheme] = useState(getStoredTheme);
    const [systemTheme, setSystemTheme] = useState(getSystemTheme);
    const resolvedTheme = theme === 'system' ? systemTheme : theme;

    useEffect(() => {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        const handleChange = (event) => setSystemTheme(event.matches ? 'dark' : 'light');
        mediaQuery.addEventListener('change', handleChange);
        return () => mediaQuery.removeEventListener('change', handleChange);
    }, []);

    useEffect(() => {
        document.documentElement.classList.toggle('dark', resolvedTheme === 'dark');
        document.documentElement.style.colorScheme = resolvedTheme;
        window.localStorage.setItem(STORAGE_KEY, theme);
    }, [resolvedTheme, theme]);

    const value = useMemo(() => ({
        theme,
        resolvedTheme,
        setTheme,
        toggleTheme: () => setTheme((current) => current === 'dark' ? 'light' : 'dark'),
    }), [resolvedTheme, theme]);

    return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (!context) throw new Error('useTheme must be used within ThemeProvider');
    return context;
}
