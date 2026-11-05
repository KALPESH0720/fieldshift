/*
 * FieldShift frontend: Land Registry Data Service
 * Feature: Stores and retrieves land ownership and document metadata needed for registry-linked features.
 * Impact: It gives the app a way to persist land-document context and support compliance-driven workflows.
 * Importance: This is key for trusted field identity and legal grade assurance in agriculture operations.
 */

import { getMockProviders } from './mockProviders';

const COUNTRY_KEY = 'fieldshift-country';
const providers = getMockProviders();

export function listProviders() {
    return providers;
}

export function getProviderForCountry(countryCode) {
    const normalized = String(countryCode || '').toUpperCase();
    return providers.find((provider) => provider.countryCodes.includes(normalized)) || providers.find((provider) => provider.id === 'generic');
}

export function getSavedCountry() {
    return window.localStorage.getItem(COUNTRY_KEY) || 'IN';
}

export function saveCountry(countryCode) {
    window.localStorage.setItem(COUNTRY_KEY, String(countryCode).toUpperCase());
}

export function getCountryOptions() {
    return [
        ['IN', 'India'],
        ['BR', 'Brazil'],
        ['EU', 'European Union'],
        ['US', 'United States'],
        ['AU', 'Australia'],
        ['KE', 'Kenya'],
        ['NG', 'Nigeria'],
        ['ID', 'Indonesia'],
        ['PH', 'Philippines'],
        ['BD', 'Bangladesh'],
        ['VN', 'Vietnam'],
        ['AR', 'Argentina'],
    ];
}

export function detectCountry() {
    return getSavedCountry();
}

