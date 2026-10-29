<script setup lang="ts">
import {
  computed,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  reactive,
  ref,
  nextTick,
} from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'
import { newCreation, type CreationForm } from './creationSettings'
import { newFlux, type FluxCatalog, type FluxForm } from './fluxSettings'
import {
  generationFieldProblems,
  vFieldError,
  type FieldLimits,
  type PreflightBlocker,
} from './generationPreflight'
import { validateProfile, type ModelProfile } from './modelProfiles'
import type { EngineReport } from './environmentTypes'
import type { Job } from './jobEvents'
import { useUnsavedChanges } from './unsavedChanges'
import {
  matchSimpleModel,
  simpleFluxComponents,
  simpleTemplates,
  type ListedModel,
  type SimpleTemplateId,
} from './simpleCreation'
import GenerationPanel from './GenerationPanel.vue'
import StudioPreview from './StudioPreview.vue'
import TemplateSnapshot from './TemplateSnapshot.vue'
import { templateSelection, type TemplateSelection, type TemplateContext } from './templateContext'

const emit = defineEmits<{
  advanced: [settings: CreationForm | FluxForm, selection?: TemplateSelection | null]
  models: [category?: 'checkpoint' | 'flux']
  settings: []
  gallery: [jobId: string]
}>()
type Catalog = {
  engine_url: string
  models: ListedModel[]
  synced_at: string | null
  sync_error: string | null
}
type Capabilities = {
  engine_url: string
  engine_matches: boolean
  available: boolean
  stale: boolean
  sampler_names: string[]
  schedulers: string[]
  bounds?: FieldLimits['bounds']
}
const selectedId = ref<SimpleTemplateId>('animagine')
const selected = computed(() => simpleTemplates.find((item) => item.id === selectedId.value)!)
const checkpoint = reactive(newCreation())
const flux = reactive(newFlux())
const form = computed(() => (selected.value.family === 'flux' ? flux : checkpoint))
const catalog = ref<Catalog | null>(null)
const fluxCatalog = ref<FluxCatalog | null>(null)
const engine = ref<EngineReport | null>(null)
const capabilities = ref<Capabilities | null>(null)
const engineUrl = ref('')
const profile = ref<ModelProfile | null>(null)
const loadedId = ref<SimpleTemplateId | null>(null)
const editing = ref(false)
const selection = computed<TemplateSelection | null>(() =>
  loadedId.value ? { template_id: loadedId.value, template_version: selected.value.version } : null,
)
const baseline = ref('')
const error = ref('')
const message = ref('')
const loading = ref(false)
const generating = ref(false)
const pending = ref(false)
const saving = ref(false)
const previewJob = ref<Job | null>(null)
const previewTemplate = ref<TemplateContext | null>(null)
const previewTemplateJob = ref('')
const savedJob = ref('')
const submittedForm = ref<{ id: string; signature: string } | null>(null)
const resultMatchesForm = computed(
  () =>
    submittedForm.value?.id === previewJob.value?.id &&
    submittedForm.value?.signature === JSON.stringify(form.value),
)
function submitted(id: string, settings: Record<string, unknown>) {
  submittedForm.value = {
    id,
    signature: JSON.stringify(
      Object.fromEntries(Object.keys(form.value).map((key) => [key, settings[key]])),
    ),
  }
}
const previewRevision = ref(0)
const reads = createRequestScope()
const profiles = createRequestScope()
const restores = createRequestScope()
const previewReads = createRequestScope()
let active = true
let templateEpoch = 0
const modified = computed(() => !!loadedId.value && JSON.stringify(form.value) !== baseline.value)
const unsaved = computed(() => modified.value)
useUnsavedChanges(unsaved, saving)
const locked = computed(() => generating.value || pending.value || saving.value)
const step = computed(() =>
  !loadedId.value
    ? 1
    : generating.value || pending.value
      ? 3
      : !resultMatchesForm.value || previewTemplate.value?.selection.template_id !== loadedId.value
        ? 2
        : savedJob.value === previewJob.value?.id
          ? 4
          : previewJob.value?.status === 'completed'
            ? 3
            : 2,
)

