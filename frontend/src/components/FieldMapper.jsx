import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { area as turfArea } from '@turf/area';
import { polygon as turfPolygon } from '@turf/helpers';
import L from 'leaflet';
import { CircleMarker, MapContainer, Polygon, Polyline, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import useScrollLock from '../hooks/useScrollLock';

const GOA_CENTER = [15.2993, 74.124];
const WORLD_BOUNDS = [[-85, -180], [85, 180]];
const AREA_FACTORS = { acres: 4046.8564, hectares: 10000, guntha: 101.17 };
const EARTH_RADIUS = 6378137;

function normalizeLongitude(longitude) {
    return ((longitude + 180) % 360 + 360) % 360 - 180;
}

function normalizePoint([latitude, longitude]) {
    return [latitude, normalizeLongitude(longitude)];
}

function getArea(coordinates, unit) {
    if (coordinates.length < 3) return 0;
    const closed = [...coordinates, coordinates[0]].map(([latitude, longitude]) => [longitude, latitude]);
    try {
        return turfArea(turfPolygon([closed])) / AREA_FACTORS[unit];
    } catch {
        let total = 0;
        coordinates.forEach(([latitude, longitude], index) => {
            const next = coordinates[(index + 1) % coordinates.length];
            total += (next[1] - longitude) * Math.PI / 180
                * (2 + Math.sin(latitude * Math.PI / 180) + Math.sin(next[0] * Math.PI / 180));
        });
        return Math.abs(total * EARTH_RADIUS ** 2 / 2) / AREA_FACTORS[unit];
    }
}

function getDistance([lat1, lng1], [lat2, lng2]) {
    const radians = Math.PI / 180;
    const dLat = (lat2 - lat1) * radians;
    const dLng = (lng2 - lng1) * radians;
    const a = Math.sin(dLat / 2) ** 2
        + Math.cos(lat1 * radians) * Math.cos(lat2 * radians) * Math.sin(dLng / 2) ** 2;
    return 2 * EARTH_RADIUS * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function getPerimeter(coordinates) {
    if (coordinates.length < 2) return 0;
    return coordinates.reduce((total, point, index) => total + getDistance(point, coordinates[(index + 1) % coordinates.length]), 0);
}

function MapResizer() {
    const map = useMap();
    useEffect(() => {
        const invalidate = () => {
            map.invalidateSize({ pan: false });
            const minZoom = map.getBoundsZoom(WORLD_BOUNDS, true);
            map.setMinZoom(minZoom);
            if (map.getZoom() < minZoom) map.setZoom(minZoom, { animate: false });
        };
        const observer = new ResizeObserver(invalidate);
        observer.observe(map.getContainer());
        window.addEventListener('resize', invalidate);
        invalidate();
        const timeout = setTimeout(invalidate, 250);
        return () => {
            clearTimeout(timeout);
            observer.disconnect();
            window.removeEventListener('resize', invalidate);
        };
    }, [map]);
    return null;
}

function DrawingHandler({ onAddPoint }) {
    useMapEvents({ click: (event) => onAddPoint(normalizePoint([event.latlng.lat, event.latlng.lng])) });
    return null;
}

function DraggableVertex({ point, index, onMove }) {
    const map = useMap();
    const markerRef = useRef(null);

    useEffect(() => {
        const marker = markerRef.current;
        if (!marker) return undefined;
        const handleMouseDown = (event) => {
            L.DomEvent.stop(event);
            map.dragging.disable();
            const handleMove = (moveEvent) => onMove(index, normalizePoint([moveEvent.latlng.lat, moveEvent.latlng.lng]));
            const handleUp = () => {
                map.dragging.enable();
                map.off('mousemove', handleMove);
                map.off('mouseup', handleUp);
            };
            map.on('mousemove', handleMove);
            map.once('mouseup', handleUp);
        };
        marker.on('mousedown', handleMouseDown);
        return () => {
            marker.off('mousedown', handleMouseDown);
            map.dragging.enable();
        };
    }, [index, map, onMove]);

    return (
        <CircleMarker
            ref={markerRef}
            center={point}
            radius={8}
            pathOptions={{ color: '#fff', weight: 2, fillColor: '#10b981', fillOpacity: 1 }}
            eventHandlers={{ click: (event) => L.DomEvent.stop(event.originalEvent) }}
        />
    );
}

function MapToolbar({ points, unit, onUndo, onClear, onConfirm, onClose }) {
    const map = useMap();
    const toolbarRef = useRef(null);
    useEffect(() => {
        if (!toolbarRef.current) return undefined;
        L.DomEvent.disableClickPropagation(toolbarRef.current);
        L.DomEvent.disableScrollPropagation(toolbarRef.current);
        return undefined;
    }, []);

    const locate = () => navigator.geolocation?.getCurrentPosition(
        ({ coords }) => map.flyTo([coords.latitude, coords.longitude], 16),
        () => undefined,
    );
    const area = getArea(points, unit);
    const perimeter = getPerimeter(points);

    return (
        <div ref={toolbarRef} className="absolute left-0 right-0 top-0 z-[10000] flex flex-wrap items-center gap-2 bg-slate-900/95 p-3 text-white shadow-lg backdrop-blur-sm">
            <button type="button" onClick={locate} className="min-h-11 rounded-lg bg-slate-700 px-3 text-sm font-bold">Use my location</button>
            <button type="button" onClick={onUndo} disabled={!points.length} className="min-h-11 rounded-lg bg-slate-700 px-3 text-sm font-bold disabled:opacity-40">Undo</button>
            <button type="button" onClick={onClear} disabled={!points.length} className="min-h-11 rounded-lg bg-slate-700 px-3 text-sm font-bold disabled:opacity-40">Clear</button>
            <span className="mr-auto px-1 text-xs font-semibold">{points.length} points · {area.toFixed(2)} {unit} · {perimeter.toFixed(1)} m perimeter</span>
            <button type="button" onClick={onClose} className="min-h-11 rounded-lg bg-slate-600 px-4 text-sm font-bold">Cancel</button>
            <button type="button" onClick={onConfirm} disabled={points.length < 3} className="min-h-11 rounded-lg bg-emerald-500 px-4 text-sm font-bold disabled:opacity-40">Finish</button>
        </div>
    );
}

export default function FieldMapper({ onClose, onConfirm, unit = 'acres' }) {
    const [points, setPoints] = useState([]);
    useScrollLock(true);

    useEffect(() => {
        const handleEscape = (event) => {
            event.preventDefault();
            event.stopPropagation();
            onClose();
        };
        window.addEventListener('keydown', handleEscape, true);
        return () => window.removeEventListener('keydown', handleEscape, true);
    }, [onClose]);

    const updatePoint = (index, point) => {
        setPoints((current) => current.map((item, itemIndex) => itemIndex === index ? point : item));
    };
    const handleConfirm = () => onConfirm({ area: getArea(points, unit).toFixed(2), unit, coordinates: points });

    return createPortal(
        <div className="fixed inset-0 z-[10000] h-[100dvh] w-screen overflow-hidden bg-slate-900">
            <MapContainer
                center={GOA_CENTER}
                zoom={11}
                minZoom={1}
                maxZoom={20}
                maxBounds={WORLD_BOUNDS}
                maxBoundsViscosity={1.0}
                worldCopyJump={false}
                scrollWheelZoom
                style={{ width: '100%', height: '100%', background: '#0f172a' }}
            >
                <MapResizer />
                <DrawingHandler onAddPoint={(point) => setPoints((current) => [...current, point])} />
                <TileLayer
                    attribution="&copy; Google"
                    maxZoom={20}
                    noWrap
                    bounds={WORLD_BOUNDS}
                    url="https://mt1.google.com/vt/lyrs=y,m&x={x}&y={y}&z={z}"
                />
                <MapToolbar
                    points={points}
                    unit={unit}
                    onUndo={() => setPoints((current) => current.slice(0, -1))}
                    onClear={() => setPoints([])}
                    onClose={onClose}
                    onConfirm={handleConfirm}
                />
                {points.map((point, index) => <DraggableVertex key={index} point={point} index={index} onMove={updatePoint} />)}
                {points.length > 1 && <Polyline positions={points} pathOptions={{ color: '#10b981', weight: 3 }} />}
                {points.length > 2 && <Polygon positions={points} pathOptions={{ color: '#10b981', fillColor: '#10b981', fillOpacity: 0.3 }} />}
            </MapContainer>
        </div>,
        document.body,
    );
}
