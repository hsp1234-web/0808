import { describe, test, expect, beforeEach } from 'bun:test';
import { JSDOM } from 'jsdom';
import { YouTubeReporter } from '../../frontend/components/YouTubeReporter.js';
import { apiService } from '../../frontend/ApiService.js';

describe('YouTubeReporter Component Unit Tests', () => {
  let dom;
  let container;

  beforeEach(() => {
    // 設定一個模擬的 DOM 環境，並提供一個 URL 以啟用 localStorage
    dom = new JSDOM('<!DOCTYPE html><html><body><div id="test-container"></div></body></html>', {
      url: 'http://localhost',
    });
    global.document = dom.window.document;
    global.window = dom.window;
    global.localStorage = dom.window.localStorage;
    global.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({}) });

    container = document.getElementById('test-container');
  });

  test('should render the component with its title', () => {
    // 模擬傳入的依賴
    const mockDeps = {
      api: apiService,
      socket: { send: () => {} },
      showStatusMessage: () => {},
      logAction: () => {},
      app: {},
    };

    // 建立並初始化元件
    const reporter = new YouTubeReporter(container, mockDeps);
    reporter.init();

    // 驗證標題是否存在
    const titleElement = container.querySelector('h2');
    expect(titleElement).not.toBeNull();
    expect(titleElement.textContent).toContain('Google API 金鑰管理');

    // 驗證 API Key 輸入框是否存在
    const apiKeyInput = container.querySelector('#api-key-input');
    expect(apiKeyInput).not.toBeNull();
  });
});
