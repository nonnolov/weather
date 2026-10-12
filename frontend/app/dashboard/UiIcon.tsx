import type {ReactNode} from "react";
const paths:Record<string,ReactNode>={
 location:<><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></>,
 map:<><path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2V5Z"/><path d="M9 3v16M15 5v16"/></>,
 gps:<><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/></>,
 rain:<><path d="M3 12a9 9 0 0 1 18 0H3Zm9 0v7a2 2 0 0 0 4 0"/></>,
 drop:<path d="M12 3c-2 4-7 8-7 12a7 7 0 0 0 14 0c0-4-5-8-7-12Z"/>,
 wind:<><path d="M3 8h12a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h6a3 3 0 1 1-3 3"/></>,
 clock:<><circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/></>,
 calendar:<><rect x="4" y="5" width="16" height="16" rx="2"/><path d="M8 3v4m8-4v4M4 10h16"/></>,
 air:<><path d="M3 8c3-5 6 5 9 0s6 5 9 0M3 13c3-5 6 5 9 0s6 5 9 0M3 18c3-5 6 5 9 0s6 5 9 0"/></>,
 message:<><path d="M4 4h16v13H9l-5 4V4Z"/><path d="M8 8h8m-8 4h6"/></>,
 moon:<path d="M21 13a9 9 0 1 1-10-10 7 7 0 0 0 10 10Z"/>,
 sun:<><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></>,
};
export function UiIcon({name,className=""}:{name:string;className?:string}) {return <svg className={"ui-icon "+className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]??paths.location}</svg>;}
