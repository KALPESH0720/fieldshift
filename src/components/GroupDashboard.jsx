import { motion } from 'framer-motion';
import {
    BadgeCheck,
    BarChart3,
    IndianRupee,
    LandPlot,
    Package,
    Sprout,
    Users,
} from 'lucide-react';
import CropImage from './CropImage';

const FARMERS = [
    { name: 'Ramesh Naik', village: 'Dicholi', crop: 'Cashew', size: '4.5 acres', status: 'On Track' },
    { name: 'Savitri Gaonkar', village: 'Amona', crop: 'Paddy', size: '3 acres', status: 'Sowing Delayed' },
    { name: 'Mohan Korgaonkar', village: 'Sanquelim', crop: 'Sugarcane', size: '7.2 acres', status: 'On Track' },
    { name: 'Anita Shirodkar', village: 'Mulgao', crop: 'Cashew', size: '2.8 acres', status: 'On Track' },
    { name: 'Vishnu Naik', village: 'Honda', crop: 'Paddy', size: '5 acres', status: 'Sowing Delayed' },
];

const KPI_CARDS = [
    {
        label: 'Registered Farmers',
        value: '42',
        detail: 'Across 8 villages',
        icon: Users,
        iconClass: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300',
    },
    {
        label: 'Cultivated Area',
        value: '115',
        suffix: 'Acres',
        detail: '92% actively managed',
        icon: LandPlot,
        iconClass: 'bg-sky-50 text-sky-600 dark:bg-sky-500/10 dark:text-sky-300',
    },
    {
        label: 'Bulk Seed Demand',
        value: '450 kg',
        detail: 'Paddy · 200 kg Cashew',
        icon: Sprout,
        iconClass: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300',
    },
    {
        label: 'Bulk Fertilizer Demand',
        value: '1,200 kg',
        detail: 'Urea required this cycle',
        icon: Package,
        iconClass: 'bg-violet-50 text-violet-600 dark:bg-violet-500/10 dark:text-violet-300',
    },
];

const itemVariants = {
    hidden: { opacity: 0, y: 16 },
    show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

export default function GroupDashboard() {
    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 pt-24 pb-12 px-4 sm:px-6 lg:px-8">
            <motion.main
                initial="hidden"
                animate="show"
                transition={{ staggerChildren: 0.08 }}
                className="max-w-7xl mx-auto flex flex-col gap-6"
            >
                <motion.header variants={itemVariants} className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-700">Extension workspace</p>
                        <h1 className="mt-1 text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100">FPO Overview</h1>
                        <p className="mt-1 text-sm font-medium text-slate-500 dark:text-slate-400">Dicholi Cooperative Society</p>
                    </div>
                    <div className="inline-flex w-fit items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3.5 py-2 text-sm font-bold text-emerald-800 dark:border-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200">
                        <BadgeCheck size={17} />
                        Admin / Extension Worker
                    </div>
                </motion.header>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {KPI_CARDS.map(({ label, value, suffix, detail, icon: Icon, iconClass }) => (
                        <motion.section key={label} variants={itemVariants} className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">{label}</p>
                                    <p className="mt-3 text-3xl font-black tracking-tight text-slate-900 dark:text-slate-100">
                                        {value}
                                        {suffix && <span className="ml-1 text-base font-bold text-slate-500 dark:text-slate-400">{suffix}</span>}
                                    </p>
                                </div>
                                <div className={`rounded-xl p-3 ${iconClass}`}><Icon size={21} /></div>
                            </div>
                            <p className="mt-4 text-xs font-medium text-slate-500 dark:text-slate-400">{detail}</p>
                        </motion.section>
                    ))}
                </div>

                <motion.section variants={itemVariants} className="overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm">
                    <div className="flex flex-col gap-4 border-b border-slate-100 dark:border-slate-800 p-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                        <div>
                            <div className="flex items-center gap-2">
                                <BarChart3 size={20} className="text-emerald-600" />
                                <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100">Farmer Directory</h2>
                            </div>
                            <p className="mt-1 text-sm font-medium text-slate-500 dark:text-slate-400">Monitor crop progress and coordinate group requirements.</p>
                        </div>
                        <div className="flex items-center gap-2 text-xs font-bold text-slate-500 dark:text-slate-400">
                            <span className="h-2 w-2 rounded-full bg-emerald-500" />
                            40 on track
                            <span className="ml-2 h-2 w-2 rounded-full bg-amber-400" />
                            2 need attention
                        </div>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full min-w-[700px] text-left">
                            <thead className="bg-slate-50 dark:bg-slate-950">
                                <tr className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                    <th className="px-6 py-3.5">Farmer Name</th>
                                    <th className="px-6 py-3.5">Village</th>
                                    <th className="px-6 py-3.5">Primary Crop</th>
                                    <th className="px-6 py-3.5">Plot Size</th>
                                    <th className="px-6 py-3.5">Status</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {FARMERS.map(({ name, village, crop, size, status }) => (
                                    <tr key={name} className="transition hover:bg-slate-50 dark:hover:bg-slate-800/60">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-50 text-sm font-bold text-emerald-700">{name.charAt(0)}</div>
                                                <span className="font-bold text-slate-900 dark:text-slate-100">{name}</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-sm font-medium text-slate-600 dark:text-slate-400">{village}</td>
                                        <td className="px-6 py-4">
                                            <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-300"><CropImage cropId={crop} size="sm" />{crop}</span>
                                        </td>
                                        <td className="px-6 py-4 text-sm font-semibold text-slate-700 dark:text-slate-300">{size}</td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${status === 'On Track' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300' : 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300'}`}>
                                                {status}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </motion.section>

                <motion.div variants={itemVariants} className="grid gap-4 sm:grid-cols-3">
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm">
                        <div className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-300"><IndianRupee size={17} className="text-emerald-600" /> Procurement estimate</div>
                        <p className="mt-2 text-2xl font-black text-slate-900 dark:text-slate-100">₹2.4L</p>
                        <p className="mt-1 text-xs font-medium text-slate-500 dark:text-slate-400">Expected group purchase value</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm">
                        <div className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-300"><Package size={17} className="text-violet-600" /> Open requests</div>
                        <p className="mt-2 text-2xl font-black text-slate-900 dark:text-slate-100">8</p>
                        <p className="mt-1 text-xs font-medium text-slate-500 dark:text-slate-400">Awaiting supplier confirmation</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm">
                        <div className="flex items-center gap-2 text-sm font-bold text-slate-700 dark:text-slate-300"><Users size={17} className="text-sky-600" /> Active villages</div>
                        <p className="mt-2 text-2xl font-black text-slate-900 dark:text-slate-100">8</p>
                        <p className="mt-1 text-xs font-medium text-slate-500 dark:text-slate-400">Participating in this cycle</p>
                    </div>
                </motion.div>
            </motion.main>
        </div>
    );
}