<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from './apiClient'
import { createRequestScope } from './requestScope'
import { categoryGb, storageCategoryNames, type StorageCategoryReport } from './systemTypes'

const props = defineProps<{ visible: boolean; engineUrl: string }>()
const emit = defineEmits<{ report: [value: StorageCategoryReport]; error: [value: boolean] }>()
const report = ref<StorageCategoryReport | null>(null)
const error = ref('')
const action = ref<'start' | 'cancel' | null>(null)
const cancelRequested = ref<string | null>(null)
const request = createRequestScope()
let poll: ReturnType<typeof setTimeout> | undefined
const scan = computed(() => report.value?.scan)
const active = computed(() => scan.value?.status === 'queued' || scan.value?.status === 'running')
const result = computed(() =>
  scan.value?.categories ? scan.value : (report.value?.last_completed ?? report.value?.last_result),
)
const currentCategories = computed(() =>
  scan.value?.scope.version === report.value?.scope.version ? scan.value?.categories : undefined,
)
const states = {
  queued: '已排入掃描',
  running: '掃描中',
  completed: '掃描完成',
  partial: '掃描不完整',
  cancelled: '掃描已取消',
  failed: '掃描失敗',
}
const showTime = (value: string) => new Date(value).toLocaleString('zh-TW')
function share(models: number, artworks: number) {
  return (100 * models) / (models + artworks) + '%'
}

function schedule() {
  clearTimeout(poll)
  if (!document.hidden) poll = setTimeout(refresh, active.value ? 1500 : 60_000)
}
async function refresh() {
  if (!action.value && !document.hidden) await load('storage/categories')
}
async function load(path: string, operation?: 'start' | 'cancel') {
  clearTimeout(poll)
  const query = request.begin()
  const previous = scan.value?.id
  if (operation) action.value = operation
  try {
    const value = await api<StorageCategoryReport>(
      path,
      operation ? 'POST' : 'GET',
      operation ? {} : undefined,
      query.signal,
    )
    if (!query.isCurrent()) return
    report.value = value
    error.value = ''
    if (operation === 'cancel' && previous) cancelRequested.value = previous
    emit('report', value)
    emit('error', false)
  } catch (failure) {
    if (!query.isCurrent()) return
    error.value = failure instanceof Error ? failure.message : '無法讀取分類容量。'
    emit('error', true)
  } finally {
    if (query.isCurrent()) {
      action.value = null
      schedule()
    }
  }
}
function visibility() {
  if (document.hidden) clearTimeout(poll)
  else void refresh()
}
onMounted(() => {
  document.addEventListener('visibilitychange', visibility)
  void refresh()
})
watch([() => props.visible, () => props.engineUrl], () => {
  void refresh()
})
onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', visibility)
  clearTimeout(poll)
  request.dispose()
})
</script>

