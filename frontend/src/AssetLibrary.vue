<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'
import UiIcon from './UiIcon.vue'
const emit = defineEmits<{ use: [id: string, purpose: string]; dirty: [value: boolean] }>()
const uploadOpen = ref(false)
type Purpose = 'unspecified' | 'style' | 'character' | 'composition'
type Asset = {
  id: string
  title: string
  width: number
  height: number
  size: number
  archived: boolean
  purpose: Purpose
  revision: number
  preprocessing: { version: number; library_version: string } | null
}
type Workflow = {
  id: string
  name: string
  implemented: boolean
  input_requirement: string
  control: string
}
const purposes: Record<Purpose, string> = {
  unspecified: '未指定',
  style: '畫風',
  character: '角色',
  composition: '結構',
}
const purpose = ref<Purpose>('unspecified'),
  filter = ref(''),
  workflows = ref<Workflow[]>([])
const items = ref<Asset[]>([]),
  busy = ref(false),
  error = ref(''),
  message = ref(''),
  archived = ref(false),
  search = ref('')
const editing = ref<string | null>(null),
  title = ref('')
const dialog = ref<HTMLDialogElement | null>(null),
  selected = ref<Asset | null>(null),
  mutating = ref(false)
let opener: HTMLElement | null = null
const dirty = computed(() => {
  const item =
    selected.value?.id === editing.value
      ? selected.value
      : items.value.find((item) => item.id === editing.value)
  return !!item && (title.value !== item.title || purpose.value !== item.purpose)
})
watch([dirty, mutating], () => emit('dirty', dirty.value || mutating.value), { flush: 'sync' })
function editAsset(item: Asset) {
  editing.value = item.id
  title.value = item.title
  purpose.value = item.purpose
}
async function openAsset(item: Asset, event: Event) {
  if (editing.value && dirty.value && !window.confirm('素材資料尚未保存，確定放棄編輯？')) return
  editing.value = null
  selected.value = item
  opener = event.currentTarget as HTMLElement
  error.value = ''
  await nextTick()
  dialog.value?.showModal()
}
function closeAsset() {
  if (mutating.value || (dirty.value && !window.confirm('素材資料尚未保存，確定放棄編輯並關閉？')))
    return
  const id = selected.value?.id
  editing.value = null
  dialog.value?.close()
  selected.value = null
  void nextTick(() => {
    const current = document.querySelector<HTMLButtonElement>('[data-asset-cover="' + id + '"]')
    if (current) current.focus()
    else if (opener?.isConnected) opener.focus()
  })
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (dirty.value || mutating.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
const hasFilters = computed(() => !!search.value.trim() || !!filter.value)
function clearFilters() {
  if (editing.value || mutating.value) return
  search.value = ''
  filter.value = ''
}
const visible = computed(() => items.value)
const total = ref(0),
  next = ref<string | null>(null),
  previous = ref<string | null>(null)
const reads = createRequestScope()
let timer: ReturnType<typeof setTimeout>
function api<T>(path = '', options?: RequestInit): Promise<T> {
  return apiJson<T>('assets' + path, options)
}
async function load(cursor: string | null = null) {
  if (editing.value) return
  const read = reads.begin()
  busy.value = true
  error.value = ''
  try {
    const query = new URLSearchParams({
      limit: '40',
      q: search.value,
      scope: archived.value ? 'archived' : 'active',
      purpose: filter.value,
    })
    if (cursor) query.set('cursor', cursor)
    const [page, definitions] = await Promise.all([
      apiJson<{
        items: Asset[]
        total: number
        next_cursor: string | null
        previous_cursor: string | null
      }>('library/assets?' + query, { signal: read.signal }),
      apiJson<Workflow[]>('reference-workflows', { signal: read.signal }),
    ])
    if (!read.isCurrent()) return
    workflows.value = definitions
    items.value = page.items
    total.value = page.total
    next.value = page.next_cursor
    previous.value = page.previous_cursor
  } catch (e) {
    if (read.isCurrent()) error.value = e instanceof Error ? e.message : '無法讀取素材'
  } finally {
    if (read.isCurrent()) busy.value = false
  }
}
watch([search, archived, filter], () => {
  clearTimeout(timer)
  reads.cancel()
  busy.value = true
  timer = setTimeout(() => void load(), 250)
})
onBeforeUnmount(() => {
  clearTimeout(timer)
  reads.dispose()
  window.removeEventListener('beforeunload', beforeUnload)
  emit('dirty', false)
})
async function upload(event: Event) {
  const input = event.target as HTMLInputElement,
    file = input.files?.[0]
  if (!file) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    if (file.size > 20 * 1024 * 1024) throw new Error('圖片不可超過 20 MiB')
    const item = await api<Asset>('?filename=' + encodeURIComponent(file.name), {
      method: 'POST',
      body: file,
      headers: { 'Content-Type': 'application/octet-stream' },
    })
    archived.value = false
    search.value = ''
    filter.value = ''
    await load()
    message.value = '參考素材已保存，可以回到創作工作台選取。'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '上傳失敗'
  } finally {
    busy.value = false
    input.value = ''
  }
}
async function update(item: Asset, archive = item.archived) {
  if (mutating.value) return
  mutating.value = true
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await api<Asset>('/' + item.id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: editing.value === item.id ? title.value : item.title,
        purpose: editing.value === item.id ? purpose.value : item.purpose,
        archived: archive,
        revision: item.revision,
      }),
    })
    items.value = items.value.map((value) => (value.id === result.id ? result : value))
    if (selected.value?.id === result.id) selected.value = result
    editing.value = null
    await load()
    message.value = '素材資料已更新。'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '更新失敗'
  } finally {
    busy.value = false
    mutating.value = false
  }
}
onMounted(() => {
  window.addEventListener('beforeunload', beforeUnload)
  void load()
})
</script>

