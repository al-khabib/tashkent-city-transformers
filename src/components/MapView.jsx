import { MapContainer, TileLayer, Marker, Popup, ZoomControl, Polygon, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import PropTypes from 'prop-types';
import { BarChart3 } from 'lucide-react';
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

const createMarkerIcon = (color, label, scale, isFocused) => {
  const size = 28 * scale;
  return L.divIcon({
    html: `<span class="grid-marker ${isFocused ? 'ring ring-offset-2 ring-sky-400 ring-offset-slate-900' : ''}" style="background:${color};width:${size}px;height:${size}px;">${label}</span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size - 6],
    popupAnchor: [0, -18],
    className: '',
  });
};

function MapView({
  stations,
  selectedId,
  onStationSelect,
  onRequestAnalytics,
  onMapReady,
  showHighGrowthZones,
}) {
  const { t } = useTranslation();

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
          icon={createMarkerIcon(
            selectedId === station.id ? '#38bdf8' : loadToColor(station.projectedPercent),
            Math.round(station.projectedPercent),
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
  selectedId: PropTypes.string,
  onStationSelect: PropTypes.func,
  onRequestAnalytics: PropTypes.func,
  onMapReady: PropTypes.func,
  showHighGrowthZones: PropTypes.bool,
};

MapView.defaultProps = {
  selectedId: null,
  onStationSelect: undefined,
  onRequestAnalytics: undefined,
  onMapReady: undefined,
  showHighGrowthZones: false,
};

export default MapView;
