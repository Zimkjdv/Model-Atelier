<script setup lang="ts">
import SizePresets from './SizePresets.vue'
import StudioPreview from './StudioPreview.vue'
import {
  computed,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue'
import { apiJson as api } from './apiClient'
import { createRequestScope } from './requestScope'
import { useUnsavedChanges } from './unsavedChanges'
import UnsavedChangesNotice from './UnsavedChangesNotice.vue'
import AssetChoices from './AssetChoices.vue'
import GenerationPanel from './GenerationPanel.vue'
import ReferenceComponents from './ReferenceComponents.vue'
import ReferenceComponentsSnapshot from './ReferenceComponentsSnapshot.vue'
import ReferenceSnapshot from './ReferenceSnapshot.vue'
import RuntimeSnapshot from './RuntimeSnapshot.vue'
import {
  copyReference,
  newReference,
  referenceProblem,
  registeredReferenceProblem,
  referenceRoles,
  type ReferenceCatalog,
  type ReferenceComponent,
  type ReferenceForm,
} from './adapterSettings'
import { validateProfile, type ModelProfile } from './modelProfiles'
import type { ReferenceAsset, ReferenceSnapshot as ReferenceMetadata } from './referenceSettings'
import type { RuntimeMetadata } from './runtimeMetadata'

const props = defineProps<{
  assetRequest?: { id: string; purpose: string; token: number } | null
  restoreRequest?: { artworkId: string; token: number } | null
}>()
const emit = defineEmits<{ models: []; assets: []; gallery: [jobId: string] }>()
type Catalog = {
  engine_url: string
  synced_at: string | null
  sync_error: string | null
  models: { name: string; listed: boolean; version?: string; architecture?: string }[]
}
type Capabilities = {
  engine_url: string
  engine_matches: boolean
  available: boolean
  stale: boolean
  sampler_names: string[]
  schedulers: string[]
}
type Restoration = {
  settings: ReferenceForm
  warnings: string[]
  reference_metadata?: ReferenceMetadata[] | null
  component_metadata?: ReferenceComponent[] | null
  runtime_metadata?: RuntimeMetadata | null
  job_id?: string
  artwork_id?: string
}
const form = reactive(newReference()),
  catalog = ref<Catalog | null>(null),
  components = ref<ReferenceCatalog | null>(null),
  capabilities = ref<Capabilities | null>(null),
  profile = ref<ModelProfile | null>(null),
  assets = ref<ReferenceAsset[]>([])
const busy = ref(false),
  metadataBusy = ref(false),
  generationBusy = ref(false),
  generationPending = ref(false),
  error = ref(''),
  message = ref('')
const origin = ref<Restoration | null>(null),
  pendingRestore = ref<Restoration | null>(null)
const baseline = ref(JSON.stringify(form)),
  dirty = computed(() => JSON.stringify(form) !== baseline.value)
useUnsavedChanges(dirty)
const locked = computed(
  () =>
    busy.value ||
    metadataBusy.value ||
    generationBusy.value ||
    generationPending.value ||
    !!pendingRestore.value,
)
const source = computed(() => assets.value.find((a) => a.id === form.image_asset_id))
const loads = createRequestScope(),
  restores = createRequestScope()
let mounted = false,
  alive = true

async function load(sync = false) {
  const request = loads.begin(),
    originalEngine = form.engine_url,
    name = form.checkpoint
  busy.value = true
  error.value = ''
  catalog.value = null
  components.value = null
  profile.value = null
  capabilities.value = null
  try {
    const values = await Promise.all([
      api<Catalog>('models', { signal: request.signal }),
      api<ReferenceCatalog>('reference-components', { signal: request.signal }),
      api<Capabilities>('engine/capabilities' + (sync ? '/sync' : ''), {
        method: sync ? 'POST' : 'GET',
        signal: request.signal,
      }),
    ])
    if (!alive || !request.isCurrent()) return
    catalog.value = values[0]
    components.value = values[1]
    capabilities.value = values[2]
    if (!form.engine_url) {
      form.engine_url = values[0].engine_url
      baseline.value = JSON.stringify(form)
    }
    if (originalEngine && form.engine_url !== originalEngine) return
    if (name && form.checkpoint === name) {
      const value = validateProfile(
        await api<ModelProfile>(
          'models/profile?' + new URLSearchParams({ engine_url: form.engine_url, name }),
          { signal: request.signal },
        ),
      )
      if (
        request.isCurrent() &&
        alive &&
        form.engine_url === value.engine_url &&
        form.checkpoint === value.name
      )
        profile.value = value
    }
  } catch (cause) {
    if (request.isCurrent() && !request.signal.aborted)
      error.value = cause instanceof Error ? cause.message : '讀取失敗'
  } finally {
    if (request.isCurrent()) busy.value = false
  }
}
watch(
  () => [form.engine_url, form.checkpoint],
  () => {
    profile.value = null
    if (mounted) void load()
  },
  { flush: 'sync' },
)
const block = computed(() => {
  if (busy.value || metadataBusy.value) return '正在更新原引擎或元件登記。'
  const input = referenceProblem(form, source.value)
  if (input) return input
  if (
    !form.checkpoint ||
    catalog.value?.engine_url !== form.engine_url ||
    !catalog.value.synced_at ||
    catalog.value.sync_error ||
    !catalog.value.models.some((m) => m.name === form.checkpoint && m.listed)
  )
    return '請在原引擎模型庫成功同步並選擇 SDXL checkpoint。'
  if (
    profile.value?.engine_url !== form.engine_url ||
    profile.value.name !== form.checkpoint ||
    profile.value.architecture !== 'sdxl'
  )
    return '需明確登記 SDXL 架構，請確認模型庫。'
  const component = registeredReferenceProblem(components.value, form)
  if (component) return component
  const c = capabilities.value
  if (c?.engine_url !== form.engine_url || !c.engine_matches || !c.available || c.stale)
    return '請更新原引擎取樣選項；歷史資料不能代替即時確認。'
  if (!c.sampler_names.includes(form.sampler_name) || !c.schedulers.includes(form.scheduler))
    return '取樣器或 scheduler 不在原引擎清單，請手動調整。'
  return ''
})
function chooseSource(id: string | null) {
  if (locked.value) return
  form.image_asset_id = id
  form.reference_ids = id ? [id] : []
  origin.value = null
}
function apply(value: Restoration) {
  if (generationBusy.value || generationPending.value || metadataBusy.value) return
  const copied = copyReference(value.settings)
  restores.cancel()
  Object.assign(form, copied)
  origin.value = value
  pendingRestore.value = null
  baseline.value = ''
  message.value = '已載入完整原參考圖、模式、元件與參數；請確認後手動建立新任務。'
  void load()
}
async function restore(kind: 'jobs' | 'artworks', id: string, token?: number) {
  if (!alive || generationBusy.value || generationPending.value || metadataBusy.value) {
    error.value = '請先完成或恢復目前提交／登記，再載入設定。'
    return
  }
  const request = restores.begin()
  error.value = ''
  try {
    const value = await api<Restoration>(kind + '/' + id + '/creation-settings', {
      signal: request.signal,
    })
    if (
      !alive ||
      !request.isCurrent() ||
      (token !== undefined && props.restoreRequest?.token !== token)
    )
      return
    if ((kind === 'jobs' ? value.job_id : value.artwork_id) !== id)
      throw new Error('回傳的來源 ID 不同，未載入。')
    copyReference(value.settings)
    if (dirty.value) pendingRestore.value = value
    else apply(value)
  } catch (cause) {
    if (request.isCurrent() && !request.signal.aborted)
      error.value = cause instanceof Error ? cause.message : '載入失敗'
  }
}
watch(
  () => props.restoreRequest,
  (value) => {
    if (value) void restore('artworks', value.artworkId, value.token)
  },
  { immediate: true },
)
onMounted(async () => {
  await load()
  mounted = true
})
onActivated(() => {
  if (mounted) void load()
})
onDeactivated(() => {
  loads.cancel()
  restores.cancel()
  busy.value = false
})
onBeforeUnmount(() => {
  alive = false
  loads.dispose()
  restores.dispose()
})

let appliedAssetToken = 0
watch(
  [() => props.assetRequest, () => assets.value, () => locked.value],
  ([request]) => {
    if (
      !request ||
      locked.value ||
      request.token === appliedAssetToken ||
      !assets.value.some((item) => item.id === request.id)
    )
      return
    appliedAssetToken = request.token
    if (dirty.value && !window.confirm('帶入素材會更換目前來源圖片，其他參數保留，確定套用？'))
      return
    chooseSource(request.id)
    if (request.purpose === 'style' || request.purpose === 'character')
      form.reference_mode = request.purpose
  },
  { flush: 'post' },
)
</script>
<template>
  <section aria-label="畫風角色參考工作台">
    <div class="studio-workbench"
      ><div class="studio-settings"
        ><UnsavedChangesNotice :dirty="dirty" page-only />
        <p v-if="error" role="alert" class="notice warning">{{ error }}</p>
        <p v-if="message" role="status" class="notice">{{ message }}</p>
        <div v-if="pendingRestore" class="notice warning"
          ><p>載入將取代目前未提交表單。</p
          ><button class="secondary" @click="pendingRestore = null">繼續編輯</button
          ><button
            class="secondary"
            :disabled="generationBusy || generationPending || metadataBusy"
            @click="apply(pendingRestore)"
            >捨棄變更並載入</button
          ></div
        ><form class="panel editor" @submit.prevent
          ><fieldset :disabled="locked">
            <label for="reference-source">參考素材</label
            ><select
              id="reference-source"
              :value="form.image_asset_id || ''"
              @change="chooseSource(($event.target as HTMLSelectElement).value || null)"
              ><option value="">選擇一張參考圖</option
              ><option v-if="form.image_asset_id && !source" :value="form.image_asset_id"
                >原素材不存在（{{ form.image_asset_id }}）</option
              ><option
                v-for="a in assets.filter((a) => !a.archived || a.id === form.image_asset_id)"
                :key="a.id"
                :value="a.id"
                :disabled="a.archived"
                >{{ a.title }} · {{ a.width }} × {{ a.height
                }}{{ a.archived ? '（已封存）' : '' }}</option
              ></select
            >
            <label for="reference-prompt">提示詞</label
            ><textarea id="reference-prompt" v-model="form.prompt" rows="5" maxlength="20000" />
            <label for="reference-checkpoint">SDXL Checkpoint</label
            ><select id="reference-checkpoint" v-model="form.checkpoint"
              ><option value="">選擇模型</option
              ><option
                v-if="form.checkpoint && !catalog?.models.some((m) => m.name === form.checkpoint)"
                :value="form.checkpoint"
                >{{ form.checkpoint }}（清單未確認）</option
              ><option
                v-for="m in catalog?.models"
                :key="m.name"
                :value="m.name"
                :disabled="!m.listed"
                >{{ m.name }}{{ m.listed ? '' : '（已不在清單）' }}</option
              ></select
            >
            <SizePresets
              :family="profile?.architecture"
              :width="form.width"
              :height="form.height"
              @select="
                (w, h) => {
                  form.width = w
                  form.height = h
                }
              "
            /><details class="studio-advanced"
              ><summary>進階設定、草稿名稱與模型能力</summary><h2>參考圖與生成設定</h2>
              <label for="reference-title">名稱</label
              ><input id="reference-title" v-model="form.title" maxlength="100" required />

              <label for="reference-mode">參考模式</label
              ><select id="reference-mode" v-model="form.reference_mode"
                ><option value="style">畫風參考</option
                ><option value="character">角色外觀參考</option></select
              >

              <figure v-if="source" class="source-preview"
                ><img
                  :src="'/api/assets/' + source.id + '/image'"
                  :alt="'參考素材：' + source.title"
                /><figcaption
                  >原素材預覽；生成時會等比縮放並補白至 224
                  方圖。素材用途標籤不會切換模式。</figcaption
                ></figure
              >
              <template v-for="spec in referenceRoles" :key="spec.role"
                ><label :for="'reference-' + spec.role">{{ spec.label }}</label
                ><select :id="'reference-' + spec.role" v-model="form[spec.key]"
                  ><option value="">選擇元件</option
                  ><option
                    v-if="
                      form[spec.key] &&
                      !components?.components.some(
                        (r) => r.role === spec.role && r.name === form[spec.key],
                      )
                    "
                    :value="form[spec.key]"
                    >{{ form[spec.key] }}（清單未確認）</option
                  ><option
                    v-for="r in components?.components.filter((r) => r.role === spec.role)"
                    :key="r.name"
                    :value="r.name"
                    :disabled="!r.listed"
                    >{{ r.name }} · {{ r.version || '未知版本' }} · {{ r.family
                    }}{{ r.listed ? '' : '（已不在清單）' }}</option
                  ></select
                ></template
              >
              <label for="reference-weight">參考權重</label
              ><input
                id="reference-weight"
                v-model.number="form.reference_weight"
                type="number"
                min="0"
                max="2"
                step="any"
              />
              <p class="footnote"
                >0
                為同流程無參考對照；權重增加可能帶入姿勢、服裝並降低提示詞遵循，沒有通用品質預設。</p
              >
              <div class="fields"
                ><label for="reference-start"
                  >作用起始<input
                    id="reference-start"
                    v-model.number="form.reference_start"
                    type="number"
                    min="0"
                    max="1"
                    step="any" /></label
                ><label for="reference-end"
                  >作用結束<input
                    id="reference-end"
                    v-model.number="form.reference_end"
                    type="number"
                    min="0"
                    max="1"
                    step="any" /></label
              ></div>

              <label for="reference-negative">負面提示詞</label
              ><textarea
                id="reference-negative"
                v-model="form.negative_prompt"
                rows="3"
                maxlength="20000"
              />
              <details class="custom-size"
                ><summary>自訂像素尺寸</summary
                ><div class="fields"
                  ><label for="reference-width"
                    >寬度<input
                      id="reference-width"
                      v-model.number="form.width"
                      type="number"
                      min="64"
                      max="8192"
                      step="8" /></label
                  ><label for="reference-height"
                    >高度<input
                      id="reference-height"
                      v-model.number="form.height"
                      type="number"
                      min="64"
                      max="8192"
                      step="8" /></label></div
              ></details>
              <label for="reference-seed">Seed（精確整數）</label
              ><input
                id="reference-seed"
                v-model="form.seed"
                inputmode="numeric"
                pattern="[0-9]{1,20}"
                maxlength="20"
              />
              <div class="fields"
                ><label for="reference-steps"
                  >Steps<input
                    id="reference-steps"
                    v-model.number="form.steps"
                    type="number"
                    min="1"
                    max="150"
                    step="1" /></label
                ><label for="reference-cfg"
                  >CFG<input
                    id="reference-cfg"
                    v-model.number="form.cfg"
                    type="number"
                    min="0"
                    max="30"
                    step="any" /></label
              ></div>
              <label for="reference-sampler">取樣器</label
              ><select id="reference-sampler" v-model="form.sampler_name"
                ><option
                  v-if="!capabilities?.sampler_names.includes(form.sampler_name)"
                  :value="form.sampler_name"
                  >{{ form.sampler_name }}（未確認）</option
                ><option v-for="name in capabilities?.sampler_names" :key="name" :value="name">{{
                  name
                }}</option></select
              >
              <label for="reference-scheduler">Scheduler</label
              ><select id="reference-scheduler" v-model="form.scheduler"
                ><option
                  v-if="!capabilities?.schedulers.includes(form.scheduler)"
                  :value="form.scheduler"
                  >{{ form.scheduler }}（未確認）</option
                ><option v-for="name in capabilities?.schedulers" :key="name" :value="name">{{
                  name
                }}</option></select
              >
              <p class="footnote"
                >原引擎：{{
                  form.engine_url || '讀取中'
                }}。需要參考模式、前處理及元件的專用格式，目前一般草稿、設定交換與比較方案均未開放。</p
              ></details
            >
          </fieldset></form
        ><details class="studio-tools"
          ><summary>草稿、來源與設定交換</summary
          ><div class="toolbar"
            ><strong>SDXL 畫風／角色外觀參考</strong
            ><button class="secondary" :disabled="locked" @click="load(true)"
              >更新清單與引擎選項</button
            ><button class="secondary" @click="emit('assets')">管理參考素材 →</button
            ><button class="secondary" @click="emit('models')">Checkpoint 版本與來源 →</button></div
          >
          <p class="footnote"
            >單張參考圖，兩種模式分開驗收。畫風模式使用 style transfer；角色外觀模式使用
            linear。相似外觀不代表身份鎖定，構圖與服裝也可能被帶入。首版不組合 LoRA。</p
          >
          <p class="footnote"
            >參考圖等比補白至 224 × 224，再由原引擎編碼；輸出尺寸獨立。單次一張、空 latent、denoise
            1。表單僅在本次工作台切換時保留，提交後可從任務／作品載入完整原設定。</p
          >
          <template v-if="origin"
            ><p v-for="warning in origin.warnings" :key="warning" class="footnote">{{ warning }}</p
            ><ReferenceComponentsSnapshot :items="origin.component_metadata" /><ReferenceSnapshot
              :items="origin.reference_metadata" /><RuntimeSnapshot :item="origin.runtime_metadata"
          /></template>
          <ReferenceComponents
            :library="components"
            :engine-url="form.engine_url"
            :disabled="locked"
            @busy="metadataBusy = $event"
            @updated="load()" />
          <AssetChoices
            :selected-ids="[form.image_asset_id || '', assetRequest?.id || '']"
            @items="assets = $event" /></details
        ><div class="studio-submit" id="studio-submit-reference"></div></div
      ><div class="studio-stage"
        ><StudioPreview :width="form.width" :height="form.height" /><GenerationPanel
          submit-target="#studio-submit-reference"
          :form="form"
          workflow="reference"
          :blocked-reason="block"
          :disabled="busy || metadataBusy || !!pendingRestore"
          @busy="generationBusy = $event"
          @pending="generationPending = $event"
          @gallery="emit('gallery', $event)"
          @restore-job="restore('jobs', $event)" /></div
    ></div>
  </section>
</template>
<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 18px;
  font-size: 12px;
}
.reference-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: 22px;
  align-items: start;
}
.editor fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
.editor label {
  display: block;
  font-size: 12px;
  margin: 18px 0 8px;
}
.editor input,
.editor select,
.editor textarea {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}
.editor select,
.editor textarea {
  font: inherit;
  font-size: 13px;
  border: 1px solid var(--border-control);
  border-radius: 7px;
  padding: 12px;
  background: var(--surface-input);
  color: var(--text-primary);
}
.editor textarea {
  line-height: 1.8;
  resize: vertical;
}
.fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.fields input {
  margin-top: 8px;
}
.footnote {
  overflow-wrap: anywhere;
  line-height: 1.8;
}
.source-preview {
  margin: 18px 0;
}
.source-preview img {
  max-width: 100%;
  max-height: 260px;
  object-fit: contain;
}
.source-preview figcaption {
  font-size: 12px;
  line-height: 1.8;
}
@media (max-width: 1100px) {
  .reference-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 500px) {
  .fields {
    grid-template-columns: 1fr;
  }
}
</style>
