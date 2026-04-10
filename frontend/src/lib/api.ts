import axios from 'axios';

// Base URLs for Microservices
const MS1_AUTH = 'http://localhost:8001';
const MS2_INGESTOR = 'http://localhost:8002';
const MS3_AI = 'http://localhost:8003';
const MS5_MAINTENANCE = 'http://localhost:8005';
const MS6_MACHINE = 'http://localhost:8006';

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

export { MS1_AUTH, MS2_INGESTOR, MS3_AI, MS5_MAINTENANCE, MS6_MACHINE };