function requirements() {
  const status = availability(selectedId.value)
  if (loading.value)
    return [{ key: 'loading', label: '正在檢查模型與引擎…', action: 'refresh' as const }]
  if (!engine.value || engine.value.url !== engineUrl.value || !engine.value.connected)
    return [
      {
        key: 'engine',
        label: '先啟動 ComfyUI，確認連線後按「重新檢查」。',
        action: 'settings' as const,
      },
    ]
  const inventory = selected.value.family === 'flux' ? fluxCatalog.value : catalog.value
  const items: { key: string; label: string; action: 'models' | 'refresh' | 'settings' }[] = []
  if (!inventory?.synced_at || inventory.sync_error)
    items.push({
      key: 'sync',
      label: '清單尚未同步或更新失敗，請到模型庫同步此分類。',
      action: 'models',
    })
  const expected =
    selected.value.family === 'flux'
      ? fluxMatches.value.map((part) => ({
          key: part.role,
          filename: part.filename,
          found: !!part.model,
          listed: fluxCatalog.value?.groups[part.category]?.some(
            (item) => item.listed && item.name === part.filename,
          ),
        }))
      : [
          {
            key: 'checkpoint',
            filename: selected.value.manifest!.filename,
            found: !!modelFor(selectedId.value),
            listed: catalog.value?.models.some(
              (item) => item.listed && item.name === selected.value.manifest!.filename,
            ),
          },
        ]
  for (const part of expected)
    if (!part.found)
      items.push({
        key: part.key,
        label: part.listed
          ? `${part.filename}：已列在清單，請核對版本與模型登記。`
          : `${part.filename}：清單中尚未找到相符項目，請先安裝並同步。`,
        action: 'models',
      })
  if (!items.length && status !== '可載入配方')
    items.push({ key: 'unknown', label: status + '，請重新檢查。', action: 'refresh' })
  return items
}
function repair(action: 'models' | 'settings' | 'refresh') {
  if (action === 'models') emit('models', selected.value.family === 'flux' ? 'flux' : 'checkpoint')
  else if (action === 'settings') emit('settings')
  else void refresh(true)
}
async function editDescription() {
  editing.value = true
  await nextTick()
  document.getElementById('simple-prompt')?.focus()
}
async function preview(value: Job | null) {
  previewJob.value = value
  if (!active) return
  if (!value) {
    previewReads.cancel()
    previewTemplate.value = null
    previewTemplateJob.value = ''
    return
  }
  if (previewTemplateJob.value === value.id) return
  const read = previewReads.begin()
  previewTemplate.value = null
  previewTemplateJob.value = value.id
  try {
    const full = await apiJson<Job>('jobs/' + value.id, { signal: read.signal })
    if (read.isCurrent() && previewJob.value?.id === value.id)
      previewTemplate.value = full.template_context || null
  } catch (cause) {
    if (read.isCurrent()) {
      previewTemplateJob.value = ''
      error.value = '結果來源讀取失敗，請重新檢查或到任務資訊查看。'
    }
  }
}

function modelFor(id: SimpleTemplateId) {
  const template = simpleTemplates.find((item) => item.id === id)!
  return template.manifest && catalog.value?.engine_url === engineUrl.value
    ? matchSimpleModel(catalog.value.models, template.manifest, 'sdxl')
    : undefined
}
const fluxMatches = computed(() =>
  simpleFluxComponents.map((part) => ({
    ...part,
    model:
      fluxCatalog.value?.engine_url === engineUrl.value
        ? matchSimpleModel(
            fluxCatalog.value.groups[part.category] || [],
            part,
            part.role === 'diffusion_model' ? 'flux' : undefined,
          )
        : undefined,
  })),
)
function availability(id: SimpleTemplateId): string {
  if (loading.value) return '檢查中'
  if (!engine.value || engine.value.url !== engineUrl.value) return '狀態未知'
  if (!engine.value.connected) return '引擎離線'
  if (id === 'flux') {
    if (!fluxCatalog.value?.synced_at || fluxCatalog.value.sync_error) return '元件清單待同步'
    return fluxMatches.value.every((part) => part.model) ? '可載入配方' : '缺少相符元件登記'
  }
  if (!catalog.value?.synced_at || catalog.value.sync_error) return '模型清單待同步'
  return modelFor(id) ? '可載入配方' : '缺少相符模型登記'
}
const canLoad = computed(() => availability(selectedId.value) === '可載入配方' && !locked.value)

