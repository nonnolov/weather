type Props = { code?: number | null; compact?: boolean };

// Decorative artwork; the adjacent forecast text provides the weather description.
export function WeatherArtwork({ code, compact = false }: Props) {
  const rain = code != null && [51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99].includes(code);
  const storm = code != null && [95,96,99].includes(code);
  const snow = code != null && [71,73,75,77,85,86].includes(code);
  const fog = code != null && [45,48].includes(code);
  const clear = code === 0;
  return <svg className={"weather-artwork" + (compact ? " compact" : "")} viewBox="0 0 560 360" fill="none" aria-hidden="true" focusable="false">
    <ellipse cx="290" cy="310" rx="220" ry="23" fill="currentColor" opacity=".05" />
    {!rain && !snow && !fog && <g>
      <circle cx="345" cy="125" r="92" fill="#e7bb70" opacity=".12" />
      <circle cx="345" cy="125" r="67" fill="#e7bb70" opacity=".17" />
      <circle cx="345" cy="125" r="47" fill="#e7bb70" />
      <circle cx="331" cy="109" r="29" fill="#f2dca5" opacity=".6" />
    </g>}
    {!clear && <g>
      <path d="M148 236h251c37 0 61-21 61-52 0-32-26-57-58-56-10-52-69-73-110-44-42-36-103-7-104 45-49-12-85 20-85 54 0 30 19 53 45 53Z" fill={rain || snow ? "#a9bfcb" : "#edf0ed"} />
      <path d="M148 236h251c32 0 54-15 60-39-69 22-121 10-158-4-52-19-107 30-187 6 7 23 20 37 34 37Z" fill={rain || snow ? "#7f9eae" : "#d5e0e2"} opacity=".65" />
      <path d="M151 155c20-14 48-10 64 2 7-54 61-73 99-42" stroke="#fff" strokeWidth="8" strokeLinecap="round" opacity=".4" />
    </g>}
    {rain && <g stroke="#80b3cd" strokeWidth="6" strokeLinecap="round">
      <path d="m184 259-9 18m64-18-9 18m119-18-9 18m64-18-9 18m-153 18-9 18m64-18-9 18" />
    </g>}
    {snow && <g fill="#e6f0f5">{[185,245,305,365,415].map((x) => <circle key={x} cx={x} cy={265 + (x % 3) * 14} r="5" />)}</g>}
    {storm && <path d="m302 228-27 42h22l-11 38 39-51h-23l18-29Z" fill="#edc272" />}
    {fog && <g stroke="#b4c5c8" strokeWidth="7" strokeLinecap="round"><path d="M140 256h270M175 276h270M120 297h260" /></g>}
    <path d="M42 310c72-40 122-24 182-13 95 18 171-51 294-5" stroke="currentColor" strokeWidth="2" opacity=".12" />
    <path d="M87 322c99-25 185 17 285-9" stroke="currentColor" strokeWidth="2" opacity=".09" />
    <g fill="currentColor" opacity=".18"><circle cx="96" cy="122" r="3" /><circle cx="454" cy="88" r="2" /><circle cx="477" cy="255" r="3" /></g>
  </svg>;
}
