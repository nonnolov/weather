/* Outline weather symbols match the supplied Stitch icon language. */
export function WeatherArtwork({code,compact=false}:{code:number|null;compact?:boolean}) {
 const rain=code!=null&&[51,53,55,56,57,61,63,65,66,67,80,81,82,95,96,99].includes(code);
 const storm=code!=null&&[95,96,99].includes(code);
 const snow=code!=null&&[71,73,75,77,85,86].includes(code);
 const fog=code===45||code===48;
 const clear=code===0,partly=code===1||code===2;
 return <svg className={"weather-artwork"+(compact?" compact":"")} viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
 {(clear||partly)&&<g className="weather-sun"><circle cx={clear?24:18} cy={clear?24:17} r={clear?8:6}/>{clear?<path d="M24 6v4m0 28v4M6 24h4m28 0h4M11 11l3 3m20 20 3 3M11 37l3-3m20-20 3-3"/>:<path d="M18 4v3M5 17h3m1-9 2 2m16-2-2 2M18 27v3"/>}</g>}
 {!clear&&<path className="weather-cloud" d="M12 31h24a7 7 0 0 0 0-14h-1a10 10 0 0 0-19-1 8 8 0 0 0-4 15Z"/>}
 {rain&&!storm&&<path className="weather-rain" d="m16 36-2 5m12-5-2 5m12-5-2 5"/>}
 {storm&&<path className="weather-rain" d="m25 32-6 8h6l-3 6"/>}
 {snow&&<g className="weather-rain"><path d="M17 35v9m-4-7 8 5m0-5-8 5M32 35v9m-4-7 8 5m0-5-8 5"/></g>}
 {fog&&<path d="M8 37h32M12 42h24"/>}
 </svg>;
}