async function refresh(explicit = false) {
  if (!active || loading.value) return
  const read = reads.begin()
  loading.value = true
  error.value = ''
  profile.value = null
  try {
    const settings = await apiJson<{ comfy_url: string }>('settings', { signal: read.signal })
    const results = await Promise.allSettled([
      apiJson<EngineReport>('engine', { signal: read.signal }),
      apiJson<Catalog>('models', { signal: read.signal }),
      apiJson<FluxCatalog>('flux/components', { signal: read.signal }),
      apiJson<Capabilities>('engine/capabilities' + (explicit ? '/sync' : ''), {
        method: explicit ? 'POST' : 'GET',
        signal: read.signal,
      }),
    ])
    const latest = await apiJson<{ comfy_url: string }>('settings', { signal: read.signal })
    if (!read.isCurrent()) return
    if (latest.comfy_url !== settings.comfy_url)
      throw new Error('引擎設定已變更，請重新檢查；目前描述已保留。')
    engineUrl.value = latest.comfy_url
    engine.value = results[0].status === 'fulfilled' ? results[0].value : null
    catalog.value = results[1].status === 'fulfilled' ? results[1].value : null
    fluxCatalog.value = results[2].status === 'fulfilled' ? results[2].value : null
    capabilities.value = results[3].status === 'fulfilled' ? results[3].value : null
    if (engine.value?.diagnostics?.matches_selected_engine === false) engine.value = null
    if (catalog.value?.engine_url !== engineUrl.value) catalog.value = null
    if (fluxCatalog.value?.engine_url !== engineUrl.value) fluxCatalog.value = null
    if (results.some((result) => result.status === 'rejected'))
      error.value = '部分可用狀態讀取失敗，請重新檢查；無法確認的項目不會視為就緒。'
    if (loadedId.value && selected.value.family === 'checkpoint') await refreshProfile()
    if (previewJob.value && !previewTemplateJob.value) void preview(previewJob.value)
  } catch (cause) {
    if (read.isCurrent()) {
      engine.value = null
      catalog.value = null
      fluxCatalog.value = null
      capabilities.value = null
      error.value = cause instanceof Error ? cause.message : '無法讀取可用狀態。'
    }
  } finally {
    if (read.isCurrent()) loading.value = false
  }
}
async function refreshProfile() {
  const read = profiles.begin()
  const model = modelFor(selectedId.value)
  profile.value = null
  if (!model) return null
  const query = new URLSearchParams({ engine_url: engineUrl.value, name: model.name })
  const result = validateProfile(
    await apiJson<ModelProfile>('models/profile?' + query, { signal: read.signal }),
  )
  if (!read.isCurrent()) return null
  if (
    result.engine_url !== engineUrl.value ||
    result.name !== model.name ||
    result.preset?.id !== selected.value.presetId ||
    !result.compatibility.allows_submission
  )
    throw new Error('模型預設與此配方不符，請到模型庫核對登記；目前內容已保留。')
  profile.value = result
  return result
}
function selectTemplate(id: SimpleTemplateId) {
  if (locked.value || loading.value || id === selectedId.value) return
  if (unsaved.value && !window.confirm('切換配方會取代簡易創作的未保存設定，確定切換？')) return
  profiles.cancel()
  selectedId.value = id
  loadedId.value = null
  editing.value = false
  baseline.value = ''
  profile.value = null
  message.value = ''
  error.value = ''
  previewJob.value = null
  previewReads.cancel()
  previewTemplate.value = null
  previewTemplateJob.value = ''
}
async function loadTemplate(edit = false) {
  if (!canLoad.value || loading.value) return
  if (unsaved.value && !window.confirm('重新載入配方會取代目前設定，確定載入？')) return
  loading.value = true
  const epoch = ++templateEpoch
  error.value = ''
  try {
    const template = selected.value
    if (template.family === 'flux') {
      const parts = Object.fromEntries(
        fluxMatches.value.map((part) => [part.role, part.model!.name]),
      )
      Object.assign(flux, newFlux(engineUrl.value), parts, {
        title: template.title,
        prompt: template.prompt,
        seed: template.seed,
        weight_dtype: 'fp8_e4m3fn',
        encoder_device: 'cpu',
      })
    } else {
      const result = await refreshProfile()
      if (!active || epoch !== templateEpoch || !result?.preset) return
      Object.assign(checkpoint, newCreation(), result.preset.settings, {
        engine_url: engineUrl.value,
        checkpoint: result.name,
        title: template.title,
        prompt: template.prompt,
        negative_prompt: template.negative,
        seed: template.seed,
      })
    }
    loadedId.value = template.id
    editing.value = edit
    baseline.value = JSON.stringify(form.value)
    message.value = edit
      ? '已套用配方，可修改英文描述後生成。'
      : '原配方已載入。可直接生成，或按「編輯描述」修改。'
    if (edit) await editDescription()
  } catch (cause) {
    if (active && epoch === templateEpoch)
      error.value = cause instanceof Error ? cause.message : '配方載入失敗。'
  } finally {
    if (active && epoch === templateEpoch) loading.value = false
  }
}
const blockers = computed<PreflightBlocker[]>(() => {
  const issues: PreflightBlocker[] = []
  if (!loadedId.value) issues.push({ message: '請先載入一份起始配方。' })
  if (!engine.value?.connected || engine.value.url !== engineUrl.value)
    issues.push({ message: '引擎離線或狀態未知，請確認連線後重新檢查。', action: 'settings' })
  if (form.value.engine_url && form.value.engine_url !== engineUrl.value)
    issues.push({ message: '配方來自不同引擎，請核對後重新載入配方。', action: 'settings' })
  if (availability(selectedId.value) !== '可載入配方')
    issues.push({
      message: availability(selectedId.value) + '；請在模型庫同步並核對架構及 SHA256。',
      action: 'models',
    })
  if (selected.value.family === 'checkpoint' && loadedId.value && !profile.value)
    issues.push({ message: '模型預設尚未確認，請重新檢查。', action: 'refresh' })
  if (
    selected.value.family === 'checkpoint' &&
    loadedId.value &&
    (!capabilities.value?.available ||
      capabilities.value.stale ||
      !capabilities.value.engine_matches ||
      capabilities.value.engine_url !== engineUrl.value)
  )
    issues.push({ message: '原引擎取樣選項尚未確認或已過期，請重新檢查。', action: 'refresh' })
  if (
    loadedId.value &&
    selected.value.family === 'checkpoint' &&
    modelFor(selectedId.value)?.name !== checkpoint.checkpoint
  )
    issues.push({ message: '配方模型已不在相符登記中，請核對後重新載入。', action: 'models' })
  if (
    loadedId.value &&
    selected.value.family === 'flux' &&
    fluxMatches.value.some((part) => part.model?.name !== flux[part.role])
  )
    issues.push({ message: '配方元件登記已變更，請核對後重新載入。', action: 'models' })
  return issues
})
const fieldProblems = computed(() => {
  const c = capabilities.value
  const reliable =
    c?.available && c.engine_matches && !c.stale && c.engine_url === form.value.engine_url
  return generationFieldProblems(
    form.value,
    selected.value.family === 'checkpoint' && reliable
      ? { bounds: c.bounds, samplers: c.sampler_names, schedulers: c.schedulers }
      : {},
  )
})
function randomSeed() {
  const words = crypto.getRandomValues(new Uint32Array(2))
  form.value.seed = ((BigInt(words[0]!) << 32n) | BigInt(words[1]!)).toString()
  message.value = '已更換 Seed；按「生成圖片」才會建立新任務。'
}
function transfer() {
  if (!loadedId.value || locked.value || loading.value) return
  emit('advanced', JSON.parse(JSON.stringify(form.value)), selection.value)
}
async function saveResult() {
  const job = previewJob.value
  if (!job || job.status !== 'completed' || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const result = await apiJson<{
      imported: unknown[]
      existing: unknown[]
      errors: { message: string }[]
    }>('jobs/' + job.id + '/artworks', { method: 'POST' })
    if (result.errors.length) throw new Error(result.errors.map((item) => item.message).join('；'))
    if (!result.imported.length && !result.existing.length)
      throw new Error('此任務沒有可保存的結果。')
    savedJob.value = job.id
    previewRevision.value++
    message.value = '結果已存入作品庫，可離線查看。'
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : '保存結果無法確認，請到作品庫查看原任務。'
  } finally {
    saving.value = false
  }
}
async function restoreJob(id: string) {
  if (locked.value || loading.value) return
  loading.value = true
  error.value = ''
  const read = restores.begin()
  try {
    const prefix = selected.value.family === 'flux' ? 'flux/' : ''
    const value = await apiJson<{
      settings: CreationForm | FluxForm
      template_context?: TemplateContext | null
    }>(prefix + 'jobs/' + id + '/creation-settings', { signal: read.signal })
    if (read.isCurrent())
      emit('advanced', value.settings, templateSelection(value.template_context))
  } catch (cause) {
    if (read.isCurrent())
      error.value = cause instanceof Error ? cause.message : '無法載入原任務設定。'
  } finally {
    if (read.isCurrent()) loading.value = false
  }
}
let mounted = false
onMounted(() => {
  mounted = true
  void refresh()
})
onActivated(() => {
  active = true
  if (mounted && !loading.value) void refresh()
})
onDeactivated(() => {
  active = false
  ++templateEpoch
  reads.cancel()
  profiles.cancel()
  restores.cancel()
  previewReads.cancel()
  previewTemplateJob.value = ''
  loading.value = false
})
onBeforeUnmount(() => {
  active = false
  ++templateEpoch
  reads.dispose()
  profiles.dispose()
  restores.dispose()
  previewReads.dispose()
})
</script>

