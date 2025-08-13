// src/frontend/ApiService.js

/**
 * 處理與後端 API 所有通訊的模組。
 */
class ApiService {
    constructor() {
        this.baseUrl = '/api';
    }

    async _request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const response = await fetch(url, options);
        if (!response.ok) {
            const error = await response.json();
            // 直接拋出從後端收到的錯誤物件，使其包含 detail 屬性
            throw error;
        }
        // 如果請求成功，但沒有內容，也回傳一個成功的狀態
        if (response.status === 204 || response.headers.get('content-length') === '0') {
            return { success: true };
        }
        return response.json();
    }

    youtube = {
        validateApiKey: (apiKey) => {
            return this._request('/youtube/validate_api_key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: apiKey }),
            });
        },
        getModels: () => {
            return this._request('/youtube/models');
        },
        process: (payload) => {
            return this._request('/youtube/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
        }
    };

    // 未來可以新增其他 API 的命名空間
    // e.g., local, downloader, etc.
}

export const apiService = new ApiService();
