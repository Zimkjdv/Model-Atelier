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
} from './trainingTypes'

const emit = defineEmits<{ dirty: [value: boolean] }>()
const list = ref<DatasetSummary[]>([]),
  current = ref<DatasetReview | null>(null),
  edited = ref<DatasetReview | null>(null)
const available = ref(true),
  busy = ref(false),
  readingFile = ref(false),
  error = ref(''),
  message = ref('')
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
    <article class="panel">
      <h2>訓練圖片與標註審查</h2>
      <p>逐張確認內容、來源用途及角色身分；保存、檢查與匯出都不會開始訓練。</p>
      <p v-if="!available" role="status"
        >請使用 Windows 原生平台進行審查；容器無法存取原生圖片與訓練環境。</p
      >
      <p v-if="error" role="alert" class="notice warning">{{ error }}</p
      ><p role="status">{{ message }}</p>
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
              @click="load(item.id)"
              >{{ item.dataset_id }} · {{ item.kind === 'style' ? '畫風' : '角色' }} ·
              {{ item.version }} · 修訂 {{ item.revision }}</button
            ></li
          ></ul
        >
      </template>
    </article>
    <template v-if="current && edited">
      <article class="panel">
        <h2>{{ edited.dataset.dataset_id }} · 圖片審查</h2>
        <p
          >{{ edited.dataset.kind === 'style' ? '畫風' : '角色' }} · 目標
          {{ edited.dataset.subject_id }} · trigger {{ edited.dataset.trigger }}</p
        >
        <p class="footnote"
          >原圖只讀。保留／排除圖不可改成訓練來源；既有曝光不可移除。同作者不等於同角色。</p
        >
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
        <TrainingReviewNavigator
          :key="current.id"
          :images="edited.dataset.images"
          :report="readiness"
          :selected="selected"
          :busy="busy"
          :dirty="dirty"
          :revision="current.revision"
          @select="selectImage"
        />
        <div v-if="image" class="image-review">
          <div
            ><p v-if="image.split === 'test'">最終評估圖保留不預覽，避免在資料審查階段提前曝光。</p
            ><img
              v-else-if="!imageFailed"
              :key="current.id + current.revision + image.id"
              :src="`/api/training/datasets/${current.id}/images/${image.id}?revision=${current.revision}`"
              :alt="`審查原圖 ${image.id}`"
              @error="imageFailed = true"
            /><p v-else role="alert">原圖預覽無法載入；請重新檢查來源，不能以舊預覽認定完整性。</p
            ><p class="footnote">{{ image.path }} · {{ image.width }} × {{ image.height }}</p
            ><p class="footnote">SHA256 {{ image.sha256 }}</p></div
          >
          <fieldset
            id="training-image-editor"
            tabindex="-1"
            :disabled="busy || image.split === 'test'"
            ><legend>{{ image.id }} 的審查欄位</legend>
            <label>內容標註<input v-model="image.caption.content" maxlength="4000" /></label>
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
            <label>標註審查人<input v-model="image.caption.reviewed_by" maxlength="200" /></label>
            <label>來源名稱<input v-model="image.provenance.attribution" maxlength="500" /></label>
            <label>作品識別<input v-model="image.provenance.work_id" maxlength="200" /></label>
            <label
              >來源網址<input v-model="image.provenance.source_url" type="url" maxlength="2048"
            /></label>
            <label
              >訓練用途紀錄<select v-model="image.provenance.training_use" aria-label="訓練用途紀錄"
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
            <label
              >圖片用途<select v-model="image.split" aria-label="圖片用途"
                ><option value="train">訓練候選</option
                ><option value="validation">開發評估</option
                ><option value="test">最終評估</option
                ><option value="excluded">排除</option></select
              ></label
            >
            <label>排除原因<input v-model="image.exclusion_reason" maxlength="2000" /></label>
            <p class="footnote"
              >已知曝光：{{
                image.exposure.join('、') || '未記錄'
              }}。來源紀錄是審查者的記載，不是平台核發的使用授權。</p
            >
          </fieldset>
        </div>
      </article>
      <article class="panel">
        <h2>資料出口檢查</h2
        ><p
          >{{
            dirty ? '目前有未保存標註，以下仍為已保存版本的檢查。' : '檢查對象為已保存版本。'
          }}
          資料出口通過不代表品質通過。</p
        >
        <button class="secondary" type="button" :disabled="busy || dirty" @click="check"
          >重新檢查原圖與標註</button
        >
        <template v-if="readiness"
          ><p
            >訓練候選 {{ readiness.counts.train }} · 開發評估 {{ readiness.counts.validation }} ·
            最終評估 {{ readiness.counts.test }} · 排除 {{ readiness.counts.excluded }}</p
          ><p role="status">{{ readiness.data_ready ? '資料出口檢查通過' : '仍有待審查項目' }}</p>
          <p class="footnote"
            >上次檢查：{{
              readiness.checked_at || current.updated_at
            }}；來源變更後需重新檢查，匯出時也會重驗。</p
          >
          <p class="footnote">完整缺項與圖片定位請見上方「圖片與缺項導覽」。</p>
        </template>
        <div class="training-actions"
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
      </article>
    </template>
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
