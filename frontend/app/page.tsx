"use client";
import Script from "next/script";
import {DashboardView} from "./dashboard/DashboardView";
import {useWeatherDashboard,liffId} from "./dashboard/useWeatherDashboard";
export default function Home(){
 const model=useWeatherDashboard();
 return <>{liffId && <Script src="https://static.line-scdn.net/liff/edge/2/sdk.js" strategy="afterInteractive" onLoad={model.initializeLiff} />}<DashboardView model={model} /></>;
}
