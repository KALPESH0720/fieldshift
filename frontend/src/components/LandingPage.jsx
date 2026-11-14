import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Leaf, Sparkles } from 'lucide-react';

const SPLINE_EARTH_URL = 'https://my.spline.design/holographicearthsatellitescan-Y4eqH49KZPSzablKqMfg8PDQ/';

export default function LandingPage() {
  const navigate = useNavigate();
  const [isSplineLoaded, setIsSplineLoaded] = useState(false);

  return (
    <div className="relative w-full h-screen bg-[#020617] overflow-hidden font-sans flex items-center justify-center select-none">
      {/* 3D Spline Holographic Earth Background */}
      <iframe
        src={SPLINE_EARTH_URL}
        frameBorder="0"
        width="100%"
        height="100%"
        title="Holographic Earth Satellite Scan 3D Animation"
        className={`absolute inset-0 w-full h-full border-0 transition-opacity duration-1000 z-0 ${
          isSplineLoaded ? 'opacity-100' : 'opacity-0'
        }`}
        allow="fullscreen"
        loading="eager"
        onLoad={() => setIsSplineLoaded(true)}
      />

      {/* Subtle Starfield / Loading Fallback */}
      {!isSplineLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#020617] z-0">
          <div className="flex flex-col items-center gap-3">
            <div className="h-10 w-10 rounded-full border-2 border-emerald-500/20 border-t-emerald-400 animate-spin" />
            <span className="text-xs font-semibold text-slate-400 tracking-widest uppercase">
              Initializing Satellite Scan…
            </span>
          </div>
        </div>
      )}

      {/* Live Scan Glassmorphism Indicator Badge */}
      <div className="pointer-events-none absolute top-4 left-4 sm:top-6 sm:left-6 z-10 flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3.5 py-1.5 text-[11px] font-semibold text-slate-200 backdrop-blur-xl shadow-[0_8px_32px_0_rgba(0,0,0,0.37)]">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
        </span>
        <span className="tracking-wide uppercase text-[10px] text-emerald-300 font-bold">
          NASA Satellite Live Scan
        </span>
      </div>

      {/* Glassmorphic Center Section */}
      <div className="relative z-10 p-4 sm:p-6 flex flex-col items-center text-center max-w-lg w-full">
        <motion.div
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="relative overflow-hidden rounded-3xl border border-white/25 bg-slate-950/25 p-8 md:p-12 text-white backdrop-blur-2xl backdrop-saturate-150 shadow-[0_8px_32px_0_rgba(0,0,0,0.5),0_0_0_1px_rgba(255,255,255,0.1),inset_0_1px_1px_0_rgba(255,255,255,0.3)] w-full"
        >
          {/* Top specular reflection glare for authentic glass look */}
          <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-white/15 to-transparent" />

          {/* Leaf Glass Icon */}
          <div className="relative flex justify-center mb-5">
            <div className="relative flex items-center justify-center p-4 rounded-2xl border border-white/25 bg-white/10 backdrop-blur-xl shadow-[0_0_30px_rgba(16,185,129,0.35),inset_0_1px_1px_0_rgba(255,255,255,0.3)]">
              <Leaf size={44} className="text-emerald-400 drop-shadow-[0_0_12px_rgba(52,211,153,0.7)]" />
            </div>
          </div>

          {/* NASA Badge */}
          <div className="relative inline-flex items-center gap-1.5 rounded-full border border-emerald-400/40 bg-emerald-500/15 px-3 py-1 text-xs font-bold text-emerald-300 mb-3 tracking-wide backdrop-blur-md shadow-sm">
            <Sparkles size={13} className="text-emerald-400" />
            <span>NASA EARTH DATA POWERED</span>
          </div>

          {/* Title */}
          <h1 className="relative text-4xl md:text-5xl font-black tracking-tight mb-4 text-white drop-shadow-[0_2px_10px_rgba(0,0,0,0.6)]">
            Field Shift
          </h1>

          {/* Subtitle */}
          <p className="relative text-slate-200 text-base md:text-lg mb-8 leading-relaxed font-normal drop-shadow-[0_1px_4px_rgba(0,0,0,0.7)]">
            Adapting Farms with NASA Data. Smart crop rotations, soil health tracking, and precise insights for better yields.
          </p>

          {/* Glass CTA Button */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => navigate('/login')}
            className="relative w-full overflow-hidden rounded-2xl border border-emerald-300/40 bg-gradient-to-r from-emerald-500/90 to-teal-500/90 hover:from-emerald-400 hover:to-teal-400 px-6 py-4 text-lg font-bold text-white backdrop-blur-xl shadow-[0_0_35px_rgba(16,185,129,0.45),inset_0_1px_1px_rgba(255,255,255,0.4)] transition-all hover:shadow-[0_0_50px_rgba(16,185,129,0.65)] cursor-pointer flex items-center justify-center gap-2.5"
          >
            Get Started <ArrowRight size={20} />
          </motion.button>
        </motion.div>
      </div>

      {/* Glassmorphic Footer hint */}
      <div className="pointer-events-none absolute bottom-4 text-center z-10">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3.5 py-1 text-[11px] font-medium text-slate-200 backdrop-blur-xl shadow-lg">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
          Interactive 3D Earth • Drag to rotate view
        </span>
      </div>
    </div>
  );
}
