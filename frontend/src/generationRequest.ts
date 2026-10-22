import { apiJson, ApiError } from './apiClient'

const receiptMessage = '平台回覆的任務 ID 缺失或與原請求不同；請保留原請求並查詢。'

function confirmsOriginalRequest(receipt: unknown, body: unknown): boolean {
  return !!(
    body &&
    typeof body === 'object' &&
    !Array.isArray(body) &&
    'request_id' in body &&
    typeof body.request_id === 'string' &&
    body.request_id &&
    receipt &&
    typeof receipt === 'object' &&
    !Array.isArray(receipt) &&
    'id' in receipt &&
    receipt.id === body.request_id
  )
}

/** A single attempt using the frozen descriptor, with no retry or form access. */
export async function submitOnce<T>(
  submission: { path: string; body: unknown },
  confirmed: () => void,
): Promise<T> {
  try {
    const value = await apiJson<T>(submission.path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(submission.body),
    })
    if (!confirmsOriginalRequest(value, submission.body))
      throw new ApiError(receiptMessage, 'invalid-response', 200)
    confirmed()
    return value
  } catch (error) {
    if (error instanceof ApiError && error.conclusive) {
      const detail = error.detail
      if (
        detail &&
        typeof detail === 'object' &&
        'job_id' in detail &&
        !confirmsOriginalRequest({ id: detail.job_id }, submission.body)
      )
        throw new ApiError(
          receiptMessage,
          'invalid-response',
          error.status,
          null,
          false,
          error.requestId,
        )
      confirmed()
    }
    throw error
  }
}
