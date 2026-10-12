"use client";
import {WeatherArtwork} from "../WeatherArtwork";
import {MapPreview} from "../MapPreview";
import {AirQualityCard} from "../AirQualityCard";
import {TemperatureTrend,RainTrend} from "./ForecastCharts";
import {UiIcon} from "./UiIcon";
import type {DashboardModel} from "./useWeatherDashboard";

import {LineOnboarding} from "./LineOnboarding";
import {DashboardHeader} from "./DashboardHeader";
import {CurrentConditions} from "./CurrentConditions";
import {HourlyForecast} from "./HourlyForecast";
import {DailyForecast} from "./DailyForecast";

export function DashboardView({model}:{model:DashboardModel}) {
 const {mapOpen,setMapOpen,chartTab,setChartTab,selectedId,forecast,location,gpsState,message,seedLoading,lineUserId,language,t,ux,isGpsBusy,busy,progress,sampleLocations,handleGps,selectSeedLocation}=model;
 return <>
    <main className={"dashboard-shell" + (forecast && location ? " has-forecast" : "")} aria-busy={busy}>
    <DashboardHeader model={model} />

    {!forecast && <section className="card welcome-card" aria-labelledby="location-heading">
      <div className="welcome-illustration"><WeatherArtwork code={2} /></div>
      <p className="eyebrow">{t.yourLocation}</p>
      <h2 id="location-heading">{ux.start}</h2>
      <p className="welcome-description">{ux.description}</p>
      <button className="gps-primary" type="button" onClick={handleGps} disabled={busy}>
        {isGpsBusy ? <span className="spinner" aria-hidden="true" /> : <UiIcon name="gps" />}
        {isGpsBusy ? progress : t.useLocation}
      </button>
      <p className="permission-note">{ux.privacy}</p>
    </section>}

    {busy ? <section className="status-panel" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div><strong>{seedLoading ? ux.loadingSample : progress}</strong>
      {isGpsBusy && <ol className="progress-steps" aria-label={progress}>
        {[ux.locating, ux.saving, ux.forecasting].map((step, index) => <li key={step} className={index <= ["locating", "saving", "forecasting"].indexOf(gpsState) ? "active" : ""}>{step}</li>)}
      </ol>}</div>
    </section> : message && <div className={"status-panel" + (gpsState === "error" ? " status-error" : "")} role={gpsState === "error" ? "alert" : "status"}>
      <p>{message === t.lineUnavailable ? ux.lineHint : message}</p>
      {gpsState === "error" && <button type="button" className="retry-button" onClick={() => selectedId !== null ? selectSeedLocation(selectedId) : handleGps()}>{ux.retry}</button>}
    </div>}

    {!forecast && <LineOnboarding model={model} />}

    {sampleLocations.length > 0 && <details className="sample-picker">
      <summary>{ux.sample}</summary>
      <label className="select-label">{ux.choose}
        <select value={selectedId ?? ""} disabled={busy} onChange={(event) => selectSeedLocation(Number(event.target.value))}>
          <option value="" disabled>{ux.choose}</option>
          {sampleLocations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
    </details>}

    {forecast && location && <div className="forecast-layout"><CurrentConditions model={model} />
    <AirQualityCard key={location.id} locationId={location.id} timeZone={location.timezone} language={language} />
<LineOnboarding model={model} />
    <div className="chart-switcher"><div className="chart-tabs" role="group" aria-label={language === "th" ? "เลือกกราฟ" : "Choose chart"}><button type="button" aria-pressed={chartTab === "temperature"} onClick={() => setChartTab("temperature")}>{t.tempTrend}</button><button type="button" aria-pressed={chartTab === "rain"} onClick={() => setChartTab("rain")}>{t.rainTrend}</button></div>{chartTab === "temperature" ? <TemperatureTrend hourly={forecast.hourly} timeZone={location.timezone} language={language} /> : <RainTrend hourly={forecast.hourly} timeZone={location.timezone} language={language} />}</div>
    <HourlyForecast model={model} />
    <DailyForecast model={model} /></div>}
    <footer className="dashboard-footer"><span>{ux.source}</span><span>{lineUserId ? t.connectedLine : ux.lineHint}</span></footer>
    </main>
    {mapOpen && location && <MapPreview location={location} isSample={selectedId!==null} language={language} onClose={() => setMapOpen(false)} />}
 </>;
}
