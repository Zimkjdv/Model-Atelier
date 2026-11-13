<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'
import { generationFamily, jobStatusLabels } from './generationNavigation'
import { mergeJob, terminal, useJobEvents, type Job } from './jobEvents'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  locate: [job: Job]
  gallery: [id: string]
}>()
const uid = useId()
const dialog = ref<HTMLDialogElement>()
const trigger = ref<HTMLButtonElement>()
const jobs = ref<Job[]>([])
const total = ref<number | null>(null)
const error = ref('')
const loading = ref(false)
const reads = createRequestScope()
const count = computed(() =>
  total.value === null
    ? null
    : Math.max(
        0,
        total.value -
          jobs.value.filter((job) => previouslyActive.has(job.id) && terminal(job)).length,
      ),
)
let previouslyActive = new Set<string>()
const familyLabels = {
  checkpoint: 'Checkpoint',
  inpaint: '局部修補',
  control: '結構引導',
  reference: '風格／角色參考',
  flux: 'FLUX 文生圖',
  'flux-addon': 'FLUX LoRA／圖生圖',
}

async function refresh() {
  if (document.visibilityState !== 'visible') return
  const request = reads.begin()
  loading.value = true
  try {
    const response = await apiJson<{ items: Job[]; active_total: number }>(
      'library/jobs/overview',
      { signal: request.signal },
    )
    if (!request.isCurrent()) return
    previouslyActive = new Set(
      response.items.filter((item) => !terminal(item)).map((item) => item.id),
    )
    const previous = new Map(jobs.value.map((item) => [item.id, item]))
    jobs.value = response.items.map((item) => mergeJob(previous.get(item.id), item))
    total.value = response.active_total
    error.value = ''
  } catch (cause) {
    if (request.isCurrent())
      error.value = cause instanceof Error ? cause.message : '暫時無法讀取任務清單。'
  } finally {
    if (request.isCurrent()) loading.value = false
  }
}
const { connections, reconnect } = useJobEvents(jobs, refresh, () => props.open)

function visibilityChanged() {
  if (document.visibilityState === 'visible') {
    if (!props.open) void refresh()
  } else {
    reads.cancel()
    loading.value = false
  }
}
let timer: ReturnType<typeof setInterval>
onMounted(() => {
  void refresh()
  document.addEventListener('visibilitychange', visibilityChanged)
  timer = setInterval(() => {
    if (!loading.value && document.visibilityState === 'visible') void refresh()
  }, 15000)
})
onBeforeUnmount(() => {
  reads.dispose()
  clearInterval(timer)
  document.removeEventListener('visibilitychange', visibilityChanged)
})
function close(restoreFocus = true) {
  dialog.value?.close()
  emit('update:open', false)
  if (restoreFocus) trigger.value?.focus()
}
watch(
  () => props.open,
  (open) => {
    if (open && !dialog.value?.open) dialog.value?.showModal()
    else if (!open && dialog.value?.open) dialog.value.close()
  },
)
defineExpose({ refresh, close })
</script>

<template>
  <button
    ref="trigger"
    class="secondary task-drawer-trigger"
    type="button"
    aria-haspopup="dialog"
    :aria-controls="uid"
    :aria-expanded="open"
    @click="emit('update:open', true)"
    >任務抽屜<span v-if="count !== null" class="task-count" :aria-label="count + ' 個未完成任務'">{{
      count
    }}</span></button
  >
  <dialog
    :id="uid"
    ref="dialog"
    class="task-drawer"
    :aria-labelledby="uid + '-title'"
    @cancel.prevent="close()"
    @click.self="close()"
  >
    <div class="task-drawer-content">
      <header>
        <div>
          <h2 :id="uid + '-title'">生成任務</h2>
          <p v-if="count !== null">{{ count }} 個未完成</p>
        </div>
        <button type="button" class="secondary" autofocus @click="close()">關閉</button>
      </header>
      <div class="task-drawer-actions">
        <button type="button" class="secondary" :disabled="loading" @click="refresh"
          >更新任務清單</button
        >
        <button
          v-if="jobs.some((job) => connections[job.id]?.state === 'offline')"
          type="button"
          class="secondary"
          @click="reconnect"
          >重新連線進度</button
        >
      </div>
      <p v-if="error" class="notice warning" role="alert">{{ error }} 已顯示的資料可能已過期。</p>
      <p v-if="total === null && !error" role="status">正在讀取任務…</p>
      <p v-if="total !== null && !jobs.length">尚無生成任務。</p>
      <p v-if="count !== null && count > 20">顯示最近 20 個未完成任務。</p>
      <ul class="task-list">
        <li v-for="job in jobs" :key="job.id" :data-task-id="job.id">
          <strong>{{ jobStatusLabels[job.status] || job.status }}</strong> ·
          {{ familyLabels[generationFamily(job)] }}
          <p>{{ job.checkpoint }} · {{ job.id.slice(0, 8) }}</p>
          <p>原引擎 {{ job.engine_url || '未知' }}</p>
          <p v-if="job.error" class="task-error">{{ job.error }}</p>
          <template v-if="!terminal(job)">
            <p v-if="job.progress"
              >目前節點 {{ job.progress.node
              }}<template v-if="job.progress.percent != null">
                · {{ job.progress.percent }}%</template
              ></p
            >
            <progress
              v-if="job.progress?.percent != null"
              :value="job.progress.percent"
              max="100"
              :aria-label="'任務 ' + job.id + ' 進度'"
            ></progress>
            <p
              v-if="
                connections[job.id]?.state === 'offline' ||
                connections[job.id]?.state === 'reconnecting'
              "
              >進度連線中斷，顯示最後一次回報。</p
            >
          </template>
          <div class="task-drawer-actions">
            <button type="button" class="secondary" @click="emit('locate', job)">前往原任務</button>
            <button
              v-if="job.status === 'completed'"
              type="button"
              class="secondary"
              @click="emit('gallery', job.id)"
              >到作品庫匯入</button
            >
          </div>
        </li>
      </ul>
    </div>
  </dialog>
</template>

<style scoped>
.task-drawer-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.task-count {
  min-width: 1.5em;
  padding-inline: 4px;
  border-radius: 10px;
  background: var(--line);
}
.task-drawer {
  position: fixed;
  inset: 0 0 0 auto;
  box-sizing: border-box;
  width: min(440px, 100%);
  max-width: none;
  height: 100dvh;
  max-height: 100dvh;
  margin: 0;
  padding: 0;
  background: var(--panel);
  color: var(--ink);
  border: 1px solid var(--line);
  overflow-y: auto;
}
.task-drawer::backdrop {
  background: rgb(0 0 0 / 55%);
}
.task-drawer-content {
  padding: 20px;
  overflow-wrap: anywhere;
}
.task-drawer header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 12px;
}
.task-drawer h2,
.task-drawer p {
  margin: 0 0 8px;
}
.task-drawer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-block: 10px;
}
.task-list {
  list-style: none;
  padding: 0;
}
.task-list li {
  border-block-start: 1px solid var(--line);
  padding-block: 14px;
}
.task-error {
  color: var(--text-notice);
}
</style>
