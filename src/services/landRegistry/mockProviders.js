import { CROPS, resolveKnownCrop } from '../../data/crops';

const CENTERS = {
    IN: [15.55, 73.83],
    BR: [-15.79, -47.88],
    EU: [52.52, 13.4],
    US: [38.9, -77.04],
    AU: [-35.28, 149.13],
    KE: [-1.29, 36.82],
    NG: [9.08, 7.4],
    ID: [-6.2, 106.82],
    PH: [14.6, 120.98],
    BD: [23.81, 90.41],
    VN: [21.03, 105.85],
    AR: [-34.6, -58.38],
};

// Valid, distinct crop IDs from src/data/crops.js for each country's mock parcels
const COUNTRY_PARCEL_CROPS = {
    IN: ['paddy', 'cashew', 'coconut'],
    BR: ['soybean', 'maize', 'coffee'],
    EU: ['wheat', 'barley', 'rapeseed'],
    US: ['maize', 'soybean', 'wheat'],
    AU: ['wheat', 'barley', 'chickpea'],
    KE: ['maize', 'tea', 'beans'],
    NG: ['cassava', 'yam', 'cowpea'],
    ID: ['rice', 'oil-palm', 'cocoa'],
    PH: ['rice', 'coconut', 'banana'],
    BD: ['paddy', 'jute', 'lentil'],
    VN: ['rice', 'coffee', 'cashew'],
    AR: ['soybean', 'maize', 'sunflower'],
};

const PARCEL_LAND_USES = ['Lowland Plot', 'Canal Block', 'Upland Terrace'];

// Mock parcels must only use crops that currently have a proper photo (distinct per parcel).
function pickAvailableCrops(preferred) {
    const picked = preferred
        .map((id) => resolveKnownCrop(id)?.id)
        .filter((id, index, list) => id && list.indexOf(id) === index);
    for (const crop of CROPS) {
        if (picked.length >= 3) break;
        if (crop.id !== 'other' && crop.id !== 'vegetables' && !picked.includes(crop.id)) picked.push(crop.id);
    }
    return picked.slice(0, 3);
}

const CONFIGS = [
    ['in-agristack', ['IN'], 'landRegistry.providers.agristack', 'AgriStack', 'mock'],
    ['br-car', ['BR'], 'landRegistry.providers.car', 'CAR / SICAR', 'mock'],
    ['eu-lpis', ['EU'], 'landRegistry.providers.lpis', 'LPIS / IACS', 'mock'],
    ['us-fsa', ['US'], 'landRegistry.providers.usda', 'USDA FSA', 'mock'],
    ['au-cadastre', ['AU'], 'landRegistry.providers.australia', 'State Cadastre', 'mock'],
    ['ke-nlis', ['KE'], 'landRegistry.providers.kenya', 'National Land Information System', 'mock'],
    ['ng-land', ['NG'], 'landRegistry.providers.nigeria', 'National Land Registry', 'mock'],
    ['id-land', ['ID'], 'landRegistry.providers.indonesia', 'National Land Agency', 'mock'],
    ['ph-land', ['PH'], 'landRegistry.providers.philippines', 'Land Management Bureau', 'mock'],
    ['bd-land', ['BD'], 'landRegistry.providers.bangladesh', 'Land Ministry Records', 'mock'],
    ['vn-land', ['VN'], 'landRegistry.providers.vietnam', 'Land Registration Office', 'mock'],
    ['ar-catastro', ['AR'], 'landRegistry.providers.argentina', 'Provincial Cadastre', 'mock'],
];

function polygonAround([lat, lng], index) {
    const offset = index * 0.006;
    return [
        [lng + offset, lat],
        [lng + 0.018 + offset, lat + 0.004],
        [lng + 0.014 + offset, lat + 0.018],
        [lng - 0.003 + offset, lat + 0.014],
        [lng + offset, lat],
    ];
}

function createMockProvider([id, countryCodes, name, agencyName]) {
    return {
        id,
        countryCodes,
        name,
        agencyName,
        authMethod: 'mock',
        consentScopes: ['parcel boundary', 'land-use record', 'eligibility status'],
        isAvailable: () => true,
        async fetchVerifiedParcels() {
            await new Promise((resolve) => setTimeout(resolve, 1200));
            const countryCode = countryCodes[0];
            const center = CENTERS[countryCode] || [0, 0];
            const crops = pickAvailableCrops(COUNTRY_PARCEL_CROPS[countryCode] || ['rice', 'wheat', 'maize']);
            return [0, 1, 2].map((index) => ({
                id: `${id}-${index + 1}`,
                parcelRef: `${countryCode}-${145 + index}/2A`,
                countryCode,
                geometry: { type: 'Polygon', coordinates: [polygonAround(center, index)] },
                areaHa: Number((1.1 + index * 0.45).toFixed(2)),
                landUse: PARCEL_LAND_USES[index] || 'Field Parcel',
                cropDeclared: crops[index],
                ownerStatus: index === 2 ? 'tenant' : 'owner',
                source: id,
                isVerified: true,
                verifiedAt: new Date().toISOString(),
                registryUrl: `https://example.org/registry/${id}/${index + 1}`,
            }));
        },
    };
}

const genericProvider = {
    id: 'generic',
    countryCodes: [],
    name: 'landRegistry.providers.generic',
    agencyName: 'Official land registry',
    authMethod: 'mock',
    consentScopes: [],
    isAvailable: () => true,
    async fetchVerifiedParcels() {
        throw new Error('Official verification is not yet available in your country. You can still map your field manually.');
    },
};

export function getMockProviders() {
    return [...CONFIGS.map(createMockProvider), genericProvider];
}
