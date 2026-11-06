# Offline synchronization contract, v1

`POST /api/v1/sync` requires the farmer's bearer token. `client_id` is a stable identifier for one installed client; keep it across restarts and do not share it between devices. Each `operation_id` is unique within that client and farmer. A successful operation ID is idempotent: retrying it returns the cached result and does not apply the mutation again. If the desired mutation changes, send a new operation ID. Rejected operations are not cached, so clients may correct and retry them.

## Request and entity identifiers

Every operation has an ISO-8601 `updated_at` including a timezone, one of `create`, `update`, or `delete`, an entity (`plot` or `crop_record`, with legacy aliases accepted), and a JSON `data` object. Up to 500 operations can be sent per batch; a batch returns up to 500 server changes. Create operations require a client-generated string `entity_id` such as `local:plot:72`. Crop creation may refer to that ID in `data.plot_id`, so a plot and its crop can be created in one ordered batch. Update/delete use the positive server ID returned by a prior result or change.

```json
{
  "client_id": "phone-install-72",
  "cursor": "0",
  "limit": 100,
  "operations": [
    {
      "operation_id": "op-1001",
      "entity": "plot",
      "entity_id": "local:plot:72",
      "action": "create",
      "updated_at": "2026-10-30T12:00:00Z",
      "data": {
        "name": "North field",
        "area_value": 1.2,
        "area_unit": "hectare",
        "location": {"type": "Point", "coordinates": [76.65, 12.3]}
      }
    },
    {
      "operation_id": "op-1002",
      "entity": "crop_record",
      "entity_id": "local:history:72:1",
      "action": "create",
      "updated_at": "2026-10-30T12:00:00Z",
      "data": {"plot_id": "local:plot:72", "season_id": 12, "crop_name": "Ragi"}
    }
  ]
}
```

Results are per operation. `status` is `applied`, `conflict`, `duplicate`, or `rejected`. Successful results include both `client_entity_id` and `entity_id` (the canonical server ID); clients must persist that mapping and use the server ID on subsequent updates. `accepted_operation_ids` includes applied operations and successful duplicates. A rejected item includes a stable error `code` and actionable `message`; valid siblings commit. Each operation runs in a savepoint, while all successful operations in the request commit together. A process/database failure before commit rolls back the successful portion of that request.

## Conflict and timestamp policy

Client timestamps must include a UTC offset or `Z`. A timestamp more than five minutes ahead of server time is rejected. Server `updated_at` values are authoritative for display; a separate accepted client timestamp is retained for conflict resolution. For both entities, a client update/delete wins only when its timestamp is strictly newer than both the current server update time and the last accepted client timestamp; equal or older timestamps resolve to the server. Plot geometry is a whole-value replacement, never coordinate-merged; the same strict comparison makes geometry conflict resolution deterministic. A stale delete does not delete the newer server record. Plot deletes archive the plot; crop-history deletes remove the row and publish a tombstone. Rejected updates/deletes for missing or foreign-owned rows do not expose record contents.

Creates validate the same schema as online operations, including GeoJSON type, coordinate ranges/order, WGS84 validity, closed and valid polygons, and the 25% polygon-area consistency check. Unknown entity/action values, malformed timestamps, duplicate crop/season records, invalid geometry, and ownership failures reject only that operation. A server ID returned by a prior create in the same batch is resolved when referenced by a later operation.

## Change cursors, retention, and recovery

`cursor` is an opaque decimal change sequence, initially `"0"`; treat it as a string and do not increment it locally. `server_changes` contains only events for the authenticated farmer, ordered by cursor. Follow `next_cursor`; when `has_more` is true, request another page with that cursor and an empty operations list. The sequence is global and gaps are normal because other farmers' changes are filtered out. Changes and successful idempotency records are retained durably until account deletion; no automatic pruning means a valid cursor does not expire. A malformed or future cursor is rejected with instructions to retry with `cursor: null`, which performs a full retained-change replay. Deletion events are tombstones (`action: "delete"`) and must be applied locally even when the entity is already absent.

Each device has its own cursor and operation key space, so multiple devices can pull the farmer's full shared change stream independently. All operation lookups, changes, and conflict reads are scoped to the bearer-authenticated farmer. Account deletion cascades its change log and operation records under the privacy deletion policy.
