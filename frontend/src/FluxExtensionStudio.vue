<script setup lang="ts">
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
import { fluxProblem, fluxRoles, newFlux } from './fluxSettings'
import {
  fluxImageId,
  fluxLoraId,
  type FluxExtensionForm,
  type FluxExtensionRestoration,
} from './fluxExtensions'
import type { ReferenceAsset } from './referenceSettings'
import UnsavedChangesNotice from './UnsavedChangesNotice.vue'
import AssetChoices from './AssetChoices.vue'
import GenerationPanel from './GenerationPanel.vue'
import ComponentSnapshot from './ComponentSnapshot.vue'
import LoraSnapshot from './LoraSnapshot.vue'
import ReferenceSnapshot from './ReferenceSnapshot.vue'
import RuntimeSnapshot from './RuntimeSnapshot.vue'

type Restoration = FluxExtensionRestoration
type Draft = FluxExtensionForm & { id: string; revision: number }
type Profile = {
  ids: string[]
  lora: { filename: string; sha256: string; version: string }
  components: Record<string, string>
}
const props = defineProps<{ imageRequested?: boolean; restoration?: Restoration | null }>()
const emit = defineEmits<{ gallery: [id: string]; models: []; assets: [] }>()
const base = reactive({
  ...newFlux(),
  title: 'FLUX 附加流程',
  width: 512,
  height: 512,
  steps: 4,
  weight_dtype: 'fp8_e4m3fn' as const,
  encoder_device: 'cpu' as const,
})
const kind = ref<'lora' | 'image'>('lora'),
  strength = ref(0.7),
  loraName = ref('flux-schnell-pvc-style.safetensors')
const imageId = ref(''),
  denoise = ref(0.6),
  resize = ref<'fit' | 'stretch'>('fit')
const assets = ref<ReferenceAsset[]>([]),
  profile = ref<Profile | null>(null),
  engine = ref('')
const drafts = ref<Draft[]>([]),
  draftId = ref<string | null>(null),
  revision = ref<number | null>(null)
const form = computed<FluxExtensionForm>(() =>
  kind.value === 'lora'
    ? { ...base, workflow_id: fluxLoraId, lora_name: loraName.value, lora_strength: strength.value }
    : {
        ...base,
        workflow_id: fluxImageId,
        image_asset_id: imageId.value,
        denoise: denoise.value,
        reference_resize: resize.value,
      },
)
const saved = ref(JSON.stringify(form.value)),
  dirty = computed(() => JSON.stringify(form.value) !== saved.value)
const busy = ref(false),
  loading = ref(false),
  generationBusy = ref(false),
  generationPending = ref(false)
const error = ref(''),
  message = ref(''),
  origin = ref<Restoration | null>(null),
  candidate = ref<Draft | Restoration | null>(null)
const locked = computed(
  () => busy.value || loading.value || generationBusy.value || generationPending.value,
)
useUnsavedChanges(dirty, busy)
const problem = computed(() => {
  const general = fluxProblem(base)
  if (general) return general
  if (
    base.width !== 512 ||
    base.height !== 512 ||
    base.steps !== 4 ||
    base.weight_dtype !== 'fp8_e4m3fn' ||
    base.encoder_device !== 'cpu'
  )
    return '此附加設定不在固定 512 FP8／CPU 驗收範圍，未改寫或提交。'
  if (!profile.value) return '請先讀取 FLUX 附加流程能力。'
  if (base.engine_url !== engine.value) return '目前引擎與原設定不同；請確認原引擎後再生成。'
  if (kind.value === 'lora') {
    if (loraName.value !== profile.value.lora.filename) return '未知 LoRA 組合保持停用。'
    if (!Number.isFinite(strength.value) || strength.value < 0 || strength.value > 1)
      return 'LoRA 強度需介於 0 與 1。'
  } else {
    if (!assets.value.some((item) => item.id === imageId.value && !item.archived))
      return '請選擇可用的原圖素材。'
    if (!Number.isFinite(denoise.value) || denoise.value < 0.05 || denoise.value >= 1)
      return '重繪強度需為 0.05 以上且小於 1。'
  }
  return ''
})
const scope = createRequestScope(),
  restores = createRequestScope()
