/**
 * TaskList 組件
 *
 * 負責渲染「進行中」和「已完成」的任務列表。
 */
export class TaskList {
    /**
     * @param {HTMLElement} element - 要將此組件渲染到的容器元素。
     */
    constructor(element) {
        this.container = element;
    }

    /**
     * 渲染組件的 HTML 骨架。
     */
    render() {
        this.container.innerHTML = `
            <div class="grid-2-col">
                <div class="card">
                    <h2>🔄 進行中任務</h2>
                    <div id="ongoing-tasks" class="task-list">
                        <p id="no-ongoing-task-msg">暫無執行中任務</p>
                    </div>
                </div>
                <div class="card">
                    <h2>✅ 已完成任務</h2>
                    <div id="completed-tasks" class="task-list">
                        <p id="no-completed-task-msg">尚無完成的任務</p>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * 初始化組件。
     */
    init() {
        this.render();
        // 後續步驟會在此處加入更多邏輯，例如載入資料。
    }
}
