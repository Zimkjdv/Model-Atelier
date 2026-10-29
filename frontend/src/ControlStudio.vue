<script setup lang="ts">
import UiIcon from './UiIcon.vue'
import StudioUtilityBar from './StudioUtilityBar.vue'
import { generationFieldProblems, vFieldError, type PreflightBlocker } from './generationPreflight'
import SizePresets from './SizePresets.vue'
import StudioPreview from './StudioPreview.vue'
import type { Job as PreviewJob } from './jobEvents'
const previewJob = ref<PreviewJob | null>(null)
const stageView = ref('source')
import { apiJson as api } from './apiClient'
import { createRequestScope } from './requestScope'
import { useUnsavedChanges } from './unsavedChanges'
import UnsavedChangesNotice from './UnsavedChangesNotice.vue'
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
import GenerationPanel from './GenerationPanel.vue'
import AssetChoices from './AssetChoices.vue'
import ControlSnapshot from './ControlSnapshot.vue'
import CannyPreview from './CannyPreview.vue'
import {
  registeredControlProblem,
  type ControlCatalog,
  type ControlMetadata,
} from './controlSettings'
import LoraControls from './LoraControls.vue'
import ReferenceSnapshot from './ReferenceSnapshot.vue'
import RuntimeSnapshot from './RuntimeSnapshot.vue'
import {
  type ReferenceAsset,
  type ReferenceSnapshot as ReferenceMetadata,
} from './referenceSettings'
import type { RuntimeMetadata } from './runtimeMetadata'
import {
  chooseSource,
  copyControl,
  controlProblem,
  newControl,
  type ControlForm,
} from './controlSettings'
import { type ModelProfile, validateProfile } from './modelProfiles'
const props = defineProps<{
  assetRequest?: { id: string; purpose: string; token: number } | null
  restoreRequest?: { artworkId: string; token: number } | null
}>()
const emit = defineEmits<{ models: []; assets: []; gallery: [jobId: string] }>()
type Catalog = {
  engine_url: string
  models: { name: string; listed: boolean; version?: string; architecture?: string }[]
}
type Capabilities = {
  engine_url: string
  engine_matches: boolean
  available: boolean
  stale: boolean
  sampler_names: string[]
  schedulers: string[]
  sync_error: string | null
}
type Restoration = {
  settings: ControlForm
  component_metadata?: ControlMetadata[] | null
  warnings: string[]
  reference_metadata?: ReferenceMetadata[] | null
  runtime_metadata?: RuntimeMetadata | null
  job_id?: string
  artwork_id?: string
}
const form = reactive(newControl()),
  catalog = ref<Catalog | null>(null),
  assets = ref<ReferenceAsset[]>([]),
  capabilities = ref<Capabilities | null>(null),
  profile = ref<ModelProfile | null>(null)
const busy = ref(false),
  error = ref(''),
  message = ref(''),
  loraBlock = ref(''),
  generationBusy = ref(false),
  generationPending = ref(false)
const origin = ref<Restoration | null>(null),
  pendingRestore = ref<Restoration | null>(null)
const baseline = ref(JSON.stringify(form)),
  dirty = computed(() => JSON.stringify(form) !== baseline.value)
const controls = ref<ControlCatalog | null>(null)
useUnsavedChanges(dirty)
const source = computed(() => assets.value.find((a) => a.id === form.image_asset_id))
const controlModel = computed(() =>
  controls.value?.controlnets.find((m) => m.name === form.control_net_name),
)
const locked = computed(
  () => busy.value || generationBusy.value || generationPending.value || !!pendingRestore.value,
)
const loads = createRequestScope(),
  restores = createRequestScope()
let mounted = false,
  alive = true
