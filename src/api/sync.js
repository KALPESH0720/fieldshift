/**
 * sync.js
 * Drains the Dexie syncQueue by batching pending operations and POSTing them
 * to the backend /sync endpoint.
 *
 * The backend schema:
 *   POST /api/v1/sync
 *   body: { client_id, operations: [{operation_id, entity, entity_id, action, updated_at, data}], cursor, limit }
 *   response: { accepted_operation_ids, operation_results: [{operation_id, entity, entity_id, status, error}], next_cursor }
 */

import { db } from '../db/db';
import { apiRequest } from './client';
import { coordinatesToGeoJson } from './plots';

const BATCH_SIZE = 50;

/**
 * Returns a stable device-scoped client ID stored in localStorage.
 */
function getClientId() {
  const KEY = 'fieldshift-client-id';
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = `cid-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    localStorage.setItem(KEY, id);
  }
  return id;
}

/**
 * Map a Dexie syncQueue row to the backend SyncOperation schema.
 */
function mapToOperation(row) {
  const payload = row.payload || {};
  const isCreate = row.action === 'CREATE_PLOT';

  switch (row.action) {
    case 'CREATE_PLOT':
    case 'UPDATE_PLOT': {
      // Backend requires CREATE entity_id to be a non-decimal client string
      const localRef = payload.localId || payload.id || row.id;
      const entityId = isCreate
        ? `client-plot-${localRef}`
        : (payload.serverId ? String(payload.serverId) : `client-plot-${localRef}`);

      const rawUnit = String(payload.areaUnit || 'acre').toLowerCase();
      const areaUnit = rawUnit.startsWith('hect') ? 'hectare' : 'acre';
      const areaValue = Number(payload.area) || 1.0;

      const rawCoords = payload.coordinates || payload.boundaryCoordinates || payload.boundary || null;
      const location = coordinatesToGeoJson(rawCoords);

      const data = {
        name: payload.name || `Plot ${localRef}`,
        area_value: areaValue,
        area_unit: areaUnit,
        district: payload.district || payload.village || 'North Goa',
      };
      if (location) {
        data.location = location;
      }
      if (payload.irrigationType || payload.irrigation_type) {
        data.irrigation_type = payload.irrigationType || payload.irrigation_type;
      }

      return {
        operation_id: String(row.id),
        entity: 'plot',
        entity_id: entityId,
        action: isCreate ? 'create' : 'update',
        updated_at: row.timestamp
          ? new Date(row.timestamp).toISOString()
          : new Date().toISOString(),
        data,
      };
    }

    case 'DELETE_PLOT': {
      return {
        operation_id: String(row.id),
        entity: 'plot',
        entity_id: payload.serverId ? String(payload.serverId) : `client-plot-${payload.id || row.id}`,
        action: 'delete',
        updated_at: row.timestamp
          ? new Date(row.timestamp).toISOString()
          : new Date().toISOString(),
        data: {},
      };
    }

    case 'ASSIGN_PLOT_ROTATION': {
      return {
        operation_id: String(row.id),
        entity: 'crop_record',
        entity_id: `client-crop-${payload.plotId || row.id}-${payload.cropId || 'rec'}`,
        action: 'create',
        updated_at: row.timestamp
          ? new Date(row.timestamp).toISOString()
          : new Date().toISOString(),
        data: {
          plot_id: payload.serverId || payload.plotId,
          crop_name: payload.cropName || payload.cropId,
          crop_family: payload.cropFamily || 'General',
          outcome_notes: payload.notes || `Assigned via Field Shift: ${payload.cropName || payload.cropId}`,
        },
      };
    }

    default:
      return {
        operation_id: String(row.id),
        entity: 'plot',
        entity_id: `client-op-${row.id}`,
        action: 'update',
        updated_at: new Date().toISOString(),
        data: payload,
      };
  }
}

/**
 * Drain all pending rows in the syncQueue by POSTing them in batches.
 *
 * Returns:
 *   { synced: number, failed: number, skipped: number }
 */
export async function drainSyncQueue() {
  const stats = { synced: 0, failed: 0, skipped: 0 };

  // Guard: skip entirely while offline
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return stats;
  }

  const clientId = getClientId();
  let cursor = null;

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const pending = await db.syncQueue
      .where('status')
      .equals('pending')
      .limit(BATCH_SIZE)
      .toArray();

    if (!pending.length) break;

    const operations = pending.map(mapToOperation);

    let resp;
    try {
      resp = await apiRequest('/sync', {
        method: 'POST',
        body: { client_id: clientId, operations, cursor, limit: BATCH_SIZE },
      });
    } catch {
      // Network / server error — stop draining, leave rows as pending
      break;
    }

    const results = resp?.operation_results || [];
    cursor = resp?.next_cursor || null;

    // Build a map of operation_id → result for quick lookup
    const resultMap = {};
    for (const r of results) {
      resultMap[r.operation_id] = r;
    }

    for (const row of pending) {
      const result = resultMap[String(row.id)];
      if (!result) {
        // If operation was in accepted_operation_ids list without error
        if (resp?.accepted_operation_ids?.includes(String(row.id))) {
          await db.syncQueue.update(row.id, { status: 'synced' });
          stats.synced += 1;
        } else {
          stats.skipped += 1;
        }
        continue;
      }

      if (result.status === 'applied' || result.status === 'duplicate' || result.status === 'conflict') {
        // Mark as synced in Dexie
        await db.syncQueue.update(row.id, { status: 'synced' });
        stats.synced += 1;

        // If the server assigned a new serverId to a plot CREATE, persist it to Dexie plot
        if (row.action === 'CREATE_PLOT' && result.entity_id) {
          const payload = row.payload || {};
          const localPlotId = payload.localId || payload.id;
          if (localPlotId) {
            await db.plots.update(localPlotId, {
              serverId: String(result.entity_id),
            });
          }
        }
      } else if (result.status === 'rejected') {
        // Mark permanently failed with error message
        await db.syncQueue.update(row.id, {
          status: 'error',
          errorMessage: result.error?.message || 'Rejected by server',
        });
        stats.failed += 1;
      } else {
        stats.skipped += 1;
      }
    }

    // If the batch was smaller than BATCH_SIZE we've drained the queue
    if (pending.length < BATCH_SIZE) break;
  }

  return stats;
}

/**
 * Convenience: enqueue an action into the Dexie syncQueue.
 */
export async function enqueueSyncAction(action, payload) {
  await db.syncQueue.add({
    action,
    payload,
    status: 'pending',
    timestamp: Date.now(),
  });
}
