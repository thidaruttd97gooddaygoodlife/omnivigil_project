import axios from 'axios';

// Central API Gateway URL
const API_GATEWAY = typeof window !== 'undefined'
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : 'http://localhost:8000';

// Base URLs for Microservices (routed through Kong API Gateway)
const MS1_AUTH = `${API_GATEWAY}/auth-service`;
const MS2_INGESTOR = `${API_GATEWAY}/ingestor-service`;
const MS3_AI = `${API_GATEWAY}/ai-service`;
const MS4_ALERT = `${API_GATEWAY}/alert-service`;
const MS5_MAINTENANCE = `${API_GATEWAY}/maintenance-service`;
const MS6_MACHINE = `${API_GATEWAY}/machine-service`;

// Add interceptor to attach token
const attachToken = (config: any) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('omnivigil_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
};

// Auth API Client
export const authApi = axios.create({
  baseURL: MS1_AUTH,
  headers: {
    'Content-Type': 'application/json',
  },
});
authApi.interceptors.request.use(attachToken);

// Ingestor API Client
export const ingestorApi = axios.create({
  baseURL: MS2_INGESTOR,
});
ingestorApi.interceptors.request.use(attachToken);

// AI Engine API Client
export const aiApi = axios.create({
  baseURL: MS3_AI,
});
aiApi.interceptors.request.use(attachToken);

// Alert API Client
export const alertApi = axios.create({
  baseURL: MS4_ALERT,
});
alertApi.interceptors.request.use(attachToken);

// Maintenance API Client
export const maintenanceApi = axios.create({
  baseURL: MS5_MAINTENANCE,
});
maintenanceApi.interceptors.request.use(attachToken);

// Machine API Client
export const machineApi = axios.create({
  baseURL: MS6_MACHINE,
});
machineApi.interceptors.request.use(attachToken);

export { MS1_AUTH, MS2_INGESTOR, MS3_AI, MS4_ALERT, MS5_MAINTENANCE, MS6_MACHINE };
