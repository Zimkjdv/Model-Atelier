<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import TrainingReviewNavigator from './TrainingReviewNavigator.vue'
import { api } from './apiClient'
import { createRequestScope } from './requestScope'
import { useUnsavedChanges } from './unsavedChanges'
import {
  type DatasetReview,
  type DatasetSummary,
  type Readiness,
  type TrainingExport,
  trainingIssue,
} from './trainingTypes'

const props = defineProps<{ stage?: number }>()
const emit = defineEmits<{ dirty: [value: boolean]; review: [] }>()
const list = ref<DatasetSummary[]>([]),
  current = ref<DatasetReview | null>(null),
  edited = ref<DatasetReview | null>(null)
const available = ref(true),
  busy = ref(false),
  readingFile = ref(false),
  error = ref(''),
  message = ref('')
const importOpen = ref(false)
const source = ref(''),
  manifest = ref(''),
  study = ref(''),
  importId = ref(''),
  nextVersion = ref('')
const selected = ref(''),
  imageFailed = ref(false),
  readiness = ref<Readiness | null>(null)
const exported = ref<TrainingExport | null>(null),
  exportId = ref('')
const scope = createRequestScope()
let alive = true
const dirty = computed(
  () =>
    !!current.value &&
    JSON.stringify(current.value.dataset) !== JSON.stringify(edited.value?.dataset),
)
const protectedState = computed(() => dirty.value || busy.value || readingFile.value)
useUnsavedChanges(protectedState)
watch(protectedState, (v) => emit('dirty', v), { immediate: true })
const reviewSummary = computed(() => {
  const images = current.value?.dataset.images || []
  const counts = { train: 0, validation: 0, test: 0, excluded: 0 }
  for (const image of images) counts[image.split]++
  const candidates = new Set(
    images.filter((image) => image.split === 'train').map((image) => image.id),
  )
  const report = readiness.value
  if (!report) return { counts, captionReady: null, pending: null, otherIssues: null }
  const candidateIssues = report.issues.filter((issue) => candidates.has(issue.image_id || ''))
  const pending = new Set(candidateIssues.map((issue) => issue.image_id)).size
  const captionPending = new Set(
    candidateIssues
      .filter((issue) => issue.code === 'caption_review_required')
      .map((issue) => issue.image_id),
  ).size
  return {
    counts,
    captionReady: candidates.size - captionPending,
    pending,
    otherIssues: report.issues.length - candidateIssues.length,
  }
})
const exportChecks = computed(() => {
  const groups = [
    { label: '圖片描述與標註審查', codes: ['caption_review_required'] },
    { label: '來源與訓練用途依據', codes: ['source_use_record_required'] },
    {
      label: '分組與角色身分',
      codes: [
        'target_character_review_required',
        'final_test_previously_exposed',
        'multiple_training_variants',
        'no_training_candidates',
      ],
    },
  ]
  const known = new Set(groups.flatMap((group) => group.codes))
  return [
    ...groups.map((group) => ({
      label: group.label,
      issues: readiness.value?.issues.filter((issue) => group.codes.includes(issue.code)) || [],
    })),
    {
      label: '原圖與其他完整性',
      issues: readiness.value?.issues.filter((issue) => !known.has(issue.code)) || [],
    },
  ]
})
async function saveNext() {
  const previous = selected.value
  await save()
  if (dirty.value || error.value || !edited.value) return
  const images = edited.value.dataset.images
  const index = images.findIndex((item) => item.id === previous)
  selected.value = images[index + 1]?.id || previous
}
const image = computed(() => edited.value?.dataset.images.find((v) => v.id === selected.value))
async function selectImage(id: string, focus: boolean) {
  selected.value = id
  if (focus) {
    await nextTick()
    if (alive) document.getElementById('training-image-editor')?.focus()
  }
}
watch(
  () => [selected.value, current.value?.revision],
  () => {
    imageFailed.value = false
  },
)
function apply(value: DatasetReview) {
  current.value = value
  edited.value = structuredClone(value)
  readiness.value = value.readiness
  nextVersion.value = `review-${value.revision + 1}`
  selected.value = value.dataset.images[0]?.id || ''
  exported.value = null
  exportId.value = ''
}
async function refresh() {
  const request = scope.begin()
  try {
    const value = await api<{ available: boolean; datasets: DatasetSummary[] }>(
      'training/datasets',
      'GET',
      undefined,
      request.signal,
    )
    if (alive && request.isCurrent()) {
      available.value = value.available
      list.value = value.datasets
      if (!current.value && value.datasets[0]) void load(value.datasets[0].id)
    }
  } catch (e) {
    if (alive && request.isCurrent()) error.value = String(e)
  }
}
async function load(id: string) {
  if (busy.value || (dirty.value && !window.confirm('資料標註尚未保存，確定載入其他版本？'))) return
  const request = scope.begin()
  error.value = ''
  try {
    const value = await api<DatasetReview>(
      'training/datasets/' + id,
      'GET',
      undefined,
      request.signal,
    )
    if (alive && request.isCurrent()) apply(value)
  } catch (e) {
    if (alive && request.isCurrent()) error.value = String(e)
  }
}
async function file(event: Event, kind: 'manifest' | 'study') {
  const input = event.target as HTMLInputElement,
    value = input.files?.[0]
  if (!value) return
  if (kind === 'manifest') manifest.value = ''
  else study.value = ''
  importId.value = ''
  readingFile.value = true
  error.value = ''
  try {
    if (value.size > 8 * 1024 * 1024) throw Error('JSON 檔案不可超過 8 MiB')
    const text = new TextDecoder('utf-8', { fatal: true }).decode(await value.arrayBuffer())
    if (alive) {
      if (kind === 'manifest') manifest.value = text
      else study.value = text
    }
  } catch (e) {
    if (alive) error.value = '無法讀取 UTF-8 JSON：' + String(e)
  } finally {
    if (alive) readingFile.value = false
    input.value = ''
  }
}
async function operation(action: () => Promise<void>) {
  if (busy.value) return
  scope.cancel()
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    await action()
  } catch (e) {
    if (alive) error.value = String(e)
  } finally {
    if (alive) busy.value = false
  }
}
async function importing() {
  if (dirty.value && !window.confirm('目前標註尚未保存，確定匯入另一份資料？')) return
  await operation(async () => {
    importId.value ||= crypto.randomUUID()
    const value = await api<DatasetReview>('training/datasets', 'POST', {
      request_id: importId.value,
      source_root: source.value,
      manifest_json: manifest.value,
      study_json: study.value,
    })
    if (alive) {
      apply(value)
      message.value = '已匯入待審查資料；原圖與原清單未修改。'
      await refresh()
    }
  })
}
async function save() {
  const value = edited.value
  if (!value || !current.value) return
  const id = current.value.id
  await operation(async () => {
    const images = value.dataset.images.map(
      ({
        id,
        group_id,
        split,
        exclusion_reason,
        exposure,
        identity,
        character_ids,
        caption,
        provenance,
      }) => ({
        id,
        group_id,
        split,
        exclusion_reason,
        exposure,
        identity,
        character_ids,
        caption,
        provenance,
      }),
    )
    const result = await api<DatasetReview>('training/datasets/' + id, 'PUT', {
      revision: current.value!.revision,
      version: nextVersion.value,
      images,
    })
    if (alive) {
      const previous = selected.value
      apply(result)
      selected.value = previous
      message.value = '已保存新版本；舊修訂可下載追溯。'
      await refresh()
    }
  })
}
async function check() {
  if (!current.value) return
  await operation(async () => {
    const result = await api<Readiness>('training/datasets/' + current.value!.id + '/check', 'POST')
    if (alive) readiness.value = result
  })
}
async function exportBundle(recover = false) {
  if (!current.value) return
  await operation(async () => {
    exportId.value ||= crypto.randomUUID()
    const result = recover
      ? await api<TrainingExport>('training/exports/' + exportId.value)
      : await api<TrainingExport>('training/datasets/' + current.value!.id + '/exports', 'POST', {
          revision: current.value!.revision,
          request_id: exportId.value,
        })
    if (alive) {
      exported.value = result
      if (result.error) error.value = result.error
    }
  })
}
onMounted(() => {
  void refresh()
})
onUnmounted(() => {
  alive = false
  scope.dispose()
  emit('dirty', false)
})
</script>

