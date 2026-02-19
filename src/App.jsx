import { useEffect, useMemo, useRef, useState } from 'react';
import MapView from './components/MapView.jsx';
import Sidebar from './components/Sidebar.jsx';
import ControlPanel from './components/ControlPanel.jsx';
import AnalyticsModal from './components/AnalyticsModal.jsx';
import TimeControlPanel from './components/TimeControlPanel.jsx';
import { useGridStress } from './hooks/useGridStress.js';

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '');

function App() {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth >= 1024 : true
  );
  const [analyticsId, setAnalyticsId] = useState(null);
  const [futureMode, setFutureMode] = useState(false);
  const [futureDate, setFutureDate] = useState(null);
  const [futureData, setFutureData] = useState(null);
  const [futureLoading, setFutureLoading] = useState(false);
  const [activeSuggestedTp, setActiveSuggestedTp] = useState(null);
  const [backendStations, setBackendStations] = useState([]);
  const [stationsLoading, setStationsLoading] = useState(true);
  const mapRef = useRef(null);
  const futureDateKey = useMemo(
    () => (futureDate ? futureDate.toISOString().slice(0, 10) : null),
    [futureDate]
  );

  // Fetch stations from backend on mount
  useEffect(() => {
    const controller = new AbortController();
    const fetchStations = async () => {
      setStationsLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/stations`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`Failed to fetch stations: ${response.status}`);
        }
        const data = await response.json();
        setBackendStations(data.stations || []);
      } catch (error) {
        if (error?.name !== 'AbortError') {
          console.error('[App] Failed to fetch backend stations:', error);
          setBackendStations([]);
        }
      } finally {
        setStationsLoading(false);
      }
    };
    fetchStations();
    return () => controller.abort();
  }, []);

  const {
    stations,
    filteredStations,
    searchMatches,
    criticalStations,
    redZoneActive,
    temperature,
    construction,
    setTemperature,
    setConstruction,
  } = useGridStress(backendStations, searchTerm);

  useEffect(() => {
    const handleResize = () => {
      const desktop = window.innerWidth >= 1024;
      setIsDesktop(desktop);
      if (desktop) {
        setSidebarOpen(false);
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (!futureMode || !futureDateKey) {
      setFutureData(null);
      setActiveSuggestedTp(null);
      return;
    }
    const controller = new AbortController();
    const runPrediction = async () => {
      setFutureLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/predict`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            target_date: futureDateKey,
          }),
        });
        if (!response.ok) {
          throw new Error(`Future mode request failed: ${response.status}`);
        }
        const payload = await response.json();
        setFutureData(payload);
      } catch (error) {
        if (error?.name !== 'AbortError') {
          console.error('[FutureMode] prediction failed', error);
          setFutureData(null);
        }
      } finally {
        setFutureLoading(false);
      }
    };
    runPrediction();
    return () => controller.abort();
  }, [futureMode, futureDateKey]);

  const handleFutureDateChange = (nextDate) => {
    if (!nextDate) return;
    if (!futureMode) {
      setFutureMode(true);
    }
    setFutureDate(nextDate);
  };

  const modalStation = useMemo(
    () => stations.find((station) => station.id === analyticsId) || null,
    [stations, analyticsId]
  );

  const flyToStation = (station) => {
    setSelectedId(station.id);
    if (mapRef.current) {
      mapRef.current.flyTo(station.coordinates, 13.2, { duration: 1.1 });
    }
    if (!isDesktop) {
      setSidebarOpen(false);
    }
  };

  const handleMapReady = (mapInstance) => {
    mapRef.current = mapInstance;
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100">
      {isDesktop && (
        <Sidebar
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          temperature={temperature}
          onTemperatureChange={setTemperature}
          construction={construction}
          onConstructionChange={setConstruction}
          searchMatches={searchMatches}
          criticalStations={criticalStations}
          onSelectStation={flyToStation}
          redZoneActive={redZoneActive}
          isDesktop
        />
      )}

      <div className="relative flex-1">
        {!isDesktop && <ControlPanel onToggle={() => setSidebarOpen(true)} />}
        <TimeControlPanel
          futureMode={futureMode}
          onFutureModeChange={setFutureMode}
          futureDate={futureDate}
          onFutureDateChange={handleFutureDateChange}
          loading={futureLoading}
        />

        <MapView
          stations={filteredStations}
          allStations={stations}
          selectedId={selectedId}
          onStationSelect={flyToStation}
          onRequestAnalytics={(station) => setAnalyticsId(station.id)}
          onMapReady={handleMapReady}
          showHighGrowthZones={false}
          futureMode={futureMode}
          futurePrediction={futureData}
          onSuggestedTpFocus={setActiveSuggestedTp}
        />
      </div>

      {!isDesktop && (
        <Sidebar
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          temperature={temperature}
          onTemperatureChange={setTemperature}
          construction={construction}
          onConstructionChange={setConstruction}
          searchMatches={searchMatches}
          criticalStations={criticalStations}
          onSelectStation={flyToStation}
          redZoneActive={redZoneActive}
          isDesktop={false}
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
      )}

      <AnalyticsModal
        open={Boolean(modalStation)}
        station={modalStation}
        onClose={() => setAnalyticsId(null)}
        temperature={temperature}
        construction={construction}
      />

    </div>
  );
}

export default App;
