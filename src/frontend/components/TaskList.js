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

        // 步驟 2：加入靜態的假資料作為初始狀態
        this.state = {
            ongoing: [
                { id: 'task-1', filename: 'podcast_episode_1.mp3', status: '轉錄中 (35%)...' }
            ],
            completed: [
                { id: 'task-2', filename: 'meeting_notes.wav', status: '✅ 完成' },
                { id: 'task-3', filename: 'lecture_audio.m4a', status: '❌ 失敗' }
            ]
        };
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
     * 根據提供的資料和目標元素來渲染一個任務列表。
     * @param {Array} tasks - 要渲染的任務物件陣列。
     * @param {HTMLElement} targetElement - 要將列表渲染進去的 DOM 元素。
     * @param {string} noTasksMessage - 當沒有任務時顯示的訊息。
     */
    _renderTaskList(tasks, targetElement, noTasksMessage) {
        if (!targetElement) return;

        if (tasks.length === 0) {
            targetElement.innerHTML = `<p>${noTasksMessage}</p>`;
            return;
        }

        targetElement.innerHTML = ''; // 清空現有內容
        tasks.forEach(task => {
            const taskElement = document.createElement('div');
            taskElement.className = 'task-item'; // 我們可以重用舊的 CSS class
            taskElement.dataset.taskId = task.id;
            taskElement.innerHTML = `
                <span class="task-filename">${task.filename}</span>
                <span class="task-status">${task.status}</span>
            `;
            targetElement.appendChild(taskElement);
        });
    }

    /**
     * 初始化組件。
     */
    init() {
        this.render();

        // 取得渲染後的列表容器
        const ongoingTasksContainer = this.container.querySelector('#ongoing-tasks');
        const completedTasksContainer = this.container.querySelector('#completed-tasks');

        // 使用靜態資料來渲染列表
        this._renderTaskList(this.state.ongoing, ongoingTasksContainer, '暫無執行中任務');
        this._renderTaskList(this.state.completed, completedTasksContainer, '尚無完成的任務');
    }
}
