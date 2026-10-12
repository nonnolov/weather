"use client";
import {useState} from "react";
import type {ForecastRun} from "../../lib/api";
import {value,timeLabel,next24Hours,translations,type Language} from "./format";
const chartPath = (values: Array<number | null>, min: number, max: number, width: number, height: number, top = 18, bottom = 28) => {
  const usableHeight = height - top - bottom;
  return values.map((value, index) => {
    const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
    const y = value === null ? null : top + (1 - (value - min) / Math.max(max - min, 1)) * usableHeight;
    return y === null ? null : `${index === 0 || values[index - 1] === null ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
  }).filter(Boolean).join(" ");
};

const chartPoint = (value: number, index: number, count: number, min: number, max: number, width: number, height: number, top = 18, bottom = 28) => ({
  cx: count === 1 ? width / 2 : (index / (count - 1)) * width,
  cy: top + (1 - (value - min) / Math.max(max - min, 1)) * (height - top - bottom),
});

/* Plot geometry. The viewBox stays close to the rendered aspect so the stretched
 * SVG keeps curve slopes honest, and every axis label lives in HTML instead of
 * inside the SVG, where preserveAspectRatio="none" would warp the text. */
const CHART_WIDTH = 640;
const CHART_HEIGHT = 300;
const CHART_PAD = 40;
const PLOT_TOP = CHART_PAD;
const PLOT_BOTTOM = CHART_HEIGHT - CHART_PAD;
const RAIN_BAR_MAX = 120;
const gridLines = (width: number) => [0, .5, 1].map((position) => (
  <line key={position} className="chart-grid" x1="0" x2={width} y1={PLOT_TOP + position * (PLOT_BOTTOM - PLOT_TOP)} y2={PLOT_TOP + position * (PLOT_BOTTOM - PLOT_TOP)} />
));

function ChartScale({ labels }: { labels: string[] }) {
  return <div className="chart-scale" aria-hidden="true">
    {labels.map((label, index) => <span key={label} style={{ top: `${(PLOT_TOP + ((PLOT_BOTTOM - PLOT_TOP) * index) / Math.max(labels.length - 1, 1)) / CHART_HEIGHT * 100}%` }}>{label}</span>)}
  </div>;
}

function ChartTimes({ hours, timeZone }: { hours: ForecastRun["hourly"]; timeZone: string }) {
  const ticks = [0, 6, 12, 18, 23].filter((index) => hours[index]);
  const last = ticks[ticks.length - 1];
  return <div className="chart-times" aria-hidden="true">
    {ticks.map((index) => <span key={index} style={{ left: `${(hours.length === 1 ? .5 : index / (hours.length - 1)) * 100}%`, transform: index === 0 ? undefined : index === last ? "translateX(-100%)" : "translateX(-50%)" }}>{timeLabel(hours[index].valid_time, timeZone).slice(0, 2)}</span>)}
  </div>;
}

function ChartInspector({ hours, timeZone, language, index, setIndex }: { hours: ForecastRun["hourly"]; timeZone: string; language: Language; index: number; setIndex: (index: number) => void }) {
  const hour = hours[Math.min(index, hours.length - 1)];
  if (!hour) return null;
  return <div className="chart-inspector">
    <output className="chart-tooltip" htmlFor={"hour-" + language + "-" + hours[0].id}><time dateTime={hour.valid_time}>{timeLabel(hour.valid_time, timeZone)}</time><span>{value(hour.temperature_2m, "°C")}</span><span>{language === "th" ? "โอกาสฝน " : "Rain chance "}{value(hour.precipitation_probability, "%")}</span><span>{value(hour.precipitation, language === "th" ? " มม." : " mm")}</span></output>
    <input id={"hour-" + language + "-" + hours[0].id} type="range" min={0} max={hours.length - 1} value={index} onChange={event => setIndex(Number(event.target.value))} aria-label={language === "th" ? "เลือกชั่วโมงเพื่อดูค่าบนกราฟ" : "Choose forecast hour"} aria-valuetext={timeLabel(hour.valid_time, timeZone)} />
  </div>;
}

export function TemperatureTrend({ hourly, timeZone, language }: { hourly: ForecastRun["hourly"]; timeZone: string; language: Language }) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const hours = next24Hours(hourly);
  const temperatures = hours.map((hour) => hour.temperature_2m);
  const available = temperatures.filter((temperature): temperature is number => temperature !== null);
  if (!available.length) return null;
  const min = Math.floor(Math.min(...available) - 1);
  const max = Math.ceil(Math.max(...available) + 1);
  const peakValue = Math.max(...available);
  const peakIndex = temperatures.findIndex((temperature) => temperature === peakValue);
  const firstValue = temperatures.find((temperature): temperature is number => temperature !== null);
  const firstIndex = temperatures.findIndex((temperature) => temperature !== null);
  const width = CHART_WIDTH;
  const height = CHART_HEIGHT;
  const summary = language === "th"
    ? `แนวโน้มอุณหภูมิ 24 ชั่วโมง ต่ำสุด ${value(Math.min(...available), "°C")} สูงสุด ${value(peakValue, "°C")}`
    : `24-hour temperature trend. Low ${value(Math.min(...available), "°C")}; high ${value(peakValue, "°C")}.`;

  return <section className="chart-card temperature-chart" aria-labelledby="temperature-trend-heading">
    <div className="chart-heading">
      <div><h2 id="temperature-trend-heading">{language === "th" ? "แนวโน้มอุณหภูมิ" : "Temperature trend"}</h2><p>{language === "th" ? "24 ชั่วโมงข้างหน้า" : "Next 24 hours"}</p></div>
      <dl className="chart-stats"><div><dt>{language === "th" ? "ต่ำสุดวันนี้" : "Low today"}</dt><dd>{value(Math.min(...available), "°C")}</dd></div><div><dt>{language === "th" ? "สูงสุดวันนี้" : "High today"}</dt><dd>{value(peakValue, "°C")}</dd></div><div><dt>{language === "th" ? "ช่วงร้อนสุด" : "Warmest"}</dt><dd>{peakIndex >= 0 ? timeLabel(hours[peakIndex].valid_time, timeZone) : "—"}</dd></div></dl>
    </div>
    <ChartInspector hours={hours} timeZone={timeZone} language={language} index={selectedIndex} setIndex={setSelectedIndex} />
    <div className="chart-body">
      <div className="chart-plot" onPointerMove={event => { const bounds = event.currentTarget.getBoundingClientRect(); const fraction = Math.max(0, Math.min(1, (event.clientX - bounds.left) / Math.max(1, bounds.width - 38))); setSelectedIndex(Math.round(fraction * (hours.length - 1))); }}>
        <svg className="trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="temperature-trend-heading temperature-trend-summary" preserveAspectRatio="none">
          <desc id="temperature-trend-summary">{summary}</desc>
          {gridLines(width)}
          <line className="chart-guide" x1={Math.min(selectedIndex, hours.length - 1) / Math.max(hours.length - 1, 1) * width} x2={Math.min(selectedIndex, hours.length - 1) / Math.max(hours.length - 1, 1) * width} y1={PLOT_TOP} y2={PLOT_BOTTOM} />
          <path className="temperature-area" d={`${chartPath(temperatures, min, max, width, height, CHART_PAD, CHART_PAD)} L ${width} ${PLOT_BOTTOM} L 0 ${PLOT_BOTTOM} Z`} />
          <path className="temperature-line" d={chartPath(temperatures, min, max, width, height, CHART_PAD, CHART_PAD)} />
          {firstValue !== undefined && <circle className="current-point" {...chartPoint(firstValue, firstIndex, hours.length, min, max, width, height, CHART_PAD, CHART_PAD)} r="5" />}
          {peakIndex >= 0 && <circle className="peak-point" {...chartPoint(peakValue, peakIndex, hours.length, min, max, width, height, CHART_PAD, CHART_PAD)} r="4" />}
        </svg>
        <ChartScale labels={[value(max, "°"), value((max + min) / 2, "°"), value(min, "°")]} />
      </div>
      <ChartTimes hours={hours} timeZone={timeZone} />
    </div>
    <p className="chart-summary">{summary}</p>
  </section>;
}

export function RainTrend({ hourly, timeZone, language }: { hourly: ForecastRun["hourly"]; timeZone: string; language: Language }) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const hours = next24Hours(hourly);
  const probabilities = hours.map((hour) => hour.precipitation_probability);
  const rainfall = hours.map((hour) => hour.precipitation);
  const availableProbabilities = probabilities.filter((probability): probability is number => probability !== null);
  const availableRainfall = rainfall.filter((amount): amount is number => amount !== null);
  if (!availableProbabilities.length && !availableRainfall.length) return null;
  const peakProbability = availableProbabilities.length ? Math.max(...availableProbabilities) : 0;
  const peakIndex = probabilities.findIndex((probability) => probability === peakProbability);
  const maxRainfall = Math.max(...availableRainfall, 0.1);
  const width = CHART_WIDTH;
  const height = CHART_HEIGHT;
  const riskHour = peakIndex >= 0 ? timeLabel(hours[peakIndex].valid_time, timeZone) : "—";
  const scaleHint = language === "th"
    ? `เส้น = โอกาสฝน 0–100% · แท่ง = ปริมาณฝน สูงสุด ${value(maxRainfall, " มม.")}`
    : `Line = chance 0–100% · bars = rainfall, max ${value(maxRainfall, " mm")}`;
  const summary = language === "th"
    ? `แนวโน้มฝน 24 ชั่วโมง โอกาสสูงสุด ${value(peakProbability, "%")} เวลา ${riskHour}`
    : `24-hour rain trend. Peak chance ${value(peakProbability, "%")} at ${riskHour}.`;

  return <section className="chart-card rain-chart" aria-labelledby="rain-trend-heading">
    <div className="chart-heading"><div><h2 id="rain-trend-heading">{language === "th" ? "แนวโน้มฝน" : "Rain trend"}</h2><p>{scaleHint}</p></div><div className={"risk-callout" + (peakProbability >= 50 ? " high-risk" : "")}><span>{peakProbability >= 50 ? translations[language].highRisk : language === "th" ? "ช่วงเสี่ยงสูงสุด" : "Peak risk"}</span><strong>{value(peakProbability, "%")}</strong><small>{riskHour}</small></div></div>
    <ChartInspector hours={hours} timeZone={timeZone} language={language} index={selectedIndex} setIndex={setSelectedIndex} />
    <div className="chart-body">
      <div className="chart-plot" onPointerMove={event => { const bounds = event.currentTarget.getBoundingClientRect(); const fraction = Math.max(0, Math.min(1, (event.clientX - bounds.left) / Math.max(1, bounds.width - 38))); setSelectedIndex(Math.round(fraction * (hours.length - 1))); }}>
        <svg className="trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="rain-trend-heading rain-trend-summary" preserveAspectRatio="none">
          <desc id="rain-trend-summary">{summary}</desc>
          {gridLines(width)}
          <line className="chart-guide" x1={Math.min(selectedIndex, hours.length - 1) / Math.max(hours.length - 1, 1) * width} x2={Math.min(selectedIndex, hours.length - 1) / Math.max(hours.length - 1, 1) * width} y1={PLOT_TOP} y2={PLOT_BOTTOM} />
          {rainfall.map((amount, index) => { const barWidth = Math.max(4, width / Math.max(hours.length, 1) - 5); const x = (index / Math.max(hours.length - 1, 1)) * width - barWidth / 2; const barHeight = amount === null ? 0 : (amount / maxRainfall) * RAIN_BAR_MAX; return <rect className="rain-bar" key={index} x={x} y={PLOT_BOTTOM - barHeight} width={barWidth} height={barHeight} rx="2" />; })}
          <path className="rain-line" d={chartPath(probabilities, 0, 100, width, height, CHART_PAD, CHART_PAD)} />
          {peakIndex >= 0 && probabilities[peakIndex] !== null && <circle className="rain-peak-point" {...chartPoint(probabilities[peakIndex], peakIndex, hours.length, 0, 100, width, height, CHART_PAD, CHART_PAD)} r="5" />}
        </svg>
        <ChartScale labels={["100%", "50%", "0%"]} />
      </div>
      <ChartTimes hours={hours} timeZone={timeZone} />
    </div>
    <p className="chart-summary">{summary}</p>
  </section>;
}
