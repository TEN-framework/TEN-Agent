/**
 * 事件发射器基类
 */
export class AGEventEmitter<T extends Record<string, any>> {
  private events: Map<keyof T, Array<(data: any) => void>> = new Map();

  /**
   * 注册事件监听器
   * @param event 事件名称
   * @param callback 回调函数
   */
  on<K extends keyof T>(event: K, callback: (data: T[K]) => void) {
    if (!this.events.has(event)) {
      this.events.set(event, []);
    }
    this.events.get(event)!.push(callback);
  }

  /**
   * 移除事件监听器
   * @param event 事件名称
   * @param callback 回调函数
   */
  off<K extends keyof T>(event: K, callback: (data: T[K]) => void) {
    if (!this.events.has(event)) {
      return;
    }
    const callbacks = this.events.get(event)!;
    const index = callbacks.indexOf(callback);
    if (index !== -1) {
      callbacks.splice(index, 1);
    }
  }

  /**
   * 触发事件
   * @param event 事件名称
   * @param data 事件数据
   */
  emit<K extends keyof T>(event: K, data?: T[K]) {
    if (!this.events.has(event)) {
      return;
    }
    const callbacks = this.events.get(event)!;
    callbacks.forEach(callback => callback(data));
  }
} 