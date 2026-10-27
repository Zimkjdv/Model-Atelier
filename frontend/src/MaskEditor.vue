<script setup lang="ts">
import {
  computed,
  nextTick,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  ref,
  watch,
} from 'vue'
import type { ReferenceAsset } from './referenceSettings'
import { binaryMask, maskPoint, uploadMaskAsset } from './inpaintSettings'
const props = defineProps<{ source?: ReferenceAsset; mask?: ReferenceAsset; disabled?: boolean }>()
const emit = defineEmits<{
  saved: [value: ReferenceAsset]
  dirty: [value: boolean]
  busy: [value: boolean]
}>()
const canvas = ref<HTMLCanvasElement | null>(null),
  ready = ref(false),
  dirty = ref(false),
  busy = ref(false),
  error = ref(''),
  message = ref('')
const brush = ref(40),
  erase = ref(false),
  white = ref(0),
  file = ref<HTMLInputElement | null>(null)
const editable = computed(() => ready.value && !props.disabled && !busy.value)
const status = computed(() => {
  if (!props.source || props.source.archived) return '請先選擇原圖。'
  if (!ready.value) return error.value ? '遮罩尚未就緒。' : '正在載入遮罩。'
  if (dirty.value) return '遮罩尚未保存，生成已暫停。'
  return props.mask ? '使用已保存遮罩。' : '請繪製或載入遮罩，再保存。'
})
type MaskState = { png: string; white: number; dirty: boolean }
const history = ref<MaskState[]>([]),
  historyIndex = ref(-1)
let active = true
function remember() {
  const png = canvas.value!.toDataURL('image/png')
  if (
    history.value[historyIndex.value]?.png === png &&
    history.value[historyIndex.value]?.dirty === dirty.value
  )
    return
  const states = history.value.slice(0, historyIndex.value + 1)
  states.push({ png, white: white.value, dirty: dirty.value })
  while (
    states.length > 21 ||
    (states.length > 2 &&
      states.reduce((sum, state) => sum + state.png.length, 0) > 32 * 1024 * 1024)
  )
    states.shift()
  history.value = states
  historyIndex.value = states.length - 1
}
async function undo(direction: number) {
  const index = historyIndex.value + direction,
    state = history.value[index]
  if (!state || !editable.value || pointer !== null) return
  const current = ticket
  busy.value = true
  try {
    const loaded = await image(state.png)
    if (current !== ticket) return
    context().clearRect(0, 0, canvas.value!.width, canvas.value!.height)
    context().drawImage(loaded, 0, 0)
    historyIndex.value = index
    white.value = state.white
    dirty.value = state.dirty
    message.value = ''
    error.value = ''
  } catch {
    if (current === ticket) error.value = '無法還原遮罩，原畫布已保留。'
  } finally {
    busy.value = false
  }
}
function region(position: string) {
  if (!editable.value) return
  stop()
  const w = canvas.value!.width,
    h = canvas.value!.height,
    ctx = context()
  const rectangle =
    position === '上方'
      ? [0, 0, w, h / 3]
      : position === '下方'
        ? [0, (h * 2) / 3, w, h / 3]
        : position === '左側'
          ? [0, 0, w / 3, h]
          : position === '右側'
            ? [(w * 2) / 3, 0, w / 3, h]
            : [w / 4, h / 4, w / 2, h / 2]
  ctx.fillStyle = 'white'
  ctx.fillRect(rectangle[0]!, rectangle[1]!, rectangle[2]!, rectangle[3]!)
  changed()
  count()
  remember()
}
function keyboard(event: KeyboardEvent) {
  if (
    !active ||
    !canvas.value?.isConnected ||
    !(event.ctrlKey || event.metaKey) ||
    (event.target as Element)?.closest('input,textarea,select,[contenteditable="true"]')
  )
    return
  if (event.key.toLowerCase() === 'z') {
    event.preventDefault()
    void undo(event.shiftKey ? 1 : -1)
  } else if (event.key.toLowerCase() === 'y') {
    event.preventDefault()
    void undo(1)
  }
}
onMounted(() => document.addEventListener('keydown', keyboard))
let ticket = 0,
  pointer: number | null = null,
  last: { x: number; y: number } | null = null
