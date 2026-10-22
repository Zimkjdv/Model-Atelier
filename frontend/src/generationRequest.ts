import { apiJson, ApiError } from './apiClient'

/** A single attempt using the frozen descriptor, with no retry or form access. */
export async function submitOnce<T>(submission: { path: string; body: unknown }, confirmed: () => void): Promise<T> {
  try {
    const value = await apiJson<T>(submission.path, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(submission.body),
    })
    confirmed()
    return value
  } catch (error) {
    if (error instanceof ApiError && error.conclusive) confirmed()
    throw error
  }
}
