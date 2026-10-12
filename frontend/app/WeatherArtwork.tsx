import Image from "next/image";

function artworkFor(code: number | null) {
 if (code === 0) return "clear";
 if (code === 1 || code === 2) return "partly-cloudy";
 if (code === 45 || code === 48) return "fog";
 if (code != null && [95,96,99].includes(code)) return "storm";
 if (code != null && [71,73,75,77,85,86].includes(code)) return "snow";
 if (code != null && [51,53,55,56,57,61,63,65,66,67,80,81,82].includes(code)) return "rain";
 return "cloudy";
}

/** Decorative artwork: adjacent labels provide the actual weather description. */
export function WeatherArtwork({code,compact=false}:{code:number|null;compact?:boolean}) {
 return <Image
  className={"weather-artwork"+(compact?" compact":"")}
  src={`/weather/${artworkFor(code)}.png`}
  width={256} height={256}
  sizes={compact ? "48px" : "(max-width: 599px) 130px, 220px"}
  alt="" aria-hidden="true"
 />;
}
