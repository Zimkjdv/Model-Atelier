export type ApiErrorKind = 'http' | 'network' | 'aborted' | 'invalid-response'

export class ApiError extends Error {
  constructor(message: string, readonly kind: ApiErrorKind, readonly status: number | null = null,
    readonly detail: unknown = null, readonly conclusive = false) {
    super(message)
    this.name = kind === 'aborted' ? 'AbortError' : 'ApiError'
  }
}

function message(detail: unknown, status: number): string {
  if (typeof detail === 'string' && detail.trim()) return detail.slice(0, 1000)
  if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') return detail.message.slice(0, 1000)
  if (Array.isArray(detail)) {
    const fields = detail.slice(0, 3).flatMap(item => {
      if (!item || typeof item.msg !== 'string') return []
      const location = Array.isArray(item.loc) ? item.loc.filter((part: unknown) => typeof part === 'string' || typeof part === 'number').filter((part: unknown) => part !== 'body').join('.') : ''
      return [(location ? location + '：' : '') + item.msg.slice(0, 240)]
    })
    if (fields.length) return fields.join('；')
  }
  return `平台請求失敗（HTTP ${status}），請查詢原請求或檢查服務狀態。`
}

async function httpError(response: Response): Promise<ApiError> {
  let payload: unknown = null, parsed = false
  const reader = response.body?.getReader()
  if (reader) {
    const chunks: Uint8Array[] = []
    let size = 0
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        size += value.byteLength
        if (size > 64 * 1024) { await reader.cancel(); break }
        chunks.push(value)
      }
      if (size <= 64 * 1024) {
        const raw = new Uint8Array(size)
        let offset = 0
        for (const chunk of chunks) { raw.set(chunk, offset); offset += chunk.byteLength }
        payload = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(raw))
        parsed = true
      }
    } catch { /* HTML, incomplete or malformed replies are not API receipts. */ }
    finally { reader.releaseLock() }
  }
  const detail = payload && typeof payload === 'object' && 'detail' in payload ? payload.detail : null
  const hasJob = detail && typeof detail === 'object' && 'job_id' in detail && typeof detail.job_id === 'string' && detail.job_id.length > 0
  return new ApiError(message(detail, response.status), 'http', response.status, detail,
    parsed && ((response.status >= 400 && response.status < 500) || !!hasJob))
}

function cancelled(signal?: AbortSignal | null): ApiError | null {
  return signal?.aborted ? new ApiError('已取消此資料查詢。', 'aborted') : null
}

/** Checked HTTP response; successful body remains untouched for byte/hash validators. */
export async function apiResponse(path: string, options: RequestInit = {}): Promise<Response> {
  const aborted = cancelled(options.signal)
  if (aborted) throw aborted
  let response: Response
  try { response = await fetch(path.startsWith('/api/') ? path : '/api/' + path, options) }
  catch (error) {
    throw cancelled(options.signal) || (error instanceof Error && error.name === 'AbortError'
      ? new ApiError('已取消此資料查詢。', 'aborted') : new ApiError('無法連接平台，請檢查連線並查詢原請求。', 'network'))
  }
  const stale = cancelled(options.signal)
  if (stale) throw stale
  if (!response.ok) {
    const error = await httpError(response)
    throw cancelled(options.signal) || error
  }
  return response
}

// Domain validation stays with callers; this has the same default as Response.json().
export async function apiJson<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await apiResponse(path, options)
  try {
    const value = await response.json()
    const aborted = cancelled(options.signal)
    if (aborted) throw aborted
    return value as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw cancelled(options.signal) || new ApiError('平台回應不是完整 JSON，請查詢原請求；目前設定保持不變。', 'invalid-response', response.status)
  }
}

export function api<T = any>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  return apiJson<T>(path, { method, signal, ...(body === undefined ? {} : {
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  }) })
}

/** JSON exchange/workflow text is returned verbatim, never reserialized. */
export async function apiText(path: string, options: RequestInit = {}): Promise<string> {
  const response = await apiResponse(path, options)
  try {
    const value = await response.text()
    const aborted = cancelled(options.signal)
    if (aborted) throw aborted
    return value
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw cancelled(options.signal) || new ApiError('平台回應未完整接收，請查詢原請求。', 'invalid-response', response.status)
  }
}
