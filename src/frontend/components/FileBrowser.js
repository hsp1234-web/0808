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
        // 在這裡，我們將來會加入 fetch('/api/list_files') 的邏輯。
        // 為了骨架建立，暫時顯示一個假資料。
        setTimeout(() => {
            listElement.innerHTML = '<p>檔案列表將會顯示在這裡。</p>';
        }, 1000);
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
