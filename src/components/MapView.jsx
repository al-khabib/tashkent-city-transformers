import { MapContainer, TileLayer, Marker, Popup, ZoomControl, Polygon, Tooltip, GeoJSON } from 'react-leaflet';
import L from 'leaflet';
import PropTypes from 'prop-types';
import { BarChart3, Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const INITIAL_CENTER = [41.3111, 69.2797];
const INITIAL_ZOOM = 12;

const HIGH_GROWTH_ZONES = [
  {
    id: 'zone-1',
    name: 'Yunusabad Redevelopment',
    color: '#38bdf8',
    coordinates: [
      [41.3505, 69.2504],
      [41.3612, 69.2848],
      [41.3436, 69.305],
      [41.3324, 69.2716],
    ],
  },
  {
    id: 'zone-2',
    name: 'Sergeli Logistics Belt',
    color: '#f97316',
    coordinates: [
      [41.24, 69.18],
      [41.2532, 69.225],
      [41.2264, 69.241],
      [41.2143, 69.1963],
    ],
  },
  {
    id: 'zone-3',
    name: 'Bektemir Industrial Cluster',
    color: '#a855f7',
    coordinates: [
      [41.2721, 69.3303],
      [41.2878, 69.3609],
      [41.2556, 69.3731],
      [41.247, 69.3378],
    ],
  },
];

const statusColors = {
  Critical: 'text-red-400',
  Watch: 'text-amber-300',
  Stable: 'text-emerald-300',
};

const loadToColor = (percent) => {
  if (percent >= 90) return '#f87171';
  if (percent >= 70) return '#facc15';
  if (percent >= 40) return '#22c55e';
  return '#94a3b8';
};

const createCurrentTpIcon = (color, scale, isFocused) => {
  const size = 30 * scale;
  return L.divIcon({
    html: `<span class="grid-marker ${isFocused ? 'ring ring-offset-2 ring-sky-400 ring-offset-slate-900' : ''}" style="background:${color};width:${size}px;height:${size}px;"><span class="grid-zap">⚡</span></span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size - 6],
    popupAnchor: [0, -18],
    className: '',
  });
};

const createSuggestedTpIcon = () =>
  L.divIcon({
    html: '<span class="grid-marker suggested-marker pulse-glow"><span class="grid-suggested-symbol">✚</span></span>',
    iconSize: [30, 30],
    iconAnchor: [15, 24],
    popupAnchor: [0, -18],
    className: '',
  });

const buildDistrictGeoJson = (stations, districtPredictionMap) => {
  if (!stations?.length) return { type: 'FeatureCollection', features: [] };
  const grouped = stations.reduce((acc, station) => {
    const key = station.district?.toLowerCase();
    if (!key) return acc;
    if (!acc[key]) acc[key] = [];
    acc[key].push(station.coordinates);
    return acc;
  }, {});

  const features = Object.entries(grouped).map(([district, points]) => {
    const lats = points.map((item) => item[0]);
    const lngs = points.map((item) => item[1]);
    const minLat = Math.min(...lats) - 0.015;
    const maxLat = Math.max(...lats) + 0.015;
    const minLng = Math.min(...lngs) - 0.015;
    const maxLng = Math.max(...lngs) + 0.015;
    const prediction = districtPredictionMap.get(district);
    return {
      type: 'Feature',
      properties: {
        district,
        load_percentage: prediction?.load_percentage ?? null,
      },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [minLng, minLat],
            [maxLng, minLat],
            [maxLng, maxLat],
            [minLng, maxLat],
            [minLng, minLat],
          ],
        ],
      },
    };
  });

  return { type: 'FeatureCollection', features };
};

function MapView({
  stations,
  allStations,
  selectedId,
  onStationSelect,
  onRequestAnalytics,
  onMapReady,
  showHighGrowthZones,
  futureMode,
  futurePrediction,
}) {
  const { t } = useTranslation();
  const districtPredictionMap = new Map(
    (futurePrediction?.district_predictions || []).map((item) => [String(item.district).toLowerCase(), item])
  );
  const districtGeoJson = buildDistrictGeoJson(allStations || stations, districtPredictionMap);
  const suggestedTpIcon = createSuggestedTpIcon();
  const futureSuggestions = futurePrediction?.suggested_tps || [];

  const getRiskLabel = (riskLabel) => {
    const normalized = (riskLabel || '').toLowerCase();
    return t(`map.risk.${normalized}`, { defaultValue: riskLabel });
  };

  return (
    <MapContainer
      center={INITIAL_CENTER}
      zoom={INITIAL_ZOOM}
      minZoom={6}
      scrollWheelZoom
      zoomControl={false}
      className="h-full w-full"
      whenCreated={onMapReady}
    >
      <ZoomControl position="bottomright" />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {futureMode && (
        <GeoJSON
          data={districtGeoJson}
          style={(feature) => {
            const load = feature?.properties?.load_percentage;
            const color = load == null ? '#64748b' : load > 90 ? '#ef4444' : load >= 70 ? '#facc15' : '#22c55e';
            return {
              color,
              fillColor: color,
              fillOpacity: 0.22,
              weight: 1.4,
            };
          }}
          onEachFeature={(feature, layer) => {
            const district = feature?.properties?.district || 'unknown';
            const load = feature?.properties?.load_percentage;
            layer.bindTooltip(
              `${district.toUpperCase()} • ${load == null ? 'N/A' : `${Math.round(load)}%`}`,
              { sticky: true }
            );
          }}
        />
      )}

      {showHighGrowthZones &&
        HIGH_GROWTH_ZONES.map((zone) => (
          <Polygon
            key={zone.id}
            positions={zone.coordinates}
            pathOptions={{
              color: zone.color,
              fillColor: zone.color,
              fillOpacity: 0.18,
              weight: 2,
            }}
          >
            <Tooltip sticky>{zone.name}</Tooltip>
          </Polygon>
        ))}

      {stations.map((station) => (
        <Marker
          key={station.id}
          position={station.coordinates}
          icon={createCurrentTpIcon(
            selectedId === station.id ? '#38bdf8' : loadToColor(station.projectedPercent),
            station.markerScale || 1,
            selectedId === station.id
          )}
          eventHandlers={{
            click: () => {
              onStationSelect?.(station);
            },
          }}
        >
          <Popup className="bg-transparent" minWidth={300} maxWidth={320}>
            <div className="rounded-2xl border border-slate-700 bg-slate-900/90 p-6 font-sans text-slate-100 shadow-xl backdrop-blur">
              <p className="text-xs uppercase tracking-[0.3em] text-slate-400">{t('map.transformer')}</p>
              <h3 className="mt-1 text-lg font-semibold text-slate-100">{station.name}</h3>
              <p className="text-xs text-slate-400">{station.district}</p>
              <div className="mt-2 inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-800/60 px-2 py-1 text-[11px] text-cyan-200">
                <Zap className="h-3 w-3" />
                Existing TP
              </div>

              <div className="mt-4 space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">{t('map.load')}:</span>
                  <span className="font-semibold text-slate-100">{station.projectedPercent}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">{t('map.capacityUtilization')}:</span>
                  <span className="font-semibold text-slate-100">
                    {Math.round((station.projectedKva / station.capacity_kva) * 100)}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">{t('map.status')}:</span>
                  <span className={`font-semibold ${statusColors[station.riskLabel] || 'text-slate-100'}`}>
                    {getRiskLabel(station.riskLabel)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">{t('map.capacity')}:</span>
                  <span className="font-semibold text-slate-100">{station.capacity_kva} kVA</span>
                </div>
                {station.maintenance && (
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">{t('map.repairs')}:</span>
                    <span className="font-semibold text-slate-100">{station.maintenance.repairs}</span>
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onRequestAnalytics?.(station);
                }}
                className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-900/90 px-3 py-2 text-sm font-semibold text-slate-100 transition hover:border-slate-500"
              >
                <BarChart3 className="h-4 w-4" />
                {t('map.deepAnalytics')}
              </button>
            </div>
          </Popup>
        </Marker>
      ))}

      {futureMode &&
        futureSuggestions.map((point) => (
          <Marker key={point.id} position={point.coordinates} icon={suggestedTpIcon}>
            <Popup className="bg-transparent" minWidth={260} maxWidth={300}>
              <div className="rounded-2xl border border-amber-500/50 bg-slate-900/95 p-4 text-slate-100 shadow-xl backdrop-blur">
                <p className="text-xs uppercase tracking-[0.3em] text-amber-300">Suggested TP</p>
                <p className="mt-1 text-sm font-semibold text-slate-100">{point.district}</p>
                <p className="text-xs text-slate-400">Future Mode placement recommendation</p>
              </div>
            </Popup>
          </Marker>
        ))}
    </MapContainer>
  );
}

MapView.propTypes = {
  stations: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
      coordinates: PropTypes.arrayOf(PropTypes.number).isRequired,
      district: PropTypes.string.isRequired,
      projectedPercent: PropTypes.number.isRequired,
      projectedKva: PropTypes.number.isRequired,
      capacity_kva: PropTypes.number.isRequired,
      riskLabel: PropTypes.string.isRequired,
      isCritical: PropTypes.bool.isRequired,
      markerScale: PropTypes.number,
      maintenance: PropTypes.shape({
        repairs: PropTypes.number,
        highLoadFailures: PropTypes.number,
        lastRepairDate: PropTypes.string,
      }),
      outages: PropTypes.arrayOf(
        PropTypes.shape({
          date: PropTypes.string.isRequired,
          duration_hours: PropTypes.number,
          cause: PropTypes.string,
        })
      ),
    })
  ).isRequired,
  allStations: PropTypes.arrayOf(
    PropTypes.shape({
      district: PropTypes.string.isRequired,
      coordinates: PropTypes.arrayOf(PropTypes.number).isRequired,
    })
  ),
  selectedId: PropTypes.string,
  onStationSelect: PropTypes.func,
  onRequestAnalytics: PropTypes.func,
  onMapReady: PropTypes.func,
  showHighGrowthZones: PropTypes.bool,
  futureMode: PropTypes.bool,
  futurePrediction: PropTypes.shape({
    district_predictions: PropTypes.arrayOf(
      PropTypes.shape({
        district: PropTypes.string,
        load_percentage: PropTypes.number,
      })
    ),
    suggested_tps: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.string,
        district: PropTypes.string,
        coordinates: PropTypes.arrayOf(PropTypes.number),
      })
    ),
  }),
};

MapView.defaultProps = {
  allStations: undefined,
  selectedId: null,
  onStationSelect: undefined,
  onRequestAnalytics: undefined,
  onMapReady: undefined,
  showHighGrowthZones: false,
  futureMode: false,
  futurePrediction: null,
};

export default MapView;
