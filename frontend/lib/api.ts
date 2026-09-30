export interface HealthResponse {
  status: string;
  version: string;
}

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}/health`);

  if (!response.ok) {
    throw new Error(`Backend health check failed (${response.status})`);
  }

  return response.json() as Promise<HealthResponse>;
}
