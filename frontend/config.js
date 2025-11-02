// Auto-detect environment (development vs production)
const IS_PRODUCTION = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';

// Backend API URL
// GANTI URL_RAILWAY_KAMU setelah deploy ke Railway!
const RAILWAY_URL = 'https://wms-dismantle-production.up.railway.app';  // <-- GANTI INI!
const API_URL = IS_PRODUCTION ? RAILWAY_URL : 'http://localhost:8001';

// WebSocket URL
const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const API_HOST = new URL(API_URL).host;
const WS_URL = `${WS_PROTOCOL}//${API_HOST}`;

console.log('🌍 Environment:', IS_PRODUCTION ? 'PRODUCTION' : 'DEVELOPMENT');
console.log('🔗 API URL:', API_URL);
console.log('💬 WebSocket URL:', WS_URL);

// Export untuk dipakai di file HTML
window.APP_CONFIG = {
    API_URL,
    WS_URL,
    IS_PRODUCTION
};