<template>
  <section class="panel category-capacity" aria-labelledby="category-capacity-title">
    <div class="category-heading">
      <div>
        <h2 id="category-capacity-title">分類容量</h2>
        <p class="muted">統計本機模型與作品庫的檔案邏輯大小。</p>
      </div>
      <div class="category-actions">
        <button type="button" class="secondary" @click="refresh" :disabled="action !== null"
          >更新狀態</button
        >
        <button
          v-if="active && scan"
          type="button"
          class="secondary"
          :disabled="action !== null || cancelRequested === scan.id"
          @click="load('storage/scans/' + scan.id + '/cancel', 'cancel')"
          >{{ cancelRequested === scan.id ? '正在取消…' : '取消掃描' }}</button
        >
        <button
          v-else
          type="button"
          :disabled="action !== null || !report"
          @click="load('storage/scans', 'start')"
          >開始分類掃描</button
        >
      </div>
    </div>
    <p v-if="error" class="notice warning" role="alert">
      分類容量請求失敗。{{ error }}{{ report ? ' 目前保留上次回報。' : '' }}
    </p>
    <p role="status">
      <template v-if="scan">
        {{ states[scan.status] }}
        <template v-if="active">
          · 已檢查 {{ scan.visited.toLocaleString('zh-TW') }} 個項目</template
        >
        <template v-else-if="scan.finished_at"> · {{ showTime(scan.finished_at) }}</template>
        {{ scan.error || '' }}
      </template>
      <template v-else>{{ report ? '尚未掃描。' : '尚無掃描狀態。' }}</template>
    </p>

    <dl v-if="report" class="category-results" aria-label="分類容量結果">
      <div v-for="(name, category) in storageCategoryNames" :key="category">
        <dt>{{ name }}</dt>
        <dd v-if="report.known[category]">
          <strong>{{ categoryGb(report.known[category].bytes) }}</strong>
          <small :class="{ muted: !report.known[category].stale_reason && !error }">
            {{ report.known[category].stale_reason || error ? '已過期 · ' : '' }}
            {{ showTime(report.known[category].checked_at) }}
            {{
              currentCategories?.[category].status === 'partial' ||
              currentCategories?.[category].status === 'unavailable'
                ? ' · 上次可靠值'
                : ''
            }}
          </small>
        </dd>
        <dd v-else-if="report.scope.unavailable.includes(category)">此部署或設定無法統計</dd>
        <dd v-else-if="currentCategories?.[category].status === 'unavailable'">無法統計</dd>
        <dd v-else-if="currentCategories?.[category].status === 'partial'">掃描不完整</dd>
        <dd v-else>尚未統計</dd>
      </div>
      <div><dt>其他</dt><dd>未知</dd></div>
    </dl>

    <p v-if="report?.scope.external_engine" class="muted">外部引擎的檔案無法從平台統計。</p>
    <p v-if="result?.stale_reason" class="notice warning"
      >掃描結果已過期。{{ result.stale_reason }}</p
    >
    <details v-if="result?.categories" :open="result.status === 'partial' || undefined">
      <summary>{{ scan?.id === result.id ? '掃描明細' : '上次掃描明細' }}</summary>
      <p class="muted"
        >{{ result.finished_at && showTime(result.finished_at) }} · 已檢查
        {{ result.visited.toLocaleString('zh-TW') }} 個項目</p
      >
      <p v-if="result.status === 'partial'">不完整的分類僅列出本次已讀取的用量。</p>
      <div v-for="volume in result.volumes" :key="volume.id" class="category-volume">
        <strong>{{ volume.path }}</strong>
        <div
          v-if="
            result.status === 'completed' &&
            !result.stale_reason &&
            !error &&
            volume.models + volume.artworks > 0
          "
          class="category-share"
          aria-hidden="true"
          ><span :style="{ width: share(volume.models, volume.artworks) }"></span
        ></div>
        <ul>
          <li v-for="(name, category) in storageCategoryNames" :key="category">
            {{ name }}
            <template v-if="result.categories[category].status !== 'unavailable'">
              {{ categoryGb(volume[category]) }}
              {{ result.categories[category].status === 'partial' ? '（已讀取）' : '' }}
            </template>
            <template v-else>未知</template>
          </li>
        </ul>
      </div>
      <p v-if="result.issue_count"
        >掃描問題 {{ result.issue_count }} 項<span
          v-if="result.issue_count > (result.issues?.length ?? 0)"
          >（顯示前 {{ result.issues?.length }} 項）</span
        ></p
      >
      <ul v-if="result.issues?.length" class="category-issues">
        <li v-for="(issue, index) in result.issues" :key="index">
          {{ storageCategoryNames[issue.category] }} · {{ issue.message }}
          <code>{{ issue.path }}</code>
        </li>
      </ul>
    </details>
    <details v-if="report">
      <summary>掃描範圍與計量</summary>
      <ul class="category-issues">
        <li v-for="root in report.scope.roots" :key="root.category + root.path">
          {{ storageCategoryNames[root.category] }} · <code>{{ root.path }}</code>
        </li>
      </ul>
      <p
        >分段條顯示各磁碟區已完整統計的模型與作品比例。磁碟已用容量採實際空間口徑，其他用量維持未知。</p
      >
    </details>
  </section>
</template>

<style scoped>
.category-capacity {
  display: grid;
  gap: 12px;
  margin-block: 16px;
}
.category-heading,
.category-actions,
.category-results,
.category-volume ul {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 18px;
}
.category-heading {
  justify-content: space-between;
  align-items: start;
}
.category-actions {
  gap: 8px;
}
.category-capacity h2,
.category-capacity p,
.category-results,
.category-results dd {
  margin: 0;
}
.category-results > div {
  min-width: 5rem;
  flex: 1 1 5rem;
}
.category-results small {
  display: block;
}
.category-volume {
  margin-block: 12px;
}
.category-volume ul {
  list-style: none;
  margin: 6px 0;
  padding: 0;
}
.category-share {
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
  background: #90cbd2;
}
.category-share span {
  display: block;
  height: 100%;
  background: #b9d3a4;
}
.category-issues {
  overflow-wrap: anywhere;
}
.category-capacity details > p {
  margin-top: 8px;
}
</style>