let mounted = false
async function load(sync = false) {
  const request = scope.begin()
  loading.value = true
  error.value = ''
  try {
    const current = await api<{ comfy_url: string }>('settings', { signal: request.signal })
    if (sync) {
      const components = await api<{ sync_error: string | null }>('flux/components/sync', {
        method: 'POST',
        body: JSON.stringify({ engine_url: current.comfy_url }),
        headers: { 'Content-Type': 'application/json' },
        signal: request.signal,
      })
      if (components.sync_error) throw new Error(components.sync_error)
      const loraCatalog = await api<{ sync_error: string | null }>('loras/sync', {
        method: 'POST',
        body: JSON.stringify({ engine_url: current.comfy_url }),
        headers: { 'Content-Type': 'application/json' },
        signal: request.signal,
      })
      if (loraCatalog.sync_error) throw new Error(loraCatalog.sync_error)
    }
    const [description, records, latest] = await Promise.all([
      api<Profile>('flux/extensions/workflow', { signal: request.signal }),
      api<Draft[]>('flux/extensions/drafts', { signal: request.signal }),
      api<{ comfy_url: string }>('settings', { signal: request.signal }),
    ])
    if (!request.isCurrent()) return
    if (
      latest.comfy_url !== current.comfy_url ||
      !description.ids.includes(fluxLoraId) ||
      !description.ids.includes(fluxImageId)
    )
      throw new Error('引擎或 FLUX 附加流程版本已變更，請重讀。')
    profile.value = description
    drafts.value = records
    engine.value = current.comfy_url
    if (!base.engine_url) {
      base.engine_url = engine.value
      for (const role of fluxRoles) base[role.key] = description.components[role.key] || ''
      saved.value = JSON.stringify(form.value)
    }
  } catch (e) {
    if (request.isCurrent()) error.value = e instanceof Error ? e.message : '附加流程讀取失敗'
  } finally {
    if (request.isCurrent()) loading.value = false
  }
}
function apply(value: Draft | Restoration) {
  const settings = 'settings' in value ? value.settings : value
  for (const key of Object.keys(newFlux()) as (keyof typeof base)[]) {
    if (key !== 'workflow_id') Object.assign(base, { [key]: settings[key] })
  }
  kind.value = settings.workflow_id === fluxLoraId ? 'lora' : 'image'
  if ('lora_name' in settings) {
    loraName.value = settings.lora_name
    strength.value = settings.lora_strength
  } else {
    imageId.value = settings.image_asset_id
    denoise.value = settings.denoise
    resize.value = settings.reference_resize
  }
  draftId.value = 'id' in value ? value.id : null
  revision.value = 'revision' in value ? value.revision : null
  origin.value = 'settings' in value ? value : null
  candidate.value = null
  saved.value = 'settings' in value ? '' : JSON.stringify(form.value)
  message.value = '完整附加設定已載入；尚未提交生成。'
}
function choose(value: Draft | Restoration) {
  if (dirty.value) candidate.value = value
  else apply(value)
}
async function restoreJob(id: string) {
  const request = restores.begin()
  error.value = ''
  try {
    const value = await api<Restoration>('flux/jobs/' + id + '/creation-settings', {
      signal: request.signal,
    })
    if (request.isCurrent()) choose(value)
  } catch (e) {
    if (request.isCurrent()) error.value = e instanceof Error ? e.message : '設定讀取失敗'
  }
}
async function save(asNew = false) {
  if (locked.value || problem.value) return
  busy.value = true
  error.value = ''
  try {
    const existing = !asNew && draftId.value
    const record = await api<Draft>(
      'flux/extensions/drafts' + (existing ? '/' + draftId.value : ''),
      {
        method: existing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form.value, ...(existing ? { revision: revision.value } : {}) }),
      },
    )
    draftId.value = record.id
    revision.value = record.revision
    saved.value = JSON.stringify(form.value)
    drafts.value = [record, ...drafts.value.filter((item) => item.id !== record.id)]
    message.value = '附加流程草稿已完整保存；未生成。'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失敗'
  } finally {
    busy.value = false
  }
}
async function download() {
  if (locked.value || problem.value) return
  busy.value = true
  error.value = ''
  try {
    const value = await api<{ workflow_json: string }>('flux/extensions/workflow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value),
    })
    if (typeof value.workflow_json !== 'string') throw new Error('原始 JSON 不完整，未匯出。')
    const url = URL.createObjectURL(new Blob([value.workflow_json], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = form.value.workflow_id + '.json'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    message.value = '原始工作流程已匯出；圖片不包含於 JSON，預覽路徑不會自動上傳。'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '匯出失敗'
  } finally {
    busy.value = false
  }
}
watch(
  () => props.restoration,
  (value) => {
    if (value) choose(value)
  },
  { immediate: true },
)
watch(
  kind,
  () => {
    draftId.value = null
    revision.value = null
  },
  { flush: 'sync' },
)
onMounted(async () => {
  await load()
  mounted = true
})
onActivated(() => {
  if (mounted) void load()
})
onDeactivated(() => {
  scope.cancel()
  restores.cancel()
  loading.value = false
})
onBeforeUnmount(() => {
  scope.dispose()
  restores.dispose()
})
watch(
  () => props.imageRequested,
  (value) => {
    if (value) kind.value = 'image'
  },
  { immediate: true },
)
</script>

<template>
  <section aria-label="FLUX LoRA 與圖生圖工作台">
    <div class="studio-workbench"
      ><div class="studio-settings"
        ><p class="notice"
          >兩個獨立流程：Schnell 模型 LoRA、原生 VAE 圖生圖。固定 512×512／4 步／FP8 e4m3fn／CPU
          編碼器；未知元件及 LoRA＋圖生圖混用保持停用。</p
        >
        <UnsavedChangesNotice :dirty="dirty" :saving="busy" :saved="!!draftId" />
        <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
        <p v-if="message" class="notice" role="status">{{ message }}</p
        ><form
          class="panel extension-editor"
          aria-label="FLUX 附加流程設定"
          @submit.prevent="save()"
          ><fieldset :disabled="locked"
            ><label for="flux-extension-kind">附加流程</label>
            <select id="flux-extension-kind" v-model="kind"
              ><option value="lora">Schnell PVC LoRA</option
              ><option value="image">VAE 圖生圖（構圖重繪）</option></select
            >
            <label for="flux-extension-prompt">附加流程提示詞</label>
            <textarea id="flux-extension-prompt" v-model="base.prompt" rows="5" maxlength="20000" />
            <template v-if="kind === 'image'"
              ><label for="flux-extension-image">FLUX 原圖素材</label
              ><select id="flux-extension-image" v-model="imageId"
                ><option value="">選擇原圖</option
                ><option
                  v-for="item in assets.filter((item) => !item.archived)"
                  :key="item.id"
                  :value="item.id"
                  >{{ item.title }}</option
                ></select
              ><label for="flux-extension-denoise">FLUX 重繪強度</label
              ><input
                id="flux-extension-denoise"
                v-model.number="denoise"
                type="number"
                min="0.05"
                max="0.99"
                step="0.05" /><label for="flux-extension-resize">原圖縮放</label
              ><select id="flux-extension-resize" v-model="resize"
                ><option value="fit">等比完整放入，白色補邊</option
                ><option value="stretch">拉伸至輸出尺寸</option></select
              ><p class="footnote"
                >VAE 由原圖建立 latent，會保留部分構圖；這不是
                Redux／IP-Adapter，也不保證畫風或角色身份一致。輸入
                PNG、來源與前處理雜湊會隨任務保存。</p
              ><img
                v-if="imageId"
                :src="'/api/assets/' + imageId + '/image'"
                alt="目前選擇的 FLUX 原圖"
                class="extension-image"
            /></template>
            <details class="studio-advanced"
              ><summary>進階設定、草稿名稱與模型能力</summary>
              <label for="flux-extension-title">附加草稿名稱</label
              ><input id="flux-extension-title" v-model="base.title" required maxlength="100" />
              <template v-if="kind === 'lora'"
                ><label for="flux-extension-lora">FLUX LoRA 名稱</label
                ><input id="flux-extension-lora" v-model="loraName" required /><label
                  for="flux-extension-strength"
                  >模型 LoRA 強度</label
                ><input
                  id="flux-extension-strength"
                  v-model.number="strength"
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                /><p class="footnote"
                  >只處理 diffusion model，CLIP 強度固定 0。已驗收固定 PVC 版本；Schnell 不沿用
                  SDXL／Dev LoRA。建議提示詞含 pvc figure；品質與授權另行確認。</p
                ></template
              >

              <div v-for="role in fluxRoles" :key="role.key"
                ><label :for="'extension-' + role.key">{{ role.label }}</label
                ><input
                  :id="'extension-' + role.key"
                  v-model="base[role.key]"
                  required
                  maxlength="2048"
              /></div>

              <label for="flux-extension-seed">附加流程 Seed</label
              ><input
                id="flux-extension-seed"
                v-model="base.seed"
                inputmode="numeric"
                pattern="[0-9]{1,20}"
                required
                maxlength="20"
              />
              <p v-if="problem" class="footnote" role="status">{{ problem }}</p>
              <div class="extension-actions"
                ><button class="primary" type="submit" :disabled="!!problem"
                  >保存附加流程草稿</button
                ><button class="secondary" type="button" :disabled="!!problem" @click="save(true)"
                  >另存附加流程草稿</button
                ><button class="secondary" type="button" :disabled="!!problem" @click="download"
                  >匯出附加流程 JSON</button
                ></div
              >
              <p class="footnote"
                >一般設定交換格式暫不支援這兩種流程；請使用本頁完整草稿、原任務／作品還原與原始
                JSON。</p
              ></details
            >
          </fieldset></form
        ><details class="studio-tools"
          ><summary>草稿、來源與設定交換</summary
          ><div class="extension-actions"
            ><button class="secondary" :disabled="locked" @click="load(true)">同步附加元件</button
            ><button class="secondary" @click="emit('models')">登記版本與 SHA256</button
            ><button class="secondary" @click="emit('assets')">匯入參考素材</button></div
          >
          <div v-if="candidate" class="notice warning" role="alert"
            ><p>載入會取代未保存的附加流程設定。</p
            ><button class="secondary" @click="candidate = null">繼續編輯附加流程</button
            ><button class="secondary" @click="apply(candidate)"
              >捨棄變更並載入附加流程</button
            ></div
          >
          <AssetChoices
            v-if="kind === 'image'"
            :selected-ids="imageId ? [imageId] : []"
            @items="assets = $event" /></details
        ><div class="studio-submit" id="studio-submit-flux-addon"></div></div
      ><div class="studio-stage"
        ><StudioPreview :width="form.width" :height="form.height" /><div
          ><GenerationPanel
            submit-target="#studio-submit-flux-addon"
            :form="form"
            workflow="flux-addon"
            :blocked-reason="problem"
            :disabled="busy || loading || !!candidate"
            @busy="generationBusy = $event"
            @pending="generationPending = $event"
            @gallery="emit('gallery', $event)"
            @restore-job="restoreJob"
          />
          <article class="panel"
            ><h2>附加流程草稿</h2
            ><p v-if="!drafts.length" class="footnote">LoRA 與原圖設定使用獨立版本格式保存。</p
            ><button
              v-for="record in drafts"
              :key="record.id"
              class="extension-draft secondary"
              :disabled="locked"
              @click="choose(record)"
              >{{ record.title }} · {{ record.workflow_id }}</button
            ></article
          >
          <template v-if="origin"
            ><ComponentSnapshot :items="origin.component_metadata" /><LoraSnapshot
              :items="origin.lora_metadata" /><ReferenceSnapshot
              :items="origin.reference_metadata" /><RuntimeSnapshot :item="origin.runtime_metadata"
          /></template> </div></div
    ></div>
  </section>
</template>

<style scoped>
.extension-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 22px;
}
.extension-grid > div {
  min-width: 0;
}
.extension-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 18px 0;
}
.extension-editor fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.extension-editor label {
  display: block;
  font-size: 12px;
  margin: 18px 0 8px;
}
.extension-editor input,
.extension-editor select,
.extension-editor textarea {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
}
.extension-editor select,
.extension-editor textarea {
  font: inherit;
  padding: 12px;
  border: 1px solid var(--border-control);
  background: var(--surface-input);
  color: var(--text-primary);
  border-radius: 7px;
}
.extension-editor select:focus-visible,
.extension-editor textarea:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 3px;
}
.extension-image {
  max-width: 100%;
  max-height: 240px;
  object-fit: contain;
}
.extension-draft {
  display: block;
  text-align: left;
  width: 100%;
  margin-top: 12px;
  overflow-wrap: anywhere;
}
@media (max-width: 1000px) {
  .extension-grid {
    grid-template-columns: 1fr;
  }
}
</style>
