import { useEffect, useMemo, useRef, useState } from 'react';
import MapView from './components/MapView.jsx';
import AnalyticsModal from './components/AnalyticsModal.jsx';
import TimeControlPanel from './components/TimeControlPanel.jsx';
import Chatbot from './components/Chatbot.jsx';
import { useGridStress } from './hooks/useGridStress.js';

const API_BASE_URL = (
  import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '');
const PREDICT_DEBOUNCE_MS = 350;

function App() {
  const [selectedId, setSelectedId] = useState(null);
  const [analyticsId, setAnalyticsId] = useState(null);
  const [futureMode, setFutureMode] = useState(false);
  const [futureDate, setFutureDate] = useState(null);
  const [futureData, setFutureData] = useState(null);
  const [futureLoading, setFutureLoading] = useState(false);
  const [activeSuggestedTp, setActiveSuggestedTp] = useState(null);
  const [backendStations, setBackendStations] = useState([]);
  const mapRef = useRef(null);
  const futureDateKey = useMemo(
    () => (futureDate ? futureDate.toISOString().slice(0, 10) : null),
    [futureDate]
  );

  // Fetch stations from backend on mount
  useEffect(() => {
    const controller = new AbortController();
    const fetchStations = async () => {
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
      }
    };
    fetchStations();
    return () => controller.abort();
  }, []);

  const {
    stations,
    filteredStations,
    temperature,
    construction,
  } = useGridStress(backendStations, '');

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
    const timeoutId = window.setTimeout(() => {
      runPrediction();
    }, PREDICT_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timeoutId);
      controller.abort();
    };
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

  const stationsWithFutureLoad = useMemo(() => {
    if (!futureMode || !futureData?.station_predictions?.length) {
      return filteredStations;
    }
    const futureById = new Map(
      futureData.station_predictions.map((item) => [item.id, item.predicted_load_pct])
    );
    return filteredStations.map((station) => ({
      ...station,
      futurePredictedPercent: futureById.has(station.id)
        ? futureById.get(station.id)
        : station.projectedPercent,
    }));
  }, [filteredStations, futureData, futureMode]);

  const flyToStation = (station) => {
    setSelectedId(station.id);
    if (mapRef.current) {
      mapRef.current.flyTo(station.coordinates, 13.2, { duration: 1.1 });
    }
  };

  const handleMapReady = (mapInstance) => {
    mapRef.current = mapInstance;
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100">
      <div className="relative flex-1">
        <TimeControlPanel
          futureMode={futureMode}
          onFutureModeChange={setFutureMode}
          futureDate={futureDate}
          onFutureDateChange={handleFutureDateChange}
          loading={futureLoading}
        />

        <MapView
          stations={stationsWithFutureLoad}
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
        futureDate={futureDateKey}
        futureSummary={futureData}
        activeSuggestedTp={activeSuggestedTp}
      />

    </div>
  );
}

export default App;
