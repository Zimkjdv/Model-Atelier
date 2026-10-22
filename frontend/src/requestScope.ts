/** One replaceable read at a time; cancellation also invalidates ignored aborts. */
export function createRequestScope() {
  let version = 0, controller: AbortController | null = null, disposed = false
  function cancel() { ++version; controller?.abort(); controller = null }
  return {
    begin() {
      if (disposed) throw new Error('資料查詢已結束。')
      cancel()
      const current = version, request = new AbortController()
      controller = request
      return { signal: request.signal, isCurrent: () => !disposed && current === version && !request.signal.aborted }
    },
    cancel,
    dispose() { disposed = true; cancel() },
  }
}
