<script setup lang="ts">
import { ref, onBeforeUnmount, watch } from 'vue'
import { apiJson } from './apiClient'
const props = defineProps<{ jobId: string }>()
type Output = {
  job_id: string
  state: string
  image_available: boolean
  import_allowed: boolean
  sha256?: string
  message: string
}
const item = ref<Output | null>(null),
  error = ref(''),
  busy = ref(false)
let abort: AbortController | null = null,
  serial = 0
async function load(save = false) {
  if (busy.value) return
  const id = props.jobId,
    current = ++serial
  abort?.abort()
  abort = new AbortController()
  busy.value = true
  error.value = ''
  item.value = null
  try {
    const result = await apiJson<Output>('jobs/' + id + '/structure-output', {
      method: save ? 'POST' : 'GET',
      signal: abort.signal,
    })
    if (current !== serial) return
    if (result.job_id !== id) throw new Error('原任務不符')
    item.value = result
  } catch (e) {
    if (current === serial && !abort?.signal.aborted)
      error.value = e instanceof Error ? e.message : '讀取失敗'
  } finally {
    if (current === serial) busy.value = false
  }
}
watch(
  () => props.jobId,
  () => {
    serial++
    abort?.abort()
    item.value = null
    busy.value = false
  },
)
onBeforeUnmount(() => {
  serial++
  abort?.abort()
})
</script>
<template>
  <details @toggle="($event.target as HTMLDetailsElement).open && load()"
    ><summary>查看原任務的姿勢／深度條件圖</summary><p v-if="error" role="alert">{{ error }}</p
    ><p v-if="item">{{ item.message }}</p
    ><button v-if="item?.import_allowed" :disabled="busy" @click="load(true)"
      >從原引擎保存條件圖</button
    ><template v-if="item?.image_available"
      ><img
        :src="'/api/jobs/' + jobId + '/structure-output/image'"
        alt="原任務實際姿勢或相對深度條件圖"
        style="max-width: 100%"
      /><a :href="'/api/jobs/' + jobId + '/structure-output/image?download=true'" download
        >下載原條件圖</a
      ><p class="footnote">SHA256 {{ item.sha256 }}</p></template
    ></details
  >
</template>
