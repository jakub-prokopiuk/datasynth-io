import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.API_URL || 'http://localhost:8001',
});

api.interceptors.request.use((config) => {
    const token = sessionStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    response => response,
    error => {
        if (error.response && error.response.status === 401) {
            window.dispatchEvent(new Event('auth-error'));
        }
        return Promise.reject(error);
    }
);

export default api;