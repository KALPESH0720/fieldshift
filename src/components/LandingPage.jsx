import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Leaf } from 'lucide-react';

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="relative w-full h-screen bg-slate-950 overflow-hidden font-sans flex items-center justify-center">
      {/* Background Mesh */}
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-950/40 via-slate-950 to-blue-950/20 z-0" />

      {/* Content Card */}
      <div className="relative z-10 p-6 flex flex-col items-center text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="bg-white/5 backdrop-blur-xl border border-white/10 p-8 md:p-12 rounded-3xl text-white shadow-2xl max-w-lg w-full"
        >
          <div className="flex justify-center mb-6">
            <div className="bg-emerald-500/20 p-4 rounded-full border border-emerald-500/30">
              <Leaf size={48} className="text-emerald-400" />
            </div>
          </div>

          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4">Field Shift</h1>

          <p className="text-slate-300 text-lg mb-8 leading-relaxed">
            Adapting Farms with NASA Data. Smart crop rotations, soil health tracking, and precise insights for better yields.
          </p>

          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => navigate('/login')}
            className="w-full bg-emerald-600 text-white font-bold text-lg py-4 rounded-2xl flex items-center justify-center gap-2 hover:bg-emerald-500 transition-colors shadow-[0_0_30px_rgba(16,185,129,0.2)]"
          >
            Get Started <ArrowRight size={20} />
          </motion.button>
        </motion.div>
      </div>
    </div>
  );
}