<template>
  <p v-if="busy" class="footnote" role="status">正在處理素材，請稍候…</p>
  <div class="page-intro"
    ><p>先指定用途，再帶入相容的創作類型。素材不會自動用於訓練。</p
    ><button class="primary" @click="uploadOpen = !uploadOpen">上傳素材</button></div
  ><article v-show="uploadOpen" class="panel upload-panel"
    ><span class="chip">REFERENCE ASSETS</span><h2>收集創作的起點</h2
    ><p>標記參考用途，再於創作工作台選擇相容流程。用途標籤僅供整理，不會自動套用畫風或鎖定角色。</p
    ><label class="upload-label"
      >選擇圖片<input
        type="file"
        aria-describedby="asset-upload-help"
        accept="image/png,image/jpeg,image/webp"
        :disabled="busy"
        @change="upload" /></label
    ><p id="asset-upload-help" class="footnote"
      >支援單張 PNG、JPEG、WebP，最多 20 MiB、1600
      萬像素。保留原始檔於你的電腦；平台儲存經方向校正、移除中繼資料的 PNG 副本。</p
    ></article
  >
  <p v-if="error" class="notice warning" role="alert">{{ error }}</p
  ><p v-if="message" class="notice" role="status">{{ message }}</p>
  <div class="asset-browser-tools">
    <div class="purpose-tabs" role="group" aria-label="素材用途">
      <button :aria-pressed="filter === ''" :disabled="editing !== null" @click="filter = ''"
        >全部</button
      >
      <button
        v-for="value in ['style', 'composition', 'character'] as const"
        :key="value"
        :aria-pressed="filter === value"
        :disabled="editing !== null"
        @click="filter = value"
        >{{ purposes[value] }}</button
      >
    </div>
    <label class="asset-search"
      ><span class="sr-only">搜尋素材</span
      ><input
        v-model="search"
        :disabled="editing !== null"
        maxlength="200"
        type="search"
        placeholder="搜尋素材名稱…"
    /></label>
  </div>
  <article v-if="!visible.length" class="panel placeholder"
    ><h2>{{
      busy
        ? '處理中…'
        : hasFilters
          ? '沒有符合的素材'
          : archived
            ? '尚無封存素材'
            : '收集你的第一張參考圖'
    }}</h2
    ><p>{{
      hasFilters
        ? '調整搜尋名稱或用途，或清除目前條件。'
        : archived
          ? '封存的素材會出現在這裡，可隨時還原。'
          : '上傳圖片並指定用途，不會自動用於訓練。'
    }}</p
    ><button
      v-if="hasFilters"
      class="secondary"
      :disabled="busy || editing !== null"
      @click="clearFilters"
      >清除搜尋與用途篩選</button
    ><p v-if="hasFilters" class="footnote">保留目前的{{ archived ? '已封存' : '使用中' }}範圍。</p
    ><button v-else-if="!archived && !busy" class="primary" @click="uploadOpen = true"
      >上傳素材</button
    ></article
  >
  <div class="asset-grid"
    ><article v-for="item in visible" :key="item.id" class="panel asset-card"
      ><button
        class="asset-cover"
        :data-asset-cover="item.id"
        :aria-label="'查看素材 ' + item.title"
        :disabled="busy || editing !== null"
        @click="openAsset(item, $event)"
        ><img :src="'/api/assets/' + item.id + '/image'" :alt="item.title" loading="lazy" /></button
      ><template v-if="editing === item.id"
        ><label>素材名稱<input v-model="title" maxlength="100" :disabled="busy" /></label
        ><label
          >素材用途<select v-model="purpose" :disabled="busy"
            ><option v-for="(label, value) in purposes" :key="value" :value="value">{{
              label
            }}</option></select
          ></label
        ><div class="asset-actions"
          ><button class="primary" :disabled="busy || !title.trim()" @click="update(item)"
            >保存素材資料</button
          ><button class="secondary" :disabled="busy" @click="editing = null">取消</button></div
        ></template
      ><template v-else
        ><div class="asset-card-heading"
          ><h2 :title="item.title">{{ item.title }}</h2>
          <span class="asset-purpose" :class="item.purpose">{{ purposes[item.purpose] }}</span></div
        ><p>
          {{ item.width }} × {{ item.height }} · {{ (item.size / 1024 / 1024).toFixed(2) }} MiB</p
        ><div class="asset-actions"
          ><button
            class="secondary"
            :disabled="busy || editing !== null || item.archived"
            @click="emit('use', item.id, item.purpose)"
            >用於創作</button
          ></div
        ><details class="asset-management"
          ><summary>素材管理</summary
          ><p class="footnote">{{
            item.preprocessing
              ? '正規化 v' +
                item.preprocessing.version +
                ' · Pillow ' +
                item.preprocessing.library_version
              : '前處理版本未知'
          }}</p>
          <div class="asset-actions"
            ><button
              class="secondary"
              :disabled="busy || editing !== null"
              :aria-label="'編輯素材 ' + item.title"
              @click="
                () => {
                  editing = item.id
                  title = item.title
                  purpose = item.purpose
                }
              "
              >編輯資料</button
            ><button
              class="secondary"
              :disabled="busy || editing !== null"
              @click="update(item, !item.archived)"
              >{{ item.archived ? '還原素材' : '封存素材' }}</button
            ></div
          ></details
        >
      </template></article
    ></div
  >
  <div class="library-footer"
    ><span role="status" class="footnote"
      >{{ archived ? '已封存' : '使用中' }}素材：{{ total }} 張符合，本頁
      {{ visible.length }} 張</span
    >
    <div v-if="previous || next" role="group" aria-label="素材分頁"
      ><button
        class="secondary"
        :disabled="busy || editing !== null || !previous"
        @click="load(previous)"
        >上一頁</button
      ><button class="secondary" :disabled="busy || editing !== null || !next" @click="load(next)"
        >下一頁</button
      ></div
    >
  </div>
  <details class="panel library-management"
    ><summary>素材篩選、整理與流程能力</summary>
    <div class="asset-toolbar"
      ><label
        >參考用途<select v-model="filter" :disabled="editing !== null"
          ><option value="">全部用途</option
          ><option v-for="(label, value) in purposes" :key="value" :value="value">{{
            label
          }}</option></select
        ></label
      ><button
        class="secondary"
        :disabled="busy || editing !== null"
        @click="archived = !archived"
        >{{ archived ? '查看使用中素材' : '查看已封存' }}</button
      ><button class="secondary" :disabled="busy || editing !== null" @click="load()"
        >重新整理</button
      ></div
    >
    <details class="panel"
      ><summary>參考流程的輸入需求與支援能力</summary
      ><article v-for="workflow in workflows" :key="workflow.id"
        ><h3
          >{{ workflow.name }} ·
          {{ workflow.implemented ? '已實作，提交仍需引擎驗證' : '尚未整合' }}</h3
        ><p>{{ workflow.input_requirement }} {{ workflow.control }}</p></article
      ></details
    >
  </details>
  <dialog
    ref="dialog"
    class="asset-dialog"
    aria-labelledby="asset-detail-title"
    @cancel.prevent="closeAsset"
  >
    <template v-if="selected">
      <div class="asset-detail-heading"
        ><h2 id="asset-detail-title">{{ selected.title }}</h2
        ><div class="asset-detail-tools"
          ><button
            class="secondary"
            :disabled="busy || editing !== null"
            @click="update(selected, !selected.archived)"
            >{{ selected.archived ? '還原素材' : '封存素材' }}</button
          ><button class="secondary" :disabled="mutating" autofocus @click="closeAsset"
            >關閉</button
          ></div
        ></div
      >
      <div class="asset-detail-grid"
        ><div class="asset-detail-image"
          ><div class="asset-detail-canvas"
            ><img :src="'/api/assets/' + selected.id + '/image'" :alt="selected.title" /></div
          ><div class="asset-image-footer"
            ><span>保留原始比例</span
            ><a
              class="asset-original-link"
              :href="'/api/assets/' + selected.id + '/image'"
              target="_blank"
              rel="noopener"
              title="另開分頁檢視原圖"
              >另開原圖<UiIcon name="external" :size="16" /></a></div
        ></div>
        <div class="asset-detail-info"
          ><div class="asset-detail-labels"
            ><span class="asset-purpose" :class="selected.purpose">{{
              purposes[selected.purpose]
            }}</span
            ><span class="asset-state" :class="{ archived: selected.archived }"
              ><span aria-hidden="true"></span>{{ selected.archived ? '已封存' : '使用中' }}</span
            ></div
          ><dl class="asset-detail-facts"
            ><div class="asset-dimensions"
              ><dt>尺寸</dt
              ><dd
                >{{ selected.width }} <span>×</span> {{ selected.height }} <small>px</small></dd
              ></div
            ><div
              ><dt>像素量</dt
              ><dd
                >{{ ((selected.width * selected.height) / 1e6).toFixed(2) }} <small>MP</small></dd
              ></div
            ><div
              ><dt>檔案大小</dt
              ><dd>{{ (selected.size / 1024 / 1024).toFixed(2) }} <small>MiB</small></dd></div
            ></dl
          ><details class="asset-technical-details"
            ><summary>前處理資訊</summary
            ><dl
              ><dt>圖片正規化</dt
              ><dd>{{
                selected.preprocessing
                  ? '正規化 v' +
                    selected.preprocessing.version +
                    ' · Pillow ' +
                    selected.preprocessing.library_version
                  : '版本未知'
              }}</dd></dl
            ></details
          >
          <p v-if="error" class="notice warning" role="alert">{{ error }}</p
          ><p v-if="message" role="status">{{ message }}</p>
          <form
            v-if="editing === selected.id"
            class="asset-detail-edit"
            @submit.prevent="update(selected)"
            ><h3>編輯素材資料</h3
            ><label
              >素材名稱<input
                v-model="title"
                maxlength="100"
                required
                :disabled="mutating" /></label
            ><label
              >素材用途<select v-model="purpose" :disabled="mutating"
                ><option v-for="(label, value) in purposes" :key="value" :value="value">{{
                  label
                }}</option></select
              ></label
            ><div class="asset-actions"
              ><button class="primary" :disabled="mutating || !title.trim()">保存素材資料</button
              ><button type="button" class="secondary" :disabled="mutating" @click="editing = null"
                >取消編輯</button
              ></div
            ></form
          >
          <div v-else class="asset-detail-create"
            ><p v-if="selected.archived" class="footnote">素材已封存，還原後即可帶入創作。</p
            ><div class="asset-actions"
              ><button
                class="primary asset-action-create"
                :disabled="busy || selected.archived"
                @click="emit('use', selected.id, selected.purpose)"
                ><UiIcon name="studio" :size="18" />用於創作</button
              ><button
                class="secondary asset-action-edit"
                :disabled="busy"
                @click="editAsset(selected)"
                ><UiIcon name="edit" :size="18" />編輯素材資料</button
              ></div
            ></div
          >
          <p class="footnote"
            >用途標籤只用於整理。帶入創作後仍需確認模型與流程，不會自動生成或加入訓練。</p
          >
        </div></div
      >
    </template>
  </dialog>
