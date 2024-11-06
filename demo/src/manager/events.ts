import { EventHandler } from "./types"

export class AGEventEmitter<T> {
  private readonly _eventMap: Map<keyof T, EventHandler<any[]>[]> = new Map()

  once<Key extends keyof T>(evt: Key, cb: T[Key]) {
    const wrapper = (...args: any[]) => {
      this.off(evt, wrapper as any)
      ;(cb as any)(...args)
    }
    this.on(evt, wrapper as any)
    return this
  }

  on<Key extends keyof T>(evt: Key, cb: T[Key]) {
    const cbs = this._eventMap.get(evt) ?? []
    cbs.push(cb as any)
    this._eventMap.set(evt, cbs)
    return this
  }

  off<Key extends keyof T>(evt: Key, cb: T[Key]) {
    const cbs = this._eventMap.get(evt)
    if (cbs) {
      this._eventMap.set(
        evt,
        cbs.filter((it) => it !== cb),
      )
    }
    return this
  }

  removeAllEventListeners(): void {
    this._eventMap.clear()
  }

  emit<Key extends keyof T>(evt: Key, ...args: any[]) {
    const cbs = this._eventMap.get(evt) ?? []
    for (const cb of cbs) {
      try {
        cb && cb(...args)
      } catch (e) {
        // cb exception should not affect other callbacks
        const error = e as Error
        const details = error.stack || error.message
        console.error(
          `[event] handling event ${evt.toString()} fail: ${details}`,
        )
      }
    }
    return this
  }
}
