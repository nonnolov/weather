import {apiUrl,ApiError,type UserLocationResponse,type IngestResponse,type ForecastRun} from "./api";
export const LINE_CONSENT_VERSION="weather-alerts-v1";
export type LineStatus={external_user_id:string;friend:boolean;location_verified:boolean;location_id:number|null;enabled:boolean;ready:boolean;consent_version:string;next_step:"friend"|"location"|"consent"|"ready"};
export type LineConfig={enabled:boolean;add_friend_url:string|null};
export class LineRequestError extends ApiError {
 constructor(status:number,public readonly reason:"friendship"|"disabled"|"other") {super("LINE signup request failed",status);}
}
async function lineFailure(response:Response):Promise<LineRequestError>{
 let detail="";try{const body=await response.json();if(typeof body?.detail==="string")detail=body.detail;}catch{}
 const reason=detail==="Weather friendship verification is not configured."||detail==="LINE friendship could not be verified."?"friendship":detail==="LINE notification signup is not available yet."?"disabled":"other";
 return new LineRequestError(response.status,reason);
}
async function lineRequest<T>(path:string,init?:RequestInit):Promise<T>{
 const token=window.liff?.getAccessToken?.();
 if(!token)throw new ApiError("LINE session unavailable",401);
 const response=await fetch(apiUrl("/api/v1/line"+path),{...init,cache:"no-store",headers:{"Content-Type":"application/json",Authorization:"Bearer "+token,...init?.headers}});
 if(!response.ok)throw await lineFailure(response);
 return response.json() as Promise<T>;
}
export async function getLineConfig():Promise<LineConfig>{
 const response=await fetch(apiUrl("/api/v1/line/onboarding/config"),{cache:"no-store"});
 if(!response.ok)throw new ApiError("LINE signup unavailable",response.status);
 return response.json();
}
export const getLineStatus=()=>lineRequest<LineStatus>("/onboarding");
export const setLineSubscription=(enabled:boolean)=>lineRequest<LineStatus>("/subscription",{method:"PUT",body:JSON.stringify({enabled,consent_version:enabled?LINE_CONSENT_VERSION:undefined})});
export const setLineLocation=(latitude:number,longitude:number)=>lineRequest<UserLocationResponse>("/location/from-gps",{method:"POST",body:JSON.stringify({latitude,longitude})});
export const getLineForecast=()=>lineRequest<ForecastRun>("/forecast");
export const refreshLineForecast=()=>lineRequest<IngestResponse>("/forecast/refresh",{method:"POST"});
export function lineSessionHeaders():HeadersInit{
 const token=typeof window!=="undefined"?window.liff?.getAccessToken?.():null;
 return token?{Authorization:"Bearer "+token}:{};
}
