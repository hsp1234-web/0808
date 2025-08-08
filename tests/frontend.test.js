import { test, beforeEach, describe } from 'node:test';
import assert from 'node:assert';
import { JSDOM } from 'jsdom';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// --- Test Setup ---
const __dirname = path.dirname(fileURLToPath(import.meta.url));
let dom;
let window;
let document;

beforeEach(() => {
  const htmlPath = path.join(__dirname, '../app/static/mp3.html');
  const htmlContent = fs.readFileSync(htmlPath, 'utf-8');
  dom = new JSDOM(htmlContent, {
    runScripts: 'dangerously',
    resources: 'usable',
    url: "file://" + htmlPath,
  });
  window = dom.window;
  document = window.document;
});

// --- Test Suite ---
describe('Frontend Logic', () => {
    test('Tab switching functionality', () => {
      const consoleTab = document.getElementById('console-tab');
      const settingsTab = document.getElementById('settings-tab');
      const consolePanel = document.getElementById('console-panel');
      const settingsPanel = document.getElementById('settings-panel');

      assert.strictEqual(consolePanel.classList.contains('hidden'), false, 'Initial state: Console panel should be visible');
      assert.strictEqual(settingsPanel.classList.contains('hidden'), true, 'Initial state: Settings panel should be hidden');
      assert.strictEqual(consoleTab.getAttribute('aria-selected'), 'true', 'Initial state: Console tab should be selected');

      settingsTab.click();

      assert.strictEqual(consolePanel.classList.contains('hidden'), true, 'After click: Console panel should be hidden');
      assert.strictEqual(settingsPanel.classList.contains('hidden'), false, 'After click: Settings panel should be visible');
      assert.strictEqual(settingsTab.getAttribute('aria-selected'), 'true', 'After click: Settings tab should be selected');
      assert.strictEqual(consoleTab.getAttribute('aria-selected'), 'false', 'After click: Console tab should be unselected');

      consoleTab.click();

      assert.strictEqual(consolePanel.classList.contains('hidden'), false, 'Click back: Console panel should be visible again');
      assert.strictEqual(settingsPanel.classList.contains('hidden'), true, 'Click back: Settings panel should be hidden again');
      assert.strictEqual(consoleTab.getAttribute('aria-selected'), 'true', 'Click back: Console tab should be selected again');
    });

    test('Start button gets correct data from settings', async () => {
        const modelSelect = document.getElementById('model-select');
        const languageSelect = document.getElementById('language-select');
        const startBtn = document.getElementById('start-transcription-btn');

        modelSelect.value = 'large';
        languageSelect.value = 'en';

        let formDataCaptured;
        window.fetch = async (url, options) => {
            formDataCaptured = options.body;
            return new window.Response(JSON.stringify({ task_id: 'mock_task_id' }), {
                status: 202,
                headers: { 'Content-Type': 'application/json' }
            });
        };

        const mockFile = new window.File(['(⌐□_□)'], 'test.mp3', { type: 'audio/mpeg' });
        const fileInput = document.getElementById('audio-file-input');
        Object.defineProperty(fileInput, 'files', { value: [mockFile] });
        fileInput.dispatchEvent(new window.Event('change', { bubbles: true }));

        // The click handler is async, so we should await it if possible,
        // or just wait for the next tick.
        await startBtn.click();

        assert.strictEqual(formDataCaptured.get('model_size'), 'large', 'Model size should be "large"');
        assert.strictEqual(formDataCaptured.get('language'), 'en', 'Language should be "en"');
        assert.deepStrictEqual(formDataCaptured.get('file'), mockFile, 'File object should be the mock file');
    });
});
