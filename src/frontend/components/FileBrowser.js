/**
 * FileBrowser 組件
 *
 * 負責渲染和管理檔案總管的 UI 和功能。
 */
export class FileBrowser {
    /**
     * @param {HTMLElement} element - 要將此組件渲染到的容器元素。
     */
    constructor(element) {
        this.container = element;
    }

    /**
     * 渲染組件的初始 HTML 結構。
     */
    render() {
        // 這是從舊的 mp3.html 中提取並簡化的結構，作為我們重構的起點。
        this.container.innerHTML = `
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h2>📁 檔案總管 (Uploads)</h2>
                    <button id="reload-file-browser-btn">🔄 重新整理</button>
                </div>
                <div id="file-browser-list" style="margin-top: 16px; min-height: 100px; border: 1px solid #eee; padding: 10px;">
                    <p id="file-browser-loading-msg">正在載入檔案列表...</p>
                </div>
            </div>
        `;
    }

    /**
     * 為組件的元素加上事件監聽。
     */
    addEventListeners() {
        const reloadBtn = this.container.querySelector('#reload-file-browser-btn');
        if (reloadBtn) {
            reloadBtn.addEventListener('click', () => {
                console.log('重新整理按鈕被點擊！');
                this.loadFileBrowser();
            });
        }
    }

    /**
     * 從後端 API 載入檔案列表並更新 UI。
     */
    async loadFileBrowser() {
        console.log('開始載入檔案列表...');
        const listElement = this.container.querySelector('#file-browser-list');
        if (!listElement) return;

        listElement.innerHTML = '<p>正在載入檔案列表...</p>';

        try {
            const response = await fetch('/api/list_files');
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`API 請求失敗，狀態碼: ${response.status}. ${errorText}`);
            }
            const files = await response.json();

            if (files.length === 0) {
                listElement.innerHTML = '<p>Uploads 目錄是空的。</p>';
                return;
            }

            // Clear loading message
            listElement.innerHTML = '';

            // 增加一些基本的樣式
            const style = document.createElement('style');
            style.textContent = `
                .file-item { display: flex; justify-content: space-between; align-items: center; padding: 8px; border-bottom: 1px solid #f0f0f0; }
                .file-item:last-child { border-bottom: none; }
                .file-name { font-family: monospace; }
                .file-details { font-size: 0.8em; color: #666; }
            `;
            listElement.appendChild(style);

            // Create and append file items
            files.forEach(file => {
                const fileElement = document.createElement('div');
                fileElement.className = 'file-item';

                const icon = file.type === 'dir' ? '📁' : '📄';
                const fileName = document.createElement('span');
                fileName.className = 'file-name';
                fileName.textContent = `${icon} ${file.name}`;

                const fileDetails = document.createElement('span');
                fileDetails.className = 'file-details';
                // Only show details for files
                if (file.type !== 'dir') {
                    const sizeInKB = (file.size / 1024).toFixed(2);
                    const modifiedDate = new Date(file.modified_time * 1000).toLocaleString('zh-TW', { hour12: false });
                    fileDetails.textContent = `${sizeInKB} KB - ${modifiedDate}`;
                }

                fileElement.appendChild(fileName);
                fileElement.appendChild(fileDetails);

                listElement.appendChild(fileElement);
            });

        } catch (error) {
            console.error('載入檔案列表時發生錯誤:', error);
            listElement.innerHTML = `<p style="color: red;">無法載入檔案列表: ${error.message}</p>`;
        }
    }

    /**
     * 初始化組件。
     */
    init() {
        this.render();
        this.addEventListeners();
        this.loadFileBrowser();
    }
}
