import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { VitePWA } from 'vite-plugin-pwa';

// ─────────────────────────────────────────────────────────────────────────────
//  vite.config.js  —  Field Shift PWA
//
//  PWA STRATEGY:
//    • registerType: 'autoUpdate'  → service worker silently replaces itself
//      when a new build is detected; no "Click to reload" prompt needed.
//    • cleanupOutdatedCaches: true → drops outdated Workbox precaches.
//    • Precache captures app shell + verified 128px crop thumbnails with content
//      revision hashes; runtime cache ('crop-card-images-v3') caches 480px cards.
// ─────────────────────────────────────────────────────────────────────────────

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  plugins: [
    react(),
    tailwindcss(),

    VitePWA({
      // ── Service Worker registration ──────────────────────────────────────
      registerType: 'autoUpdate',

      // Include the service worker in the Vite dev server so it works
      // in development mode as well as production.
      devOptions: {
        enabled: true,
        type: 'module',
      },

      // ── Web App Manifest ─────────────────────────────────────────────────
      manifest: {
        name: 'Field Shift',
        short_name: 'Field Shift',
        description: 'Offline-first smart crop rotation and soil management for Indian farmers.',
        start_url: '/farm',
        display: 'standalone',
        background_color: '#0f172a',
        theme_color: '#0f172a',
        orientation: 'portrait-primary',
        lang: 'en',
        categories: ['agriculture', 'productivity', 'utilities'],
        icons: [
          {
            src: '/icon-192.svg',
            sizes: '192x192',
            type: 'image/svg+xml',
            purpose: 'any',
          },
          {
            src: '/icon-512.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'any maskable',
          },
        ],
      },

      // ── Workbox caching rules ─────────────────────────────────────────────
      workbox: {
        // Precache app shell and 128px crop thumbnails; runtime-cache 480px card photos
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2}', 'crops/*-thumb.webp'],
        globIgnores: ['**/crops/*-card.webp', '**/crops-removed/**', '**/crop-preview.html'],

        // Drop outdated precaches and activate the updated service worker immediately
        cleanupOutdatedCaches: true,
        skipWaiting: true,
        clientsClaim: true,
        ignoreURLParametersMatching: [/^v$/, /^utm_/, /^fbclid$/],

        runtimeCaching: [
          // ── 0a. Crop card photographs (480px WebP, CacheFirst v2 for offline) ─
          {
            urlPattern: /\/crops\/.*-card\.webp(\?.*)?$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'crop-card-images-v3',
              expiration: { maxEntries: 80, maxAgeSeconds: 60 * 60 * 24 * 90 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // ── 0b. Crop thumb photographs (128px WebP, v2 runtime fallback) ──────
          {
            urlPattern: /\/crops\/.*-thumb\.webp(\?.*)?$/i,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'crop-thumb-images-v3',
              expiration: { maxEntries: 80, maxAgeSeconds: 60 * 60 * 24 * 90 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // ── 1. Google Fonts stylesheets ──────────────────────────────────────
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-stylesheets',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // ── 2. Google Fonts files ────────────────────────────────────────────
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-webfonts',
              expiration: { maxEntries: 30, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // ── 3. Spline 3D CDN assets ──────────────────────────────────────────
          {
            urlPattern: /^https:\/\/prod\.spline\.design\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'spline-3d-assets',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // ── 3b. Tesseract OCR worker, WASM core & traineddata assets ─────────
          {
            urlPattern: /^https:\/\/(?:cdn\.jsdelivr\.net|tessdata\.projectnaptha\.com)\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'tesseract-ocr-assets-v1',
              expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 180 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // ── 4. Field Shift backend API (stale-while-revalidate) ──────────────
          {
            urlPattern: /^https:\/\/.*\/api\/v1\/.*/i,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'fieldshift-api-cache',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          // ── 5. All other non-crop static image assets ────────────────────────
          {
            urlPattern: ({ url }) =>
              !url.pathname.startsWith('/crops/') &&
              /\.(?:png|jpg|jpeg|svg|gif|webp|ico)$/i.test(url.pathname),
            handler: 'CacheFirst',
            options: {
              cacheName: 'static-images-v2',
              expiration: { maxEntries: 60, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
});
