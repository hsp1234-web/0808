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
        this.container.innerHTML = `
            <div class="card">
                <div class="flex justify-between items-center flex-wrap gap-4">
                    <h2>📁 檔案總管 (Uploads)</h2>
                    <button id="reload-file-browser-btn" class="btn btn-primary bg-gray-500 hover:bg-gray-600">🔄 重新整理</button>
                </div>
                <div id="file-browser-list" class="task-list mt-4">
                    <p id="file-browser-loading-msg" class="text-gray-500 text-center">正在載入檔案列表...</p>
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
        const listElement = this.container.querySelector('#file-browser-list');
        if (!listElement) return;

        listElement.innerHTML = `<p class="text-gray-500 text-center">正在載入檔案列表...</p>`;

        try {
            const response = await fetch('/api/list_files');
            if (!response.ok) throw new Error(`API 請求失敗: ${response.statusText}`);
            const files = await response.json();

            listElement.innerHTML = ''; // 清空讀取中訊息

            if (files.length === 0) {
                listElement.innerHTML = '<p class="text-gray-500 text-center">Uploads 目錄是空的。</p>';
                return;
            }

            files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'task-item'; // 使用與 TaskList 相同的 class

                const icon = file.type === 'dir' ? '📁' : '📄';
                const formattedSize = file.type !== 'dir' ? `${(file.size / 1024).toFixed(2)} KB` : '';
                const modifiedDate = new Date(file.modified_time * 1000).toLocaleString('zh-TW');

                item.innerHTML = `
                    <div class="flex-grow overflow-hidden mr-2.5 min-w-0">
                        <strong class="task-filename" title="${file.name}">${icon} ${file.name}</strong>
                        <small class="block text-gray-500 text-xs mt-1">
                            ${formattedSize ? `${formattedSize} | ` : ''}${modifiedDate}
                        </small>
                    </div>
                    <div class="task-actions">
                        <a href="${file.path}" download="${file.name}" class="btn-download">下載</a>
                    </div>
                `;
                listElement.appendChild(item);
            });

        } catch (error) {
            console.error('載入檔案列表時發生錯誤:', error);
            listElement.innerHTML = `<p class="text-red-500 text-center">無法載入檔案列表: ${error.message}</p>`;
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
