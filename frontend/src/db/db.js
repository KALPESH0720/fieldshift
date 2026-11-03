import Dexie from 'dexie';

// Initialize the offline database for the Field Shift PWA
export const db = new Dexie('FieldShiftDB');

// Version 1 — Core: plots, crop rules, sync outbox
db.version(1).stores({
    // Stores the farmer's plots for offline viewing
    // Verification/provenance fields are intentionally not indexed.
    plots: '++id, serverId, name, area, village',

    // Caches the ICAR/university crop rules so the recommender works offline
    cropRules: 'id, cropFamily, duration, nitrogenEffect, waterNeed',

    // The Outbox: Stores user actions (add, edit, delete) when offline to sync later
    syncQueue: '++id, action, status, timestamp',
});

// Version 2 — Phase 2: Soil Health Card records per plot
db.version(2).stores({
    // All prior tables inherited automatically
    // Verification/provenance fields are intentionally not indexed.
    plots: '++id, serverId, name, area, village',
    cropRules: 'id, cropFamily, duration, nitrogenEffect, waterNeed',
    syncQueue: '++id, action, status, timestamp',

    // Soil Health Card data keyed by plotId for per-plot soil tracking
    soilRecords: '++id, plotId, ph, nitrogen, phosphorus, potassium, timestamp',
});

db.version(3).stores({
    plots: '++id, serverId, name, area, village, providerId, externalId',
    cropRules: 'id, cropFamily, duration, nitrogenEffect, waterNeed',
    syncQueue: '++id, action, status, timestamp',
    soilRecords: '++id, plotId, ph, nitrogen, phosphorus, potassium, timestamp',
}).upgrade((tx) => tx.table('plots').toCollection().modify((plot) => {
    if (plot.source === 'agristack') plot.source = 'in-agristack';
    plot.providerId ??= plot.source === 'manual' ? 'manual' : (plot.source || 'manual');
    plot.externalId ??= plot.surveyNumber || null;
    plot.isVerified ??= Boolean(plot.provenance?.verified);
    plot.provenance ??= {
        providerId: plot.providerId,
        externalId: plot.externalId,
        verified: Boolean(plot.isVerified),
        verifiedAt: plot.verifiedAt || null,
    };
}));

db.version(4).stores({
    plots: '++id, serverId, name, area, village, providerId, externalId',
    cropRules: 'id, cropFamily, duration, nitrogenEffect, waterNeed',
    syncQueue: '++id, action, status, timestamp',
    soilRecords: '++id, plotId, ph, nitrogen, phosphorus, potassium, timestamp',
    weatherCache: 'id, updatedAt',
});

db.version(5).stores({
    plots: '++id, serverId, name, area, village, providerId, externalId',
    cropRules: 'id, cropFamily, duration, nitrogenEffect, waterNeed',
    syncQueue: '++id, action, status, timestamp',
    soilRecords: '++id, plotId, ph, nitrogen, phosphorus, potassium, timestamp',
    weatherCache: 'id, updatedAt',
    marketCache: 'id, updatedAt',
    priceAlerts: '++id, cropId, targetPrice, direction, active, triggeredAt, createdAt',
});