<template>
  <div class="simple-creation">
    <div class="simple-intro">
      <div><h2>從一份配方開始創作</h2><p>選配方 → 修改描述 → 生成 → 存入作品庫</p></div>
      <button class="secondary" :disabled="loading || locked" @click="refresh(true)"
        >重新檢查</button
      >
    </div>
    <ol class="simple-steps" aria-label="創作進度">
      <li
        v-for="(label, index) in ['選擇配方', '確認或修改描述', '生成圖片', '保存成果']"
        :key="label"
        :aria-current="step === index + 1 ? 'step' : undefined"
        :class="{ reached: step >= index + 1 }"
      >
        <span>{{ index + 1 }}</span
        >{{ label }}
      </li>
    </ol>
    <div class="simple-cards" role="group" aria-label="起始配方">
      <button
        v-for="item in simpleTemplates"
        :key="item.id"
        type="button"
        class="simple-card"
        :aria-pressed="selectedId === item.id"
        :disabled="loading || locked"
        @click="selectTemplate(item.id)"
      >
        <span class="simple-card-model">{{ item.model }}</span
        ><strong>{{ item.title }}</strong> <span>{{ item.description }}</span
        ><small>{{ availability(item.id) }}</small>
      </button>
    </div>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <p v-if="message" class="notice" role="status">{{ message }}</p>
    <div class="simple-workbench">
      <section class="simple-editor panel" aria-label="簡易創作設定">
        <h3>{{ selected.title }}</h3
        ><p>{{ selected.note }}</p>
        <p class="footnote">本版提供起始配方，尚未附真實範例圖；載入不會下載模型或自動生成。</p>
        <button class="primary" :disabled="!canLoad || loading" @click="loadTemplate(false)">
          {{ loadedId ? '還原配方設定' : '載入起始配方' }}
        </button>
        <button
          v-if="!loadedId"
          class="secondary simple-edit-entry"
          :disabled="!canLoad || loading"
          @click="loadTemplate(true)"
          >套用後修改</button
        >
        <button
          v-else-if="!editing"
          class="secondary simple-edit-entry"
          :disabled="locked || loading"
          @click="editDescription"
          >編輯描述</button
        >
        <div v-if="availability(selectedId) !== '可載入配方' && !loading" class="simple-repair">
          <strong>還需要完成</strong>
          <ul
            ><li v-for="item in requirements()" :key="item.key"
              ><span>{{ item.label }}</span>
              <button
                class="secondary"
                :disabled="loading || locked"
                @click="repair(item.action)"
                >{{
                  item.action === 'models'
                    ? '前往對應模型分類'
                    : item.action === 'settings'
                      ? '連線設定'
                      : '重新檢查'
                }}</button
              >
            </li></ul
          >
        </div>
        <fieldset :disabled="!loadedId || loading || locked">
          <label for="simple-prompt">實際生成提示詞（英文）</label>
          <textarea
            id="simple-prompt"
            v-model="form.prompt"
            :readonly="!editing"
            v-field-error:prompt="fieldProblems.prompt"
            rows="7"
            maxlength="20000"
            aria-describedby="simple-language"
          />
          <p id="simple-language" class="footnote"
            >直接修改英文提示詞。此處沒有自動翻譯；上方中文是配方說明。</p
          >
          <p v-if="loadedId && !editing" class="footnote"
            >目前保留原配方描述。要修改時按「編輯描述」；還原配方會恢復描述與固定 Seed。</p
          >
          <p class="simple-size">輸出比例：正方形 1:1 · {{ form.width }} × {{ form.height }}</p>
          <p class="footnote">首版保留配方尺寸；其他比例可帶到進階工作台調整。</p>
          <p v-if="loadedId" role="status">{{
            modified ? '已修改配方，不沿用原配置的驗收結論。' : '使用原始配方設定。'
          }}</p>
          <div class="simple-actions">
            <button class="secondary" @click="randomSeed">換 Seed，準備再畫一張</button>
            <button class="secondary" @click="transfer">帶到進階工作台</button>
          </div>
        </fieldset>
        <details v-if="loadedId" class="simple-recipe"
          ><summary>查看完整設定</summary>
          <p class="footnote">配方版本 v1 · {{ selected.note }} · 登記匹配不代表目前權重已驗檔。</p>
          <p v-if="profile?.preset" class="footnote">{{ profile.preset.validation }}</p>
          <pre>{{ JSON.stringify(form, null, 2) }}</pre>
        </details>
        <p v-if="loadedId" class="footnote"
          >設定會在站內切頁時保留；重新整理前可帶到進階工作台保存草稿。</p
        >
        <div id="simple-submit" class="simple-submit"></div>
      </section>
      <div class="simple-stage">
        <p v-if="previewJob && loadedId && !resultMatchesForm" class="notice" role="status"
          >右側仍為既有任務結果，不代表目前表單的成果；修改描述不會更新舊圖。</p
        >
        <StudioPreview
          :key="selected.family + ':' + previewRevision"
          :job="previewJob"
          :width="form.width"
          :height="form.height"
          :family="previewJob?.checkpoint || selected.model"
          title="簡易創作"
          @gallery="emit('gallery', $event)"
        />
        <div v-if="previewJob?.status === 'completed'" class="simple-result-actions">
          <button
            class="primary"
            :disabled="saving || savedJob === previewJob.id"
            @click="saveResult"
          >
            {{ saving ? '保存中…' : savedJob === previewJob.id ? '已存入作品庫' : '存入作品庫' }}
          </button>
          <button class="secondary" @click="emit('gallery', previewJob.id)">查看作品庫</button>
        </div>
        <TemplateSnapshot :item="previewTemplate" />
        <GenerationPanel
          :key="selected.family"
          preview-stage
          submit-target="#simple-submit"
          :form="form"
          :template-selection="selection"
          :workflow="selected.family === 'flux' ? 'flux' : undefined"
          :field-problems="fieldProblems"
          :blockers="blockers"
          :blocked-reason="blockers[0]?.message"
          :disabled="loading || saving"
          @preview="preview"
          @submitted="submitted"
          @busy="generating = $event"
          @pending="pending = $event"
          @refresh-options="refresh(true)"
          @gallery="emit('gallery', $event)"
          @restore-job="restoreJob"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.simple-creation {
  max-width: 1500px;
  margin: auto;
  padding: 24px;
}
.simple-steps {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  padding: 0;
  margin: 0 0 20px;
  list-style: none;
}
.simple-steps li {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink2);
}
.simple-steps li[aria-current='step'] {
  color: var(--accent);
  font-weight: 600;
}
.simple-steps span {
  display: grid;
  place-items: center;
  border: 1px solid var(--line2);
  border-radius: 50%;
  width: 26px;
  height: 26px;
}
.simple-steps .reached span {
  border-color: var(--accent);
}
.simple-edit-entry {
  margin: 8px 0 0 8px;
}
.simple-repair ul {
  padding-left: 18px;
}
.simple-repair li {
  margin-block: 12px;
  overflow-wrap: anywhere;
}
.simple-repair li span {
  display: block;
  margin-bottom: 8px;
}
.simple-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.simple-intro h2 {
  margin: 0 0 6px;
}
.simple-intro p {
  margin: 0;
  color: var(--ink2);
}
.simple-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.simple-card {
  display: flex;
  flex-direction: column;
  text-align: left;
  gap: 10px;
  padding: 18px;
  border: 1px solid var(--line2);
  border-radius: 12px;
  background: var(--panel);
  color: var(--ink);
}
.simple-card[aria-pressed='true'] {
  border-color: var(--accent);
  background: var(--asoft);
  box-shadow: inset 0 0 0 1px var(--accent);
}
.simple-card strong {
  font-size: 18px;
}
.simple-card-model,
.simple-card small {
  color: var(--ink2);
  font-size: 12px;
}
.simple-card span {
  line-height: 1.6;
}
.simple-workbench {
  display: grid;
  grid-template-columns: minmax(280px, 390px) minmax(0, 1fr);
  gap: 24px;
}
.simple-editor,
.simple-stage {
  min-width: 0;
}
.simple-editor h3 {
  margin-top: 0;
}
.simple-editor fieldset {
  border: 0;
  padding: 0;
  margin: 22px 0 0;
  min-width: 0;
}
.simple-editor label {
  display: block;
  margin-bottom: 10px;
}
.simple-editor textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
}
.simple-size {
  font-weight: 600;
}
.simple-actions,
.simple-result-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin: 16px 0;
}
.simple-repair {
  margin: 14px 0;
}
.simple-repair button {
  margin: 0 8px 8px 0;
}
.simple-recipe {
  margin-top: 20px;
}
.simple-recipe pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 360px;
  overflow: auto;
  font-size: 12px;
}
.simple-submit {
  margin-top: 20px;
}
.simple-stage :deep(.studio-preview) {
  min-height: 320px;
  height: 480px;
}
@media (max-width: 900px) {
  .simple-creation {
    padding: 16px;
  }
  .simple-workbench {
    grid-template-columns: 1fr;
  }
  .simple-cards {
    grid-template-columns: 1fr;
  }
  .simple-intro {
    align-items: flex-start;
  }
  .simple-stage :deep(.studio-preview) {
    height: 360px;
    min-height: 220px;
  }
}
</style>
