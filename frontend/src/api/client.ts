import axios from "axios";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export interface ReadyResponse {
  status: string;
  database: string;
  providers: Record<string, boolean>;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
}

export async function fetchReady(): Promise<ReadyResponse> {
  const { data } = await api.get<ReadyResponse>("/health/ready");
  return data;
}
