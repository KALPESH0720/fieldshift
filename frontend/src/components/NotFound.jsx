/*
 * FieldShift frontend: Not Found State
 * Feature: Displays a graceful fallback screen when a user navigates to an unknown route or dead-end page.
 * Impact: It keeps the app experience stable and reduces confusion during navigation issues.
 * Importance: Good fallback states preserve trust and prevent users from feeling stranded inside the product.
 */

import { Link } from 'react-router-dom';
import { ArrowLeft, SearchX } from 'lucide-react';

export default function NotFound() {
    return (
        <main className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950 px-4 py-16">
            <div className="w-full max-w-md rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center shadow-sm">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
                    <SearchX size={28} />
                </div>
                <p className="mt-6 text-sm font-bold uppercase tracking-[0.18em] text-emerald-700">Page not found</p>
                <h1 className="mt-2 text-4xl font-black tracking-tight text-slate-900 dark:text-slate-100">404</h1>
                <p className="mt-3 text-sm font-medium leading-6 text-slate-500 dark:text-slate-400">The page you are looking for does not exist or may have moved.</p>
                <Link
                    to="/"
                    className="mt-6 inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
                >
                    <ArrowLeft size={16} />
                    Return Home
                </Link>
            </div>
        </main>
    );
}