<template>
  <div class="training-review">
    <p v-if="error" role="alert" class="notice warning">{{ error }}</p
    ><p v-if="message" role="status">{{ message }}</p>
    <div v-if="!current" class="empty-state"
      ><h2>尚未選擇審查資料</h2><p>匯入圖片清單與原圖目錄，或選擇已保存的資料集開始審查。</p
      ><button class="primary" @click="importOpen = true">匯入審查資料</button></div
    >
    <template v-if="current && edited">
      <section v-show="props.stage !== 1" class="training-review-content">
        <div class="training-progress"
          ><span v-if="reviewSummary.counts.train"
            >訓練候選標註：{{ reviewSummary.captionReady ?? '未知' }} /
            {{ reviewSummary.counts.train }} 通過</span
          ><span v-else>尚無訓練候選標註可審查</span
          ><span>待處理候選 {{ reviewSummary.pending ?? '未知' }} 張</span
          ><progress
            v-if="reviewSummary.counts.train && reviewSummary.captionReady !== null"
            :max="reviewSummary.counts.train"
            :value="reviewSummary.captionReady"
            aria-label="訓練候選標註審查進度"
          ></progress
        ></div>
        <div class="review-split-counts" role="group" aria-label="已保存版本的圖片分組"
          ><span>訓練候選 {{ reviewSummary.counts.train }} 張</span
          ><span>開發評估 {{ reviewSummary.counts.validation }} 張</span
          ><span>最終評估 {{ reviewSummary.counts.test }} 張</span
          ><span>排除 {{ reviewSummary.counts.excluded }} 張</span></div
        >
        <p class="review-export-status" role="status"
          >資料出口：{{
            dirty
              ? '有未保存變更，請先保存再檢查'
              : !readiness
                ? '尚未檢查'
                : readiness.data_ready
                  ? '檢查通過'
                  : '未通過檢查'
          }}</p
        >
        <p class="footnote"
          >統計依已保存修訂 {{ current.revision }}；{{
            dirty ? '目前編輯尚未保存，進度不會隨輸入更新。' : ''
          }}標註通過不代表來源、角色或原圖完整性通過，匯出仍依完整檢查。</p
        >
        <p v-if="!reviewSummary.counts.train" class="notice warning"
          >尚無訓練候選；請先核對資料分組，不將保留或排除圖當成已審查候選。</p
        >
        <p v-if="reviewSummary.pending" class="notice warning"
          >{{
            reviewSummary.pending
          }}
          張訓練候選仍有阻擋項目；請檢查描述、來源、角色及原圖完整性。</p
        >
        <p v-if="reviewSummary.otherIssues" class="notice warning"
          >另有
          {{ reviewSummary.otherIssues }}
          項保留圖或資料集層級阻擋；請至「匯出資料包」查看完整缺項。</p
        >
        <div class="training-review-grid">
          <TrainingReviewNavigator
            :key="current.id"
            :dataset-id="current.id"
            :images="edited.dataset.images"
            :report="readiness"
            :selected="selected"
            :busy="busy"
            :dirty="dirty"
            :revision="current.revision"
            :candidate-count="reviewSummary.counts.train"
            :pending-candidates="reviewSummary.pending"
            @select="selectImage"
          />
          <template v-if="image">
            <div class="panel training-source-image"
              ><p v-if="image.split === 'test'"
                >最終評估圖保留不預覽，避免在資料審查階段提前曝光。</p
              ><img
                v-else-if="!imageFailed"
                :key="current.id + current.revision + image.id"
                :src="`/api/training/datasets/${current.id}/images/${image.id}?revision=${current.revision}`"
                :alt="`審查原圖 ${image.id}`"
                @error="imageFailed = true"
              /><p v-else role="alert">原圖預覽無法載入；請重新檢查來源，不能以舊預覽認定完整性。</p
              ><details class="review-image-metadata"
                ><summary>來源圖片資訊</summary
                ><p class="footnote">{{ image.path }} · {{ image.width }} × {{ image.height }}</p
                ><p class="footnote">SHA256 {{ image.sha256 }}</p></details
              ></div
            >
            <fieldset
              class="panel training-image-form"
              id="training-image-editor"
              tabindex="-1"
              :disabled="busy || image.split === 'test'"
              ><legend>{{ image.id }} 的審查欄位</legend>
              <h2
                >圖片 {{ edited.dataset.images.findIndex((item) => item.id === selected) + 1 }} /
                {{ edited.dataset.images.length }}</h2
              >
              <label
                >圖片描述<textarea
                  aria-label="內容標註"
                  v-model="image.caption.content"
                  maxlength="4000"
                  rows="4"
                ></textarea>
              </label>
              <label
                >來源網址<input
                  v-model="image.provenance.source_url"
                  type="url"
                  maxlength="2048"
                  placeholder="填寫可追溯的來源"
              /></label>
              <label
                >圖片用途<select v-model="image.split" aria-label="圖片用途"
                  ><option value="train">訓練候選</option
                  ><option value="validation">開發評估</option
                  ><option value="test">最終評估</option
                  ><option value="excluded">排除</option></select
                ></label
              >
              <button class="primary" type="button" :disabled="busy || !dirty" @click="saveNext"
                >保存並看下一張</button
              >
              <details class="review-extra-fields"
                ><summary>標註、來源依據與角色詳細資料</summary>
                <label
                  >畫風觀察<textarea
                    v-model="image.caption.style_description"
                    maxlength="2000"
                  ></textarea>
                </label>
                <label
                  >標註狀態<select v-model="image.caption.status" aria-label="標註狀態"
                    ><option value="pending">待審查</option
                    ><option value="approved">已審查</option
                    ><option value="rejected">不採用</option></select
                  ></label
                >
                <label
                  >標註審查人<input v-model="image.caption.reviewed_by" maxlength="200"
                /></label>
                <label
                  >來源名稱<input v-model="image.provenance.attribution" maxlength="500"
                /></label>
                <label>作品識別<input v-model="image.provenance.work_id" maxlength="200" /></label>
                <label
                  >訓練用途紀錄<select
                    v-model="image.provenance.training_use"
                    aria-label="訓練用途紀錄"
                    ><option value="unreviewed">尚未核對</option
                    ><option value="recorded">已記錄依據</option
                    ><option value="exclude">不作訓練</option></select
                  ></label
                >
                <label
                  >來源用途依據<textarea
                    v-model="image.provenance.usage_note"
                    maxlength="4000"
                  ></textarea>
                </label>
                <label
                  >來源審查人<input v-model="image.provenance.reviewed_by" maxlength="200"
                /></label>
                <label
                  >角色身分<select v-model="image.identity" aria-label="角色身分"
                    ><option value="unreviewed">待確認</option
                    ><option value="target">目標角色</option
                    ><option value="other">其他角色</option
                    ><option value="mixed">多位角色</option></select
                  ></label
                >
                <label
                  >角色 ID（以逗號分隔）<input
                    :value="image.character_ids.join(',')"
                    @input="
                      image.character_ids = ($event.target as HTMLInputElement).value
                        .split(',')
                        .map((v) => v.trim())
                        .filter(Boolean)
                    "
                /></label>
                <label>原作群組<input v-model="image.group_id" /></label>
                <label>排除原因<input v-model="image.exclusion_reason" maxlength="2000" /></label>
                <p class="footnote"
                  >已知曝光：{{
                    image.exposure.join('、') || '未記錄'
                  }}。來源紀錄是審查者的記載，不是平台核發的使用授權。</p
                >
              </details>
            </fieldset>
          </template></div
        >
        <details class="panel training-version-management"
          ><summary>資料集版本與保存紀錄</summary>
          <div class="training-actions"
            ><label>新版本名稱<input v-model="nextVersion" :disabled="busy" maxlength="80" /></label
            ><button type="button" class="primary" :disabled="busy || !dirty" @click="save"
              >保存新版本</button
            ><button class="secondary" type="button" :disabled="busy" @click="load(current.id)"
              >重新載入已保存版本</button
            ><strong role="status">{{
              dirty ? '尚未保存變更' : '已保存 · 修訂 ' + current.revision
            }}</strong></div
          >
          <details
            ><summary>下載版本清單</summary
            ><ul
              ><li v-for="revision in current.revision" :key="revision"
                ><a
                  :href="`/api/training/datasets/${current.id}/manifest?revision=${revision}`"
                  download
                  >下載修訂 {{ revision }} JSON</a
                ></li
              ></ul
            ></details
          >
        </details>
      </section>
      <section v-show="props.stage === 1 || props.stage === undefined" class="training-export">
        <div class="panel training-export-check"
          ><div class="training-export-heading"
            ><h2>匯出前檢查</h2
            ><button class="secondary" type="button" :disabled="busy || dirty" @click="check"
              >重新檢查原圖與標註</button
            ></div
          ><p
            >{{
              dirty ? '目前有未保存標註，以下仍為已保存版本的檢查。' : '檢查對象為已保存版本。'
            }}
            資料出口通過不代表品質通過。</p
          >
          <div v-for="item in exportChecks" :key="item.label" class="training-check-row"
            ><strong>{{ item.label }}</strong
            ><span class="chip" :class="{ warning: !!item.issues.length }">{{
              !readiness
                ? '尚未檢查'
                : item.issues.length
                  ? item.issues.length + ' 項需處理'
                  : '通過'
            }}</span></div
          >
          <template v-if="readiness"
            ><p role="status">{{
              dirty
                ? '有未保存變更，保存後重新檢查才能匯出'
                : readiness.data_ready
                  ? '資料出口檢查通過'
                  : '仍有待審查項目'
            }}</p
            ><details class="training-export-details"
              ><summary>完整缺項與檢查版本</summary
              ><p
                >訓練候選 {{ readiness.counts.train }} · 開發評估
                {{ readiness.counts.validation }} · 最終評估 {{ readiness.counts.test }} · 排除
                {{ readiness.counts.excluded }}</p
              >
              <p class="footnote"
                >上次檢查：{{
                  readiness.checked_at || current.updated_at
                }}；來源變更後需重新檢查，匯出時也會重驗。</p
              >
              <ul
                ><li
                  v-for="(issue, index) in [...readiness.issues, ...readiness.warnings]"
                  :key="index"
                  >{{ issue.image_id ? issue.image_id + '：' : ''
                  }}{{ trainingIssue[issue.code] || issue.code }}</li
                ></ul
              ></details
            >
          </template></div
        >
        <div class="training-actions training-export-actions"
          ><button class="secondary" type="button" @click="emit('review')">回到待補項目</button
          ><button
            type="button"
            class="primary"
            :disabled="busy || dirty || !readiness?.data_ready || !!exportId"
            @click="exportBundle()"
            >匯出已審查訓練資料包</button
          ><button
            class="secondary"
            v-if="exportId"
            type="button"
            :disabled="busy"
            @click="exportBundle(true)"
            >查回原匯出結果</button
          ></div
        >
        <p v-if="exportId" class="footnote"
          >匯出 UUID：{{ exportId }}；回應不明時查回原 UUID，不會自動重做。</p
        ><p v-if="exported" role="status"
          >匯出狀態：{{ exported.status }}<br />{{ exported.path }}</p
        >
        <p class="footnote"
          >只複製 train 圖與
          caption，保留圖不進資料包。開始作者試訓前請逐張確認來源、角色及涵蓋範圍；最終品質比較前，另需未參與調參的不同原作評估圖。</p
        >
      </section>
    </template>
    <details
      class="panel training-dataset-management"
      :open="importOpen"
      @toggle="importOpen = ($event.target as HTMLDetailsElement).open"
      ><summary>資料集匯入、選擇與版本管理</summary>
      <h2>{{ props.stage === 1 ? '匯出資料包' : '訓練圖片與標註審查' }}</h2>
      <p>逐張確認內容、來源用途及角色身分；保存、檢查與匯出都不會開始訓練。</p>
      <p v-if="!available" role="status"
        >請使用 Windows 原生平台進行審查；容器無法存取原生圖片與訓練環境。</p
      >
      <template v-if="available">
        <form @submit.prevent="importing">
          <fieldset :disabled="busy || readingFile"
            ><legend>匯入 T02 清單</legend>
            <label
              >原圖來源目錄<input
                v-model="source"
                required
                placeholder="原圖的完整資料夾路徑"
                @input="importId = ''"
            /></label>
            <label
              >資料清單 JSON<input
                type="file"
                accept=".json,application/json"
                @change="file($event, 'manifest')"
            /></label>
            <label
              >前序 R02 study JSON（清單有 parent_study 時必填）<input
                type="file"
                accept=".json,application/json"
                @change="file($event, 'study')"
            /></label>
            <button type="submit" class="primary" :disabled="!manifest || !source || !!importId">{{
              readingFile ? '讀取檔案中…' : '匯入待審查清單'
            }}</button>
          </fieldset>
        </form>
        <div class="training-actions"
          ><button class="secondary" type="button" :disabled="busy" @click="refresh"
            >更新資料集清單</button
          ><button
            class="secondary"
            v-if="importId"
            type="button"
            :disabled="busy"
            @click="load(importId)"
            >查回原匯入資料集</button
          ><span>匯入 UUID：{{ importId || '尚未匯入' }}</span></div
        >
        <p v-if="!list.length">尚未登記資料集。先使用 T02 工具建立清單，再選擇 JSON 與原圖目錄。</p>
        <ul class="dataset-list"
          ><li v-for="item in list" :key="item.id"
            ><button
              class="secondary"
              type="button"
              :disabled="busy"
              :aria-pressed="current?.id === item.id"
              :data-dataset-id="item.id"
              @click="load(item.id)"
              >{{ item.dataset_id }} · {{ item.kind === 'style' ? '畫風' : '角色' }} ·
              {{ item.version }} · 修訂 {{ item.revision }}</button
            ></li
          ></ul
        >
      </template>
    </details>
  </div>
