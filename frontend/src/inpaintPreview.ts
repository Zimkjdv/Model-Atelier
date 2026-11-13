import type { FeatherForm } from './inpaintSettings'

const previewErrorLimit = 64 * 1024
const previewImageLimit = 32 * 1024 * 1024
const previewErrorFallback = '合成遮罩預覽失敗。'

async function readPreviewBytes(response: Response) {
  const reader = response.body?.getReader()
  if (!reader) {
    if (response.ok) throw new Error('預覽回應沒有圖片。')
    return new Uint8Array()
  }

  const limit = response.ok ? previewImageLimit : previewErrorLimit
  const chunks: Uint8Array[] = []
  let size = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      size += value.byteLength
      if (size > limit) {
        await reader.cancel()
        throw new Error(response.ok ? '預覽圖片超過 32 MiB。' : '預覽錯誤回應超過 64 KiB。')
      }
      if (value.byteLength) chunks.push(value)
    }
  } finally {
    reader.releaseLock()
  }

  const raw = new Uint8Array(size)
  let offset = 0
  for (const chunk of chunks) {
    raw.set(chunk, offset)
    offset += chunk.byteLength
  }
  return raw
}

function previewErrorMessage(raw: Uint8Array): string {
  try {
    const value: unknown = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(raw))
    if (value && typeof value === 'object' && 'detail' in value) {
      const { detail } = value
      if (typeof detail === 'string' && detail.trim()) return detail
    }
  } catch {
    return previewErrorFallback
  }
  return previewErrorFallback
}

export function blendPreviewIdentity(form: FeatherForm) {
  return JSON.stringify([
    form.image_asset_id,
    form.mask_asset_id,
    form.reference_ids,
    form.width,
    form.height,
    form.reference_resize,
    form.feather_radius,
  ])
}
export async function checkedBlendPreview(response: Response, form: FeatherForm): Promise<Blob> {
  if (!response.ok) throw new Error(previewErrorMessage(await readPreviewBytes(response)))
  const hash = response.headers.get('X-Atelier-SHA256') || ''
  if (
    response.headers.get('Content-Type')?.split(';')[0] !== 'image/png' ||
    !/^[0-9a-f]{64}$/.test(hash) ||
    response.headers.get('X-Atelier-Width') !== String(form.width) ||
    response.headers.get('X-Atelier-Height') !== String(form.height) ||
    response.headers.get('X-Atelier-Feather-Radius') !== String(form.feather_radius)
  )
    throw new Error('預覽回應與本次輸入不同，未顯示。')
  const raw = await readPreviewBytes(response)
  const view = new DataView(raw.buffer)
  if (
    raw.byteLength < 33 ||
    [137, 80, 78, 71, 13, 10, 26, 10].some((v, i) => raw[i] !== v) ||
    String.fromCharCode(...raw.slice(12, 16)) !== 'IHDR' ||
    view.getUint32(16) !== form.width ||
    view.getUint32(20) !== form.height ||
    raw[24] !== 8 ||
    raw[25] !== 2
  )
    throw new Error('預覽 PNG 尺寸或格式不同。')
  const actual = [...new Uint8Array(await crypto.subtle.digest('SHA-256', raw))]
    .map((n) => n.toString(16).padStart(2, '0'))
    .join('')
  if (actual !== hash) throw new Error('預覽圖片 SHA256 不符，未顯示。')
  return new Blob([raw], { type: 'image/png' })
}
