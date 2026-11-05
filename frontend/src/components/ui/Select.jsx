import { ChevronDown } from 'lucide-react';

export default function Select({ className = '', wrapperClassName = '', children, ...props }) {
  return (
    <div className={`relative min-w-0 ${wrapperClassName}`}>
      <select
        {...props}
        className={`min-h-11 w-full appearance-none rounded-xl border border-slate-300 bg-white ps-3 pe-9 text-[15px] font-medium text-slate-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 [&>option]:bg-white [&>option]:text-slate-900 dark:[&>option]:bg-slate-900 dark:[&>option]:text-slate-100 ${className}`}
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden="true"
        size={16}
        className="pointer-events-none absolute end-3 top-1/2 -translate-y-1/2 text-slate-500 dark:text-slate-400"
      />
    </div>
  );
}
