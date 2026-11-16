<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
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
const refreshButton = ref<HTMLButtonElement>()
const pagination = ref<HTMLElement>()
const jobs = ref<Job[]>([])
const recent = ref<Job[]>([])
const total = ref<number | null>(null)
const page = ref(1)
const limit = ref(20)
const error = ref('')
const loading = ref(false)
const reads = createRequestScope()
const activeJobs = computed(() => jobs.value.filter((job) => !terminal(job)))
const settled = computed(() => jobs.value.length - activeJobs.value.length)
const count = computed(() => (total.value === null ? null : total.value - settled.value))
const lastPage = computed(() => Math.max(page.value, Math.ceil((count.value ?? 0) / limit.value)))
const groups = computed(() => [
  { label: '未完成任務', items: activeJobs.value },
  { label: '最近結束的任務', items: recent.value },
])
const familyLabels = {
  checkpoint: 'Checkpoint',
  inpaint: '局部修補',
  control: '結構引導',
  reference: '風格／角色參考',
  flux: 'FLUX 文生圖',
  'flux-addon': 'FLUX LoRA／圖生圖',
}

async function loadPage(target: number | 'last') {
  if (document.visibilityState !== 'visible') return
  const request = reads.begin()
  loading.value = true
  try {
    const response = await apiJson<{
      items: Job[]
      active_total: number
      active_page: number
      active_limit: number
    }>('library/jobs/overview?active_page=' + target, { signal: request.signal })
    if (!request.isCurrent()) return
    const previous = new Map(jobs.value.map((item) => [item.id, item]))
    jobs.value = response.items
      .filter((item) => !terminal(item))
      .map((item) => mergeJob(previous.get(item.id), item))
    recent.value = response.items.filter(terminal)
    total.value = response.active_total
    page.value = response.active_page
    limit.value = response.active_limit
    error.value = ''
  } catch (cause) {
    if (request.isCurrent())
      error.value = cause instanceof Error ? cause.message : '暫時無法讀取任務清單。'
  } finally {
    if (request.isCurrent()) loading.value = false
  }
}

async function refresh() {
  if (!loading.value) await loadPage(page.value)
}

async function turnPage(target: number | 'last') {
  if (loading.value || target === page.value) return
  if (target === 'last' ? page.value >= lastPage.value : target < 1 || target > lastPage.value)
    return
  await loadPage(target)
}

const { connections, reconnect } = useJobEvents(jobs, refresh, () => props.open)
watch(settled, (value) => {
  if (value) void refresh()
})
watch(lastPage, async (value) => {
  if (value !== 1 || !pagination.value?.contains(document.activeElement)) return
  await nextTick()
  if (props.open) refreshButton.value?.focus()
})

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
    void refresh()
  }, 15000)
})
onBeforeUnmount(() => {
  reads.dispose()
  clearInterval(timer)
  document.removeEventListener('visibilitychange', visibilityChanged)
})
function close(restoreFocus = true) {
  dialog.value?.close()
  reads.cancel()
  loading.value = false
  emit('update:open', false)
  if (restoreFocus) trigger.value?.focus()
}
watch(
  () => props.open,
  (open) => {
    if (open && !dialog.value?.open) dialog.value?.showModal()
    if (!open) {
      dialog.value?.close()
      reads.cancel()
      loading.value = false
    }
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
    :aria-controls="open ? uid : undefined"
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
        <button
          ref="refreshButton"
          type="button"
          class="secondary"
          :aria-disabled="loading"
          @click="refresh"
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
      <p v-if="total === 0 && !recent.length">尚無生成任務。</p>
      <nav v-if="lastPage > 1" ref="pagination" aria-label="未完成任務分頁">
        <p role="status">未完成任務第 {{ page }}／{{ lastPage }} 頁</p>
        <div class="task-drawer-actions">
          <button
            type="button"
            class="secondary"
            :aria-disabled="loading || page === 1"
            @click="turnPage(page - 1)"
            >上一頁</button
          >
          <button
            type="button"
            class="secondary"
            :aria-disabled="loading || page === lastPage"
            @click="turnPage(page + 1)"
            >下一頁</button
          >
          <button
            type="button"
            class="secondary"
            :aria-disabled="loading || page === lastPage"
            @click="turnPage('last')"
            >最早一頁</button
          >
        </div>
      </nav>
      <template v-for="group in groups" :key="group.label">
        <template v-if="group.items.length">
          <h3>{{ group.label }}</h3>
          <ul class="task-list" :aria-label="group.label">
            <li v-for="job in group.items" :key="job.id" :data-task-id="job.id">
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
                <button type="button" class="secondary" @click="emit('locate', job)"
                  >前往原任務</button
                >
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
        </template>
      </template>
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
.task-drawer h3,
.task-drawer p {
  margin: 0 0 8px;
}
.task-drawer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-block: 10px;
}
.task-drawer-actions button[aria-disabled='true'] {
  opacity: 0.55;
  cursor: default;
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
