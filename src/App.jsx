import { useEffect, useMemo, useRef, useState } from 'react';
import MapView from './components/MapView.jsx';
import Sidebar from './components/Sidebar.jsx';
import ControlPanel from './components/ControlPanel.jsx';
import AnalyticsModal from './components/AnalyticsModal.jsx';
import Chatbot from './components/Chatbot.jsx';
import TimeControlPanel from './components/TimeControlPanel.jsx';
import transformerSubstations from './data/mockData.js';
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
  const mapRef = useRef(null);

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
  } = useGridStress(transformerSubstations, searchTerm);

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
    if (!futureMode || !futureDate) {
      setFutureData(null);
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
            target_date: futureDate.toISOString().slice(0, 10),
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
  }, [futureMode, futureDate]);

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
          onFutureDateChange={setFutureDate}
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

      <Chatbot
        temperature={temperature}
        construction={construction}
        selectedTransformerId={selectedId}
        futureMode={futureMode}
        futureDate={futureDate ? futureDate.toISOString().slice(0, 10) : null}
        futureSummary={futureData}
      />
    </div>
  );
}

export default App;
