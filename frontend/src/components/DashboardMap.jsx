import { useEffect, useMemo } from 'react';
import { MapContainer, Polygon, TileLayer, Tooltip, useMap } from 'react-leaflet';
import { Browser, latLngBounds } from 'leaflet';
import { useTranslation } from '../context/LanguageContext';

const WORLD_CENTER = [20, 0];
const WORLD_BOUNDS = [[-85, -180], [85, 180]];

function normalizeLongitude(longitude) {
    return ((longitude + 180) % 360 + 360) % 360 - 180;
}

function getCoordinates(plot) {
    const coordinates = plot.coordinates || plot.boundaryCoordinates || [];
    return coordinates
        .map((point) => Array.isArray(point)
            ? [Number(point[0]), normalizeLongitude(Number(point[1]))]
            : [Number(point.latitude), normalizeLongitude(Number(point.longitude))])
        .filter(([latitude, longitude]) => Number.isFinite(latitude) && Number.isFinite(longitude));
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
        const resizeObserver = new ResizeObserver(invalidate);
        resizeObserver.observe(map.getContainer());
        window.addEventListener('resize', invalidate);
        const timeout = setTimeout(invalidate, 250);
        return () => {
            clearTimeout(timeout);
            resizeObserver.disconnect();
            window.removeEventListener('resize', invalidate);
        };
    }, [map]);
    return null;
}

function MapViewport({ polygons }) {
    const map = useMap();

    useEffect(() => {
        if (polygons.length === 0) {
            map.fitBounds(WORLD_BOUNDS, { padding: [0, 0], animate: false });
            return;
        }

        const bounds = latLngBounds(polygons.flat());
        map.fitBounds(bounds, { padding: [28, 28], maxZoom: 17 });
        setTimeout(() => map.invalidateSize(), 250);
    }, [map, polygons]);

    return null;
}

export default function DashboardMap({ plots = [], className = '', isExpanded = false }) {
    const { t } = useTranslation();
    const mappedPlots = useMemo(() => {
        const plotList = Array.isArray(plots) ? plots : [];
        return plotList
            .map((plot) => ({ plot, coordinates: getCoordinates(plot) }))
            .filter(({ coordinates }) => coordinates.length >= 3);
    }, [plots]);
    const polygons = mappedPlots.map(({ coordinates }) => coordinates);

    return (
        <div className={`relative isolate z-0 overflow-hidden rounded-xl ${isExpanded ? 'h-full' : 'h-[300px] md:h-[400px]'} ${className}`}>
            <MapContainer
                center={WORLD_CENTER}
                zoom={2}
                minZoom={1}
                maxZoom={20}
                maxBounds={WORLD_BOUNDS}
                maxBoundsViscosity={1.0}
                worldCopyJump={false}
                scrollWheelZoom={isExpanded}
                dragging={isExpanded || !Browser.mobile}
                className="h-full w-full bg-slate-900"
            >
                <TileLayer
                    attribution="&copy; Google Maps"
                    maxZoom={20}
                    noWrap
                    bounds={WORLD_BOUNDS}
                    url="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
                />
                <MapResizer />
                <MapViewport polygons={polygons} />
                {mappedPlots.map(({ coordinates, plot }, index) => {
                    const verified = Boolean(plot?.isVerified);
                    return (
                        <Polygon
                            key={`saved-plot-${plot?.id || index}`}
                            positions={coordinates}
                            pathOptions={{
                                color: verified ? '#16a34a' : '#a16207',
                                weight: 3,
                                dashArray: verified ? undefined : '8 7',
                                fillColor: verified ? '#22c55e' : '#f59e0b',
                                fillOpacity: verified ? 0.3 : 0.16,
                            }}
                        >
                            <Tooltip>
                                <strong>{plot?.name || 'Field'}</strong>
                                <br />
                                {verified ? t('verification.verifiedBy', { agency: plot?.providerId || 'land registry' }) : t('verification.unverified')}
                                {plot?.surveyNumber ? <><br />{plot.surveyNumber}</> : null}
                                <br />
                                {plot?.area || '—'} {plot?.areaUnit || ''}
                            </Tooltip>
                        </Polygon>
                    );
                })}
            </MapContainer>
            {polygons.length === 0 && (
                <div className="pointer-events-none absolute bottom-3 left-3 z-[500] rounded-lg bg-slate-950/70 px-3 py-2 text-xs font-semibold text-white backdrop-blur-sm">
                    No mapped fields yet — Showing Goa
                </div>
            )}
            {polygons.length > 0 && (
                <div className="pointer-events-none absolute bottom-3 left-3 z-[500] flex flex-wrap gap-2 rounded-lg bg-slate-950/75 px-3 py-2 text-[11px] font-semibold text-white backdrop-blur-sm">
                    <span className="inline-flex items-center gap-1.5"><span className="h-2 w-5 rounded border-2 border-emerald-400" /> {t('verification.verified')}</span>
                    <span className="inline-flex items-center gap-1.5"><span className="h-0 w-5 border-t-2 border-dashed border-amber-300" /> {t('verification.unverified')}</span>
                </div>
            )}
        </div>
    );
}
