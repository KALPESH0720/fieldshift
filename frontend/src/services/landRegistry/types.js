/**
 * FieldShift frontend: Land Registry Domain Types
 * Feature: Defines the shared contract for land-registry providers and verified parcel records used by consent and validation flows.
 * Impact: This gives the frontend a stable data model for farmer land verification, reducing ambiguity as different registry integrations are plugged in.
 * Importance: Structured land verification is critical for trust, compliance, and accurate field operations in regulated agricultural systems.
 *
 * @typedef {Object} LandRegistryProvider
 * @property {string} id
 * @property {string[]} countryCodes
 * @property {string} name
 * @property {string} agencyName
 * @property {'oauth'|'idNumber'|'otp'|'mock'} authMethod
 * @property {string[]} consentScopes
 * @property {(session?: Object) => Promise<Parcel[]>} fetchVerifiedParcels
 * @property {() => boolean} isAvailable
 *
 * @typedef {Object} Parcel
 * @property {string} id
 * @property {string} parcelRef
 * @property {string} countryCode
 * @property {{type: 'Polygon', coordinates: number[][][]} | {type: 'MultiPolygon', coordinates: number[][][][]}} geometry
 * @property {number} areaHa
 * @property {string} landUse
 * @property {string} cropDeclared
 * @property {'owner'|'tenant'|'unknown'} ownerStatus
 * @property {string} source
 * @property {boolean} isVerified
 * @property {string} verifiedAt
 * @property {string} registryUrl
 */