watch(dirty, (v) => emit('dirty', v), { flush: 'sync', immediate: true })
watch(busy, (v) => emit('busy', v), { flush: 'sync', immediate: true })
function image(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const item = new Image()
    item.onload = () => resolve(item)
    item.onerror = () => reject(new Error('無法讀取素材圖片。'))
    item.src = url
  })
}
function context() {
  const value = canvas.value?.getContext('2d', { willReadFrequently: true })
  if (!value) throw new Error('此瀏覽器無法使用遮罩畫布。')
  return value
}
function count() {
  const value = context().getImageData(0, 0, canvas.value!.width, canvas.value!.height)
  white.value = binaryMask(value.data)
  context().putImageData(value, 0, 0)
}
async function load() {
  stop()
  const current = ++ticket,
    source = props.source,
    mask = props.mask
  ready.value = false
  dirty.value = false
  error.value = ''
  message.value = ''
  white.value = 0
  history.value = []
  historyIndex.value = -1
  if (!source || source.archived) return
  await nextTick()
  if (current !== ticket || !canvas.value) return
  if (source.width * source.height > 16000000) {
    error.value = '原圖超過畫布上限。'
    return
  }
  canvas.value.width = source.width
  canvas.value.height = source.height
  try {
    const ctx = context()
    ctx.fillStyle = 'black'
    ctx.fillRect(0, 0, source.width, source.height)
    if (mask && !mask.archived && mask.width === source.width && mask.height === source.height) {
      const loaded = await image('/api/assets/' + mask.id + '/image')
      if (current !== ticket) return
      if (loaded.naturalWidth !== source.width || loaded.naturalHeight !== source.height)
        throw new Error('遮罩圖片實際尺寸不同，未載入。')
      ctx.fillStyle = 'white'
      ctx.fillRect(0, 0, source.width, source.height)
      ctx.drawImage(loaded, 0, 0)
      count()
    } else white.value = 0
    if (current === ticket) {
      ready.value = true
      remember()
    }
  } catch (e) {
    if (current === ticket) error.value = e instanceof Error ? e.message : '遮罩讀取失敗'
  }
}
function point(event: PointerEvent) {
  return maskPoint(
    event.clientX,
    event.clientY,
    canvas.value!.getBoundingClientRect(),
    canvas.value!.width,
    canvas.value!.height,
  )
}
function line(from: { x: number; y: number }, to: { x: number; y: number }) {
  const ctx = context()
  ctx.strokeStyle = erase.value ? 'black' : 'white'
  ctx.fillStyle = ctx.strokeStyle
  ctx.lineWidth = brush.value
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.beginPath()
  ctx.moveTo(from.x, from.y)
  ctx.lineTo(to.x, to.y)
  ctx.stroke()
  ctx.beginPath()
  ctx.arc(to.x, to.y, brush.value / 2, 0, Math.PI * 2)
  ctx.fill()
  changed()
}
function changed() {
  dirty.value = true
  error.value = ''
  message.value = ''
}
function start(event: PointerEvent) {
  if (!editable.value || pointer !== null || event.button !== 0 || !event.isPrimary) return
  event.preventDefault()
  pointer = event.pointerId
  last = point(event)
  canvas.value!.setPointerCapture(pointer)
  line(last, last)
}
function move(event: PointerEvent) {
  if (event.pointerId !== pointer || !last) return
  if (!editable.value) {
    stop()
    return
  }
  const next = point(event)
  line(last, next)
  last = next
}
function stop(event?: PointerEvent) {
  if (event && event.pointerId !== pointer) return
  const captured = pointer
  pointer = null
  last = null
  if (captured !== null && canvas.value?.hasPointerCapture(captured))
    canvas.value.releasePointerCapture(captured)
  if (captured !== null && ready.value) {
    count()
    remember()
  }
}
function clear() {
  if (!editable.value) return
  stop()
  const ctx = context()
  ctx.fillStyle = 'black'
  ctx.fillRect(0, 0, canvas.value!.width, canvas.value!.height)
  changed()
  white.value = 0
  remember()
}
function invert() {
  if (!editable.value) return
  stop()
  const ctx = context(),
    pixels = ctx.getImageData(0, 0, canvas.value!.width, canvas.value!.height)
  white.value = binaryMask(pixels.data, true)
  ctx.putImageData(pixels, 0, 0)
  changed()
  remember()
}
async function upload(blob: Blob, name: string, current: number, sourceId: string) {
  const value = await uploadMaskAsset(blob, name)
  if (value.width !== props.source?.width || value.height !== props.source?.height)
    throw new Error('保存後的遮罩尺寸不同，未套用。')
  if (current !== ticket || props.source?.id !== sourceId) return
  emit('saved', value as ReferenceAsset)
  message.value = '遮罩已保存為素材；請確認參數後生成。'
  dirty.value = false
}
async function save() {
  if (!ready.value || busy.value || props.disabled || !props.source) return
  stop()
  if (!white.value) {
    error.value = '請先畫出白色編輯範圍。'
    return
  }
  const current = ticket,
    sourceId = props.source.id
  busy.value = true
  error.value = ''
  try {
    const blob = await new Promise<Blob>((resolve, reject) =>
      canvas.value!.toBlob(
        (v) => (v ? resolve(v) : reject(new Error('無法輸出遮罩'))),
        'image/png',
      ),
    )
    if (current === ticket) await upload(blob, 'mask-' + sourceId + '.png', current, sourceId)
  } catch (e) {
    if (current === ticket) error.value = e instanceof Error ? e.message : '保存失敗'
  } finally {
    busy.value = false
  }
}
async function selectFile(event: Event) {
  const input = event.target as HTMLInputElement,
    chosen = input.files?.[0]
  input.value = ''
  if (!chosen || !props.source || !editable.value) return
  stop()
  const current = ticket,
    source = props.source
  busy.value = true
  error.value = ''
  message.value = ''
  let url = ''
  try {
    if (chosen.size > 20 * 1024 * 1024) throw new Error('遮罩檔案不可超過 20 MiB。')
    const signature = new Uint8Array(await chosen.slice(0, 8).arrayBuffer())
    if (![137, 80, 78, 71, 13, 10, 26, 10].every((byte, index) => signature[index] === byte))
      throw new Error('請選擇有效的 PNG 遮罩檔案。')
    if (current !== ticket) return
    url = URL.createObjectURL(chosen)
    const loaded = await image(url)
    if (current !== ticket) return
    if (loaded.naturalWidth !== source.width || loaded.naturalHeight !== source.height)
      throw new Error('遮罩須與原圖尺寸完全相同。')
    const ctx = context()
    ctx.fillStyle = 'white'
    ctx.fillRect(0, 0, source.width, source.height)
    ctx.drawImage(loaded, 0, 0)
    changed()
    count()
    remember()
    message.value = '遮罩已載入畫布，請保存後再生成。'
  } catch (e) {
    if (current === ticket) error.value = e instanceof Error ? e.message : '載入失敗'
  } finally {
    if (url) URL.revokeObjectURL(url)
    busy.value = false
  }
}
watch(
  [
    () => props.source?.id,
    () => props.source?.archived,
    () => props.mask?.id,
    () => props.mask?.archived,
  ],
  () => void load(),
  { immediate: true, flush: 'post' },
)
watch(
  editable,
  (value) => {
    if (!value) stop()
  },
  { flush: 'sync' },
)
onDeactivated(() => {
  active = false
  stop()
  ++ticket
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', keyboard)
  stop()
  ++ticket
})
onActivated(() => {
  active = true
  if (!ready.value && !dirty.value) void load()
})
</script>
<template>
  <section class="mask-editor" aria-label="遮罩繪製">
    <h3>標出要修改的範圍</h3>
    <p class="footnote"
      >白色範圍會重新生成，黑色保留處理後原圖。筆刷尺寸以原圖像素計算；保存後才能使用新遮罩。</p
    >
    <div class="tools"
      ><button
        type="button"
        class="secondary"
        :disabled="!editable || historyIndex <= 0"
        @click="undo(-1)"
        >復原</button
      ><button
        type="button"
        class="secondary"
        :disabled="!editable || historyIndex >= history.length - 1"
        @click="undo(1)"
        >重做</button
      >
      <button
        type="button"
        class="secondary"
        :aria-pressed="!erase"
        :disabled="disabled || busy || !ready"
        @click="erase = false"
        >筆刷</button
      ><button
        type="button"
        class="secondary"
        :aria-pressed="erase"
        :disabled="disabled || busy || !ready"
        @click="erase = true"
        >擦除</button
      ><label for="mask-brush"
        >大小
        <input
          id="mask-brush"
          v-model.number="brush"
          type="range"
          min="1"
          max="256"
          :disabled="!editable"
        />
        {{ brush }} px</label
      ></div
    >
    <div
      v-if="source && !source.archived"
      class="mask-stage"
      :style="{ aspectRatio: String(source.width / source.height) }"
      ><img :src="'/api/assets/' + source.id + '/image'" alt="遮罩繪製用原圖" /><canvas
        ref="canvas"
        aria-label="在原圖上繪製白色編輯範圍"
        @pointerdown="start"
        @pointermove="move"
        @pointerup="stop"
        @pointercancel="stop"
        @lostpointercapture="stop"
    /></div>
    <div class="tools"
      ><button type="button" class="secondary" :disabled="disabled || busy || !ready" @click="clear"
        >清空</button
      ><button
        type="button"
        class="secondary"
        :disabled="disabled || busy || !ready"
        @click="invert"
        >反相</button
      ><button
        type="button"
        class="secondary"
        :disabled="disabled || busy || !ready"
        @click="file?.click()"
        >載入 PNG 遮罩</button
      ><input
        ref="file"
        class="mask-file"
        type="file"
        accept="image/png"
        @change="selectFile"
      /><button
        type="button"
        class="primary"
        :disabled="disabled || busy || !ready || !white || !dirty"
        @click="save"
        >{{ busy ? '處理中…' : '保存遮罩' }}</button
      ></div
    >
    <details
      ><summary>鍵盤區塊選取與快捷鍵</summary
      ><p class="footnote"
        >Ctrl/Cmd+Z 復原，Shift+Ctrl/Cmd+Z 或 Ctrl+Y 重做。文字欄位保留原生快捷鍵。</p
      ><div class="tools"
        ><button
          v-for="position in ['中央', '上方', '下方', '左側', '右側']"
          :key="position"
          type="button"
          class="secondary"
          :disabled="!editable"
          @click="region(position)"
          >{{ position }}區塊</button
        ></div
      ></details
    >
    <p class="footnote" role="status"
      >{{ status }} 已標記 {{ white.toLocaleString() }} 個原圖像素。</p
    >
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p
    ><p v-if="message" class="notice" role="status">{{ message }}</p>
  </section>
</template>
<style scoped>
.mask-editor {
  margin-top: 20px;
  border-top: 1px solid var(--border-control);
  padding-top: 18px;
}
.mask-editor h3 {
  font-size: 14px;
}
.tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin: 14px 0;
}
.tools label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.tools input {
  width: 120px;
}
.mask-stage {
  position: relative;
  width: 100%;
  max-height: none;
  background: white;
  isolation: isolate;
}
.mask-stage img {
  display: block;
  width: 100%;
  height: 100%;
  position: absolute;
  inset: 0;
  object-fit: fill;
}
.mask-stage canvas {
  display: block;
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0.55;
  mix-blend-mode: screen;
  touch-action: none;
  cursor: crosshair;
}
.mask-file {
  display: none;
}
.footnote {
  line-height: 1.7;
}
.tools [aria-pressed='true'] {
  border-color: var(--focus-ring);
}
</style>