</template>

<style scoped>
.upload-panel {
  background: linear-gradient(120deg, #253b2d, #191d20);
}
.upload-label {
  display: grid;
  gap: 12px;
  font-size: 12px;
  max-width: 420px;
}
.upload-label input {
  font-size: 12px;
}
.asset-toolbar {
  display: flex;
  align-items: end;
  gap: 12px;
  flex-wrap: wrap;
}
.asset-toolbar label {
  flex: 1;
  display: grid;
  gap: 8px;
  font-size: 12px;
}
.asset-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}
.asset-card {
  margin-bottom: 0;
  min-width: 0;
}
.asset-card img {
  width: 100%;
  height: 200px;
  object-fit: contain;
  background: #101617;
  border-radius: 8px;
}
.asset-card h2 {
  overflow-wrap: anywhere;
  font-size: 14px;
  margin-top: 20px;
}
.asset-card p {
  font-size: 11px;
}
.asset-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 15px;
}
.asset-card label {
  display: grid;
  gap: 8px;
  font-size: 12px;
  margin-top: 15px;
}
@media (max-width: 1100px) {
  .asset-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 700px) {
  .asset-grid {
    grid-template-columns: 1fr;
  }
  .asset-toolbar label {
    flex-basis: 100%;
  }
}
</style>
