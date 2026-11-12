import { apiRequest, getAuthToken } from './client';
import { db } from '../db/db';

export function coordinatesToGeoJson(coordinates) {
  if (!coordinates || !coordinates.length) return null;

  // Normalize points to [lat, lon]
  const normalized = coordinates
    .map((pt) => {
      if (Array.isArray(pt)) return [Number(pt[0]), Number(pt[1])];
      if (pt && typeof pt === 'object') {
        const lat = Number(pt.lat ?? pt.latitude);
        const lon = Number(pt.lng ?? pt.longitude ?? pt.lon);
        if (Number.isFinite(lat) && Number.isFinite(lon)) return [lat, lon];
      }
      return null;
    })
    .filter(Boolean);

  if (normalized.length >= 3) {
    // GeoJSON Polygon uses [longitude, latitude] and must be closed (min 4 vertices)
    const ring = normalized.map(([lat, lon]) => [lon, lat]);
    const first = ring[0];
    const last = ring[ring.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) {
      ring.push([first[0], first[1]]);
    }
    return {
      type: 'Polygon',
      coordinates: [ring],
    };
  }

  if (normalized.length >= 1) {
    const [lat, lon] = normalized[0];
    return {
      type: 'Point',
      coordinates: [lon, lat],
    };
  }

  return null;
}

export function geoJsonToCoordinates(location) {
  if (!location) return [];
  let parsed = location;
  if (typeof location === 'string') {
    try {
      parsed = JSON.parse(location);
    } catch {
      return [];
    }
  }
  if (parsed?.type === 'Polygon' && Array.isArray(parsed.coordinates?.[0])) {
    // GeoJSON ring is [lon, lat] -> Leaflet wants [lat, lon]
    return parsed.coordinates[0].map(([lon, lat]) => [lat, lon]);
  }
  if (parsed?.type === 'Point' && Array.isArray(parsed.coordinates)) {
    const [lon, lat] = parsed.coordinates;
    return [[lat, lon]];
  }
  return [];
}

export async function fetchPlots({ limit = 50, offset = 0 } = {}) {
  const token = getAuthToken();
  if (!token) return { items: [], total: 0 };
  return apiRequest(`/plots?limit=${limit}&offset=${offset}`, { method: 'GET' });
}

export async function createBackendPlot(plotData = {}) {
  if (!plotData || typeof plotData !== 'object') {
    throw new Error('createBackendPlot requires a plot data object');
  }

  const rawArea = plotData.areaValue ?? (String(plotData.area || '1').replace(/[^\d.]/g, '') || '1');
  const numericArea = Math.max(0.01, Number(rawArea) || 1);
  const areaUnit = String(plotData.areaUnit || 'acres').toLowerCase().includes('ha')
    ? 'hectare'
    : 'acre';

  const location = coordinatesToGeoJson(plotData.coordinates || plotData.boundaryCoordinates);

  const payload = {
    name: String(plotData.name || plotData.fieldName || 'My Plot').trim(),
    area_value: numericArea,
    area_unit: areaUnit,
    district: plotData.district || plotData.village || 'North Goa',
    irrigation_type: plotData.irrigation_type || plotData.irrigation || 'rainfed',
    ...(location ? { location } : {}),
  };

  return apiRequest('/plots', {
    method: 'POST',
    body: payload,
  });
}

export async function deleteBackendPlot(plotId) {
  return apiRequest(`/plots/${plotId}`, { method: 'DELETE' });
}

/**
 * Synchronize Dexie local database with backend plots
 */
export async function syncPlotsWithServer() {
  const token = getAuthToken();
  if (!token || (typeof navigator !== 'undefined' && !navigator.onLine)) {
    return;
  }

  try {
    const remote = await fetchPlots({ limit: 100 });
    const remotePlots = remote?.items || [];
    const localPlots = await db.plots.toArray();

    // 1. Upsert remote plots into Dexie
    for (const rPlot of remotePlots) {
      const match = localPlots.find(
        (lp) => (lp.serverId && String(lp.serverId) === String(rPlot.id)) || (lp.name === rPlot.name && !lp.serverId),
      );

      const coords = geoJsonToCoordinates(rPlot.location);
      const numericArea = Number(rPlot.area_value) || 1;
      const isHectare = rPlot.area_unit === 'hectare';
      const areaHectares = Number((numericArea * (isHectare ? 1 : 0.404686)).toFixed(4));

      const plotDoc = {
        name: rPlot.name,
        area: `${rPlot.area_value} ${rPlot.area_unit}s`,
        areaUnit: isHectare ? 'hectares' : 'acres',
        areaHectares,
        village: rPlot.district || '',
        serverId: rPlot.id,
        isVerified: true,
        source: 'backend',
        providerId: 'fieldshift-api',
        boundaryCoordinates: coords,
        coordinates: coords,
        irrigation_type: rPlot.irrigation_type,
      };

      if (match) {
        await db.plots.update(match.id, {
          ...plotDoc,
          primaryCrop: match.primaryCrop || 'wheat',
        });
      } else {
        await db.plots.add({
          ...plotDoc,
          primaryCrop: 'wheat',
        });
      }
    }

    // 2. Upload any local plots not yet on server
    const freshLocal = await db.plots.toArray();
    for (const lp of freshLocal) {
      if (!lp.serverId && lp.name) {
        try {
          const created = await createBackendPlot(lp);
          if (created?.id) {
            await db.plots.update(lp.id, { serverId: created.id });
          }
        } catch (e) {
          console.warn('Could not upload local plot to server:', lp.name, e);
        }
      }
    }
  } catch (err) {
    console.warn('Plot sync failed gracefully:', err);
  }
}