async function load(sync = false) {
  const request = loads.begin(),
    url = form.engine_url,
    name = form.checkpoint
  busy.value = true
  error.value = ''
  catalog.value = null
  capabilities.value = null
  profile.value = null
  controls.value = null
  try {
    const results = await Promise.all([
      api<Catalog>('models', { signal: request.signal }),
      api<ControlCatalog>('controlnets', { signal: request.signal }),
      api<Capabilities>('engine/capabilities' + (sync ? '/sync' : ''), {
        method: sync ? 'POST' : 'GET',
        signal: request.signal,
      }),
    ])
    if (!request.isCurrent() || !alive) return
    catalog.value = results[0]
    controls.value = results[1]
    capabilities.value = results[2]
    if (!form.engine_url) {
      form.engine_url = results[0].engine_url
      baseline.value = JSON.stringify(form)
    }
    if (form.engine_url !== url && url) return
    if (name && form.checkpoint === name) {
      const value = validateProfile(
        await api<ModelProfile>(
          'models/profile?' + new URLSearchParams({ engine_url: form.engine_url, name }),
          { signal: request.signal },
        ),
      )
      if (
        request.isCurrent() &&
        form.checkpoint === name &&
        form.engine_url === value.engine_url &&
        value.name === name
      )
        profile.value = value
    }
  } catch (e) {
    if (request.isCurrent() && !request.signal.aborted)
      error.value = e instanceof Error ? e.message : '讀取失敗'
  } finally {
    if (request.isCurrent()) {
      busy.value = false
    }
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
  if (busy.value) return '正在更新輸入與引擎資料。'
  if (loraBlock.value) return loraBlock.value
  const input = controlProblem(form, source.value)
  if (input) return input
  if (!form.checkpoint) return '請選擇 checkpoint。'
  if (catalog.value?.engine_url !== form.engine_url)
    return '原設定的引擎與目前設定不同，請連接原引擎再更新。'
  if (!catalog.value.models.some((m) => m.listed && m.name === form.checkpoint))
    return '模型清單未確認此 checkpoint，請到模型庫同步。'
  if (
    profile.value?.engine_url !== form.engine_url ||
    profile.value.name !== form.checkpoint ||
    !['sd1', 'sdxl'].includes(profile.value.architecture)
  )
    return '需明確登記 SD 1.x 或 SDXL 架構，請確認模型庫。'
  const control = registeredControlProblem(
    controls.value,
    form.engine_url,
    form.control_net_name,
    profile.value.architecture,
    form.control_kind ?? 'canny',
  )
  if (control) return control
  const c = capabilities.value
  if (c?.engine_url !== form.engine_url || !c.available || !c.engine_matches || c.stale)
    return '需更新原引擎的取樣選項；历史快照不能用於生成。'
  if (!c.sampler_names.includes(form.sampler_name) || !c.schedulers.includes(form.scheduler))
    return '目前取樣器或 scheduler 未在原引擎選項內，請手動調整。'
  return ''
})
function changeKind(kind: string) {
  if (locked.value) return
  if (kind === 'canny') delete form.control_kind
  else if (kind === 'pose' || kind === 'depth') form.control_kind = kind
  form.control_net_name = ''
  origin.value = null
}
function selectSource(id: string | null) {
  if (!locked.value) {
    chooseSource(form, id)
    origin.value = null
  }
}
function apply(value: Restoration) {
  if (generationBusy.value || generationPending.value) return
  const copied = copyControl(value.settings)
  restores.cancel()
  delete form.control_kind
  Object.assign(form, copied)
  origin.value = value
  pendingRestore.value = null
  baseline.value = ''
  message.value = '完整結構來源、控制模型與設定已載入。請手動確認，再生成新任務。'
  void load()
}
async function restore(kind: 'jobs' | 'artworks', id: string, token?: number) {
  if (generationBusy.value || generationPending.value || !alive) {
    error.value = '請先完成或恢復目前提交，再載入設定。'
    return
  }
  const request = restores.begin()
  error.value = ''
  try {
    const value = await api<Restoration>(kind + '/' + id + '/creation-settings', {
      signal: request.signal,
    })
    if (
      !request.isCurrent() ||
      (token !== undefined && props.restoreRequest?.token !== token) ||
      !alive
    )
      return
    if ((kind === 'jobs' ? value.job_id : value.artwork_id) !== id)
      throw new Error('回傳的來源 ID 不同，未載入。')
    copyControl(value.settings)
    if (dirty.value) pendingRestore.value = value
    else apply(value)
  } catch (e) {
    if (request.isCurrent() && !request.signal.aborted)
      error.value = e instanceof Error ? e.message : '還原失敗'
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
    selectSource(request.id)
  },
  { flush: 'post' },
)
const fieldProblems = computed(() => generationFieldProblems(form))
const preflightBlockers = computed(() => {
  const issues: PreflightBlocker[] = [],
    c = capabilities.value
  if (!busy.value && catalog.value?.engine_url !== form.engine_url)
    issues.push({ message: '原設定的引擎與目前設定不同，請連接原引擎再更新。', action: 'settings' })
  if (
    form.checkpoint &&
    catalog.value &&
    !catalog.value.models.some((model) => model.listed && model.name === form.checkpoint)
  )
    issues.push({ message: '模型清單未確認此 checkpoint，請到模型庫同步。', action: 'models' })
  if (
    !busy.value &&
    (c?.engine_url !== form.engine_url || !c.available || !c.engine_matches || c.stale)
  )
    issues.push({ message: '需更新原引擎的取樣選項；歷史快照不能用於生成。', action: 'settings' })
  if (block.value && !issues.some((item) => item.message === block.value))
    issues.push({ message: block.value })
  return issues
})
</script>
<template>
  <section aria-label="結構參考工作台">
    <div class="studio-workbench"
      ><div class="studio-settings"
        ><div class="studio-fields-scroll">
          <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
          <p v-if="message" class="notice" role="status">{{ message }}</p>
          <div v-if="pendingRestore" class="notice warning"
            ><p>載入將取代目前未提交表單。</p
            ><button class="secondary" @click="pendingRestore = null">繼續編輯</button
            ><button
              class="secondary"
              :disabled="generationBusy || generationPending"
              @click="apply(pendingRestore)"
              >捨棄變更並載入</button
            ></div
          ><form class="panel editor" @submit.prevent
            ><fieldset :disabled="locked">
              <label for="control-source" class="studio-field-label"
                ><UiIcon name="assets" :size="15" />結構來源圖</label
              ><select
                v-field-error:image_asset_id="fieldProblems.image_asset_id"
                id="control-source"
                :value="form.image_asset_id ?? ''"
                @change="selectSource(($event.target as HTMLSelectElement).value || null)"
                ><option value="">選擇原圖素材</option
                ><option v-if="form.image_asset_id && !source" :value="form.image_asset_id"
                  >原素材不存在（{{ form.image_asset_id }}）</option
                ><option
                  v-for="asset in assets.filter((a) => !a.archived || a.id === form.image_asset_id)"
                  :key="asset.id"
                  :value="asset.id"
                  :disabled="asset.archived"
                  >{{ asset.title }} · {{ asset.width }} × {{ asset.height
                  }}{{ asset.archived ? '（已封存）' : '' }}</option
                ></select
              >
              <label for="control-prompt" class="studio-field-label"
                ><UiIcon name="text" :size="15" />描述你想創作的畫面
                <small>{{ form.prompt.length.toLocaleString() }} / 20,000</small></label
              ><textarea
                v-field-error:prompt="fieldProblems.prompt"
                id="control-prompt"
                v-model="form.prompt"
                maxlength="20000"
                rows="5"
                placeholder="描述希望生成的物件、動作或場景"
              />
              <label for="control-checkpoint" class="studio-field-label"
                ><UiIcon name="models" :size="15" />模型</label
              ><select
                v-field-error:checkpoint="fieldProblems.checkpoint"
                id="control-checkpoint"
                v-model="form.checkpoint"
                ><option value="">選擇模型</option
                ><option
                  v-if="form.checkpoint && !catalog?.models.some((m) => m.name === form.checkpoint)"
                  :value="form.checkpoint"
                  >{{ form.checkpoint }}（清單未確認）</option
                ><option
                  v-for="model in catalog?.models"
                  :key="model.name"
                  :value="model.name"
                  :disabled="
                    !model.listed || ['flux', 'sd3', 'other'].includes(model.architecture || '')
                  "
                  >{{ model.name
                  }}{{
                    !model.listed
                      ? '（已不在清單）'
                      : ['flux', 'sd3', 'other'].includes(model.architecture || '')
                        ? '（此流程不支援）'
                        : ''
                  }}</option
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
              /><label for="control-kind" class="studio-field-label"
                ><UiIcon name="control" :size="15" />結構方式</label
              ><select
                id="control-kind"
                :value="form.control_kind ?? 'canny'"
                @change="changeKind(($event.target as HTMLSelectElement).value)"
                ><option value="canny">Canny 輪廓</option
                ><option value="pose">Pose 姿勢（SDXL）</option
                ><option value="depth">Depth 相對深度（SDXL）</option></select
              >
              <details class="studio-advanced"
                ><summary>進階設定</summary><h2>原圖與生成設定</h2
                ><label for="control-title">名稱</label
                ><input
                  v-field-error:title="fieldProblems.title"
                  id="control-title"
                  v-model="form.title"
                  required
                  maxlength="100" />

                <figure v-if="source" class="source-preview"
                  ><img
                    :src="'/api/assets/' + source.id + '/image'"
                    :alt="'結構參考素材：' + source.title"
                  /><figcaption
                    >原素材預覽；生成時先縮放／補白，再由原引擎計算所選條件。此處是原圖。</figcaption
                  ></figure
                >
                <p class="footnote"
                  >Pose／Depth
                  需額外前處理節點與匹配控制權重；同次實際條件圖在任務完成後保存。動漫偵測可能遺漏手部或臉部。</p
                ><label for="control-model">ControlNet</label
                ><select
                  v-field-error:control_net_name="fieldProblems.control_net_name"
                  id="control-model"
                  v-model="form.control_net_name"
                  ><option value="">選擇控制模型</option
                  ><option
                    v-if="form.control_net_name && !controlModel"
                    :value="form.control_net_name"
                    >{{ form.control_net_name }}（清單未確認）</option
                  ><option
                    v-for="model in controls?.controlnets"
                    :key="model.name"
                    :value="model.name"
                    :disabled="!model.listed"
                    >{{ model.name }} · {{ model.version || '未知' }} · {{ model.kind
                    }}{{ !model.listed ? '（已不在清單）' : '' }}</option
                  ></select
                >
                <p class="footnote"
                  >控制模型版本 {{ controlModel?.version || '未知' }} · 架構
                  {{ controlModel?.architecture || '未知' }} · 類型
                  {{ controlModel?.kind || '未知' }}。登記資料不是驗檔證明。</p
                >
                <label for="control-strength"
                  >控制強度<input
                    v-field-error:control_strength="fieldProblems.control_strength"
                    id="control-strength"
                    v-model.number="form.control_strength"
                    type="number"
                    min="0"
                    max="10"
                    step="any"
                /></label>
                <div class="fields"
                  ><label for="control-start"
                    >作用起始<input
                      v-field-error:control_start="fieldProblems.control_start"
                      id="control-start"
                      v-model.number="form.control_start"
                      type="number"
                      min="0"
                      max="1"
                      step="any" /></label
                  ><label for="control-end"
                    >作用結束<input
                      v-field-error:control_end="fieldProblems.control_end"
                      id="control-end"
                      v-model.number="form.control_end"
                      type="number"
                      min="0"
                      max="1"
                      step="any" /></label
                ></div>
                <div v-if="!form.control_kind" class="fields"
                  ><label for="control-low"
                    >Canny 低閾值<input
                      v-field-error:canny_low="fieldProblems.canny_low"
                      id="control-low"
                      v-model.number="form.canny_low"
                      type="number"
                      min="0.01"
                      max="0.99"
                      step="any" /></label
                  ><label for="control-high"
                    >Canny 高閾值<input
                      v-field-error:canny_high="fieldProblems.canny_high"
                      id="control-high"
                      v-model.number="form.canny_high"
                      type="number"
                      min="0.01"
                      max="0.99"
                      step="any" /></label
                ></div>
                <p class="footnote"
                  >作用起始小於結束；低閾值小於高閾值。這是原生 Canny 浮點閾值，不是 OpenCV 的
                  0–255。控制強度沒有通用品質預設。</p
                >

                <label for="control-negative">負面提示詞</label
                ><textarea
                  v-field-error:negative_prompt="fieldProblems.negative_prompt"
                  id="control-negative"
                  v-model="form.negative_prompt"
                  maxlength="20000"
                  rows="3" />
                <details class="custom-size"
                  ><summary>自訂像素尺寸</summary
                  ><div class="fields"
                    ><label for="control-width"
                      >寬度<input
                        v-field-error:width="fieldProblems.width"
                        id="control-width"
                        v-model.number="form.width"
                        type="number"
                        min="64"
                        max="8192"
                        step="8" /></label
                    ><label for="control-height"
                      >高度<input
                        v-field-error:height="fieldProblems.height"
                        id="control-height"
                        v-model.number="form.height"
                        type="number"
                        min="64"
                        max="8192"
                        step="8" /></label></div
                ></details>
                <label for="control-resize">結構素材縮放</label
                ><select
                  v-field-error:reference_resize="fieldProblems.reference_resize"
                  id="control-resize"
                  v-model="form.reference_resize"
                  ><option value="fit">等比縮放並補白</option
                  ><option value="stretch">拉伸至輸出尺寸</option></select
                >

                <label for="control-seed">Seed（精確整數）</label
                ><input
                  v-field-error:seed="fieldProblems.seed"
                  id="control-seed"
                  v-model="form.seed"
                  inputmode="numeric"
                  maxlength="20"
                  pattern="[0-9]{1,20}" />
                <div class="fields"
                  ><label for="control-steps"
                    >Steps<input
                      v-field-error:steps="fieldProblems.steps"
                      id="control-steps"
                      v-model.number="form.steps"
                      type="number"
                      min="1"
                      max="150"
                      step="1" /></label
                  ><label for="control-cfg"
                    >CFG<input
                      v-field-error:cfg="fieldProblems.cfg"
                      id="control-cfg"
                      v-model.number="form.cfg"
                      type="number"
                      min="0"
                      max="30"
                      step="any" /></label
                ></div>
                <label for="control-sampler">取樣器</label
                ><select
                  v-field-error:sampler_name="fieldProblems.sampler_name"
                  id="control-sampler"
                  v-model="form.sampler_name"
                  ><option
                    v-if="!capabilities?.sampler_names.includes(form.sampler_name)"
                    :value="form.sampler_name"
                    >{{ form.sampler_name }}（未確認）</option
                  ><option v-for="name in capabilities?.sampler_names" :key="name" :value="name">{{
                    name
                  }}</option></select
                >
                <label for="control-scheduler">Scheduler</label
                ><select
                  v-field-error:scheduler="fieldProblems.scheduler"
                  id="control-scheduler"
                  v-model="form.scheduler"
                  ><option
                    v-if="!capabilities?.schedulers.includes(form.scheduler)"
                    :value="form.scheduler"
                    >{{ form.scheduler }}（未確認）</option
                  ><option v-for="name in capabilities?.schedulers" :key="name" :value="name">{{
                    name
                  }}</option></select
                >
                <p class="footnote"
                  >固定空 latent／denoise 1，使用 Canny 作結構條件；不以來源 latent
                  作圖生圖。單次輸出一張。</p
                >
                <details class="advanced-controls"
                  ><summary>LoRA 與有序組合</summary
                  ><LoraControls
                    v-model="form.loras"
                    :engine-url="form.engine_url"
                    :checkpoint="form.checkpoint"
                    @blocked="loraBlock = $event" /></details
              ></details> </fieldset></form
          ><StudioUtilityBar :drafts="false" /><UnsavedChangesNotice
            :dirty="dirty"
            page-only /><details class="studio-tools"
            ><summary>草稿、來源與設定交換</summary
            ><div class="toolbar"
              ><strong>Checkpoint 結構參考</strong
              ><button class="secondary" :disabled="locked" @click="load(true)"
                >更新清單與引擎選項</button
              ><button class="secondary" @click="emit('assets')">管理結構素材 →</button
              ><button class="secondary" @click="emit('models')">模型版本與來源 →</button></div
            >
            <details class="studio-validation"
              ><summary>相容性與流程限制</summary
              ><p class="footnote"
                >表單在工作台切換時保留；重新整理會清除未提交的表單。生成後可從任務或作品載入完整原設定。目前不提供一般草稿或比較方案。新提交使用
                Canny v2，完成後可在任務與作品明確保存／查看實際邊緣圖；舊設定重新生成會建立新的 v2
                任務。</p
              >
              <p class="footnote"
                >原引擎 {{ form.engine_url || '讀取中' }} · 模型版本
                {{
                  catalog?.engine_url === form.engine_url
                    ? catalog.models.find((m) => m.name === form.checkpoint)?.version || '未知'
                    : '未知'
                }}。Canny 引導輪廓／構圖，不保證畫風、角色或逐像素相同。</p
              ></details
            >
            <template v-if="origin"
              ><p v-for="warning in origin.warnings" :key="warning" class="footnote">{{
                warning
              }}</p
              ><ControlSnapshot :items="origin.component_metadata" /><ReferenceSnapshot
                :items="origin.reference_metadata" /><RuntimeSnapshot
                :item="origin.runtime_metadata"
            /></template>
            <AssetChoices
              :selected-ids="[form.image_asset_id || '', assetRequest?.id || '']"
              @items="assets = $event" /></details></div
        ><div class="studio-submit" id="studio-submit-control"></div></div
      ><div class="studio-stage control-stage"
        ><div class="stage-view-switch" role="group" aria-label="舞台內容"
          ><button
            class="secondary"
            :aria-pressed="stageView === 'source'"
            @click="stageView = 'source'"
            >結構預覽</button
          ><button
            class="secondary"
            :aria-pressed="stageView === 'result'"
            @click="stageView = 'result'"
            >生成結果</button
          ></div
        ><StudioPreview
          v-if="stageView === 'result'"
          :job="previewJob"
          :width="form.width"
          :height="form.height"
          title="結構引導"
          @gallery="emit('gallery', $event)" /><CannyPreview
          v-show="stageView === 'source'"
          :form="form"
          :source="source"
          :disabled="locked" /><GenerationPanel
          preview-stage
          @preview="previewJob = $event"
          submit-target="#studio-submit-control"
          :form="form"
          workflow="control"
          :blockers="preflightBlockers"
          :field-problems="fieldProblems"
          :blocked-reason="block"
          :disabled="busy || !!pendingRestore"
          @busy="generationBusy = $event"
          @pending="generationPending = $event"
          @gallery="emit('gallery', $event)"
          @restore-job="restore('jobs', $event)" /></div
    ></div>
  </section>
</template>
<style scoped>
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
  line-height: 1.7;
  color: var(--text-secondary);
}
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 18px;
  font-size: 12px;
}
.control-grid {
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
  box-sizing: border-box;
  min-width: 0;
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
  line-height: 1.7;
}
@media (max-width: 1100px) {
  .control-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 500px) {
  .fields {
    grid-template-columns: 1fr;
  }
}
</style>
