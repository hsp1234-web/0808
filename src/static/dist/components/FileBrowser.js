// src/frontend/components/FileBrowser.js
class FileBrowser {
  constructor(element) {
    this.container = element;
  }
  render() {
    this.container.innerHTML = `
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h2>\uD83D\uDCC1 檔案總管 (Uploads)</h2>
                    <button id="reload-file-browser-btn">\uD83D\uDD04 重新整理</button>
                </div>
                <div id="file-browser-list" style="margin-top: 16px; min-height: 100px; border: 1px solid #eee; padding: 10px;">
                    <p id="file-browser-loading-msg">正在載入檔案列表...</p>
                </div>
            </div>
        `;
  }
  addEventListeners() {
    const reloadBtn = this.container.querySelector("#reload-file-browser-btn");
    if (reloadBtn) {
      reloadBtn.addEventListener("click", () => {
        console.log("重新整理按鈕被點擊！");
        this.loadFileBrowser();
      });
    }
  }
  async loadFileBrowser() {
    console.log("開始載入檔案列表...");
    const listElement = this.container.querySelector("#file-browser-list");
    if (!listElement)
      return;
    listElement.innerHTML = "<p>正在載入檔案列表...</p>";
    setTimeout(() => {
      listElement.innerHTML = "<p>檔案列表將會顯示在這裡。</p>";
    }, 1000);
  }
  init() {
    this.render();
    this.addEventListeners();
    this.loadFileBrowser();
  }
}
export {
  FileBrowser
};