</template>

<style scoped>
.training-review {
  display: grid;
  gap: 20px;
  min-width: 0;
}
.training-review p,
.training-review li {
  overflow-wrap: anywhere;
}
.training-review fieldset {
  border: 1px solid var(--line, #36413b);
  border-radius: 8px;
  padding: 16px;
  min-width: 0;
}
.training-review label {
  display: grid;
  gap: 7px;
  margin: 12px 0;
  font-size: 12px;
}
.training-review input,
.training-review textarea,
.training-review select {
  width: 100%;
  box-sizing: border-box;
  min-width: 0;
}
.training-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin: 16px 0;
}
.review-split-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  font-size: 12px;
  color: var(--ink3);
  margin-bottom: 10px;
}
.review-export-status {
  font-weight: 600;
  margin-bottom: 4px;
}
.training-actions span {
  overflow-wrap: anywhere;
  font-size: 11px;
}
.dataset-list {
  padding-left: 0;
  list-style: none;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.image-choices {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 14px 0;
}
.image-review {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
.image-review img {
  max-width: 100%;
  max-height: 640px;
  object-fit: contain;
}
.training-review button[aria-pressed='true'] {
  outline: 2px solid #a7c296;
}
.training-review .footnote {
  overflow-wrap: anywhere;
}
@media (max-width: 850px) {
  .image-review {
    grid-template-columns: 1fr;
  }
}
</style>
