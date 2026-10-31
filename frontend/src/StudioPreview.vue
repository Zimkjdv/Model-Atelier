<script setup lang="ts">
import { computed, onActivated, onDeactivated, onBeforeUnmount, ref, watch } from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'
import type { Job } from './jobEvents'
const props = withDefaults(
  defineProps<{
    width: number
    height: number
    title?: string
    family?: string
    job?: Job | null
    compact?: boolean
  }>(),
  { title: '文字創作', family: '', job: null },
)
const emit = defineEmits<{ gallery: [id: string] }>()
type Output = {
  index: number
  filename: string
  saved: boolean
  local_available: boolean
  width: number | null
  height: number | null
}
const outputs = ref<Output[]>([]),
  selected = ref(0),
  image = ref(''),
  error = ref(''),
  loading = ref(false)
const actual = ref<{ width: number; height: number } | null>(null)
const reads = createRequestScope()
const output = computed(() => outputs.value.find((item) => item.index === selected.value))
const size = computed(
  () =>
    actual.value ||
    (output.value?.width && output.value.height
      ? { width: output.value.width, height: output.value.height }
      : null),
)
function release() {
  if (image.value) URL.revokeObjectURL(image.value)
  image.value = ''
  actual.value = null
}
async function load(manifest = true) {
  const request = reads.begin(),
    job = props.job
  release()
  error.value = ''
  loading.value = false
  if (manifest) {
    outputs.value = []
    selected.value = 0
  }
  if (!job || job.status !== 'completed') return
  loading.value = true
  try {
    if (manifest) {
      const result = await apiJson<{ items: Output[] }>('jobs/' + job.id + '/results', {
        signal: request.signal,
      })
      if (!request.isCurrent()) return
      outputs.value = result.items
    }
    if (!output.value) throw new Error('此任務沒有可顯示的結果圖片。')
    const response = await fetch(`/api/jobs/${job.id}/results/${selected.value}/image`, {
      signal: request.signal,
    })
    if (!response.ok) {
      const value = await response.json().catch(() => ({}))
      throw new Error(value.detail || '結果圖片無法讀取。')
    }
    const blob = await response.blob()
    if (request.isCurrent()) image.value = URL.createObjectURL(blob)
  } catch (cause) {
    if (request.isCurrent() && !request.signal.aborted)
      error.value = cause instanceof Error ? cause.message : '結果讀取失敗。'
  } finally {
    if (request.isCurrent()) loading.value = false
  }
}
watch(
  () => [props.job?.id, props.job?.status, props.job?.revision],
  () => void load(),
  { immediate: true },
)
onBeforeUnmount(() => {
  reads.dispose()
  release()
})
let deactivated = false
onDeactivated(() => {
  deactivated = true
  reads.cancel()
  release()
})
onActivated(() => {
  if (deactivated) {
    deactivated = false
    void load()
  }
})
function imageFailed() {
  error.value = '圖片無法解碼'
  release()
}
function loaded(event: Event) {
  const img = event.target as HTMLImageElement
  actual.value = { width: img.naturalWidth, height: img.naturalHeight }
}
</script>
<template>
  <section
    class="studio-preview"
    aria-label="創作畫布"
    :style="{ '--canvas-ratio': (size?.width || width) / (size?.height || height) }"
  >
    <div class="stage-heading"
      ><div class="comparison-chips"
        ><span>{{ title }}</span
        ><span v-if="family">{{ family }}</span
        ><span v-if="job">{{
          output?.saved ? (output.local_available ? '已存入作品庫' : '作品庫原圖遺失') : '任務結果'
        }}</span
        ><span v-if="compact && job">{{
          job.status === 'completed'
            ? '已完成'
            : job.status === 'running'
              ? '生成中'
              : job.status === 'queued'
                ? '排隊中'
                : '尚未完成'
        }}</span></div
      ><div class="stage-dimensions"
        >{{ size ? size.width + ' × ' + size.height : job ? '尺寸待讀取' : width + ' × ' + height
        }}<span v-if="compact && job" :title="job.id"> · 任務 {{ job.id.slice(0, 8) }}</span></div
      ></div
    >
    <div v-if="job && (!compact || outputs.length > 1)" class="stage-result-meta"
      ><span v-if="!compact">任務 {{ job.id }}</span
      ><label v-if="outputs.length > 1"
        >結果<select v-model="selected" :disabled="loading" @change="load(false)"
          ><option v-for="item in outputs" :key="item.index" :value="item.index"
            >{{ item.index + 1 }} · {{ item.filename }}</option
          ></select
        ></label
      ></div
    >
    <div v-if="image" class="result-canvas"
      ><img :src="image" alt="所選任務的生成結果" @load="loaded" @error="imageFailed"
    /></div>
    <div
      v-else
      class="empty-canvas"
      :style="{ aspectRatio: size ? size.width + ' / ' + size.height : width + ' / ' + height }"
      ><template v-if="loading"><span role="status">正在讀取結果圖片…</span></template
      ><template v-else-if="error"
        ><p role="alert">{{ error }}</p
        ><button class="secondary" @click="load()">重新讀取結果</button></template
      ><template v-else-if="job"
        ><span>{{
          job.status === 'completed'
            ? '結果待讀取'
            : job.status === 'running'
              ? '生成中'
              : job.status === 'queued'
                ? '等待引擎生成'
                : '此任務尚無完成結果'
        }}</span
        ><p v-if="job.progress?.percent != null">{{ job.progress.percent }}%</p
        ><p v-if="job.error">{{ job.error }}</p></template
      ><template v-else><span>準備下一張作品</span><p>設定好後按「生成圖片」。</p></template></div
    >
    <p v-if="job?.status === 'completed'" class="stage-caption"
      >{{
        output?.saved
          ? output.local_available
            ? '顯示已保存原圖，可離線讀取。'
            : '作品庫原圖遺失；目前讀取原引擎結果，請檢查備份。'
          : '僅預覽原引擎結果；尚未保存到作品庫。'
      }}<button v-if="!compact" class="secondary" @click="emit('gallery', job!.id)">{{
        output?.saved ? '前往作品庫' : '前往作品庫匯入'
      }}</button></p
    >
    <p v-else class="stage-caption">預覽依實際輸出尺寸顯示，不同模型的結果比例可能不同。</p>
  </section>
</template>
