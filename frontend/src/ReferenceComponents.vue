<script setup lang="ts">
import { reactive, ref, watch, onBeforeUnmount, onDeactivated } from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'
import { parseFileSize, type Architecture } from './modelMetadata'
import { referenceRoles, type ReferenceCatalog, type ReferenceComponent } from './adapterSettings'

const props = defineProps<{
  library: ReferenceCatalog | null
  engineUrl: string
  disabled: boolean
  managed?: boolean
}>()
const emit = defineEmits<{ updated: []; busy: [value: boolean]; editing: [value: boolean] }>()
const selected = ref(''),
  busy = ref(false),
  error = ref(''),
  message = ref('')
const edits = reactive({
  architecture: 'unknown' as Architecture,
  family: 'unknown',
  version: '',
  sha256: '',
  size: '',
  source_url: '',
  license_name: '',
  license_url: '',
  notes: '',
})
const reads = createRequestScope()
watch(busy, (v) => emit('busy', v), { flush: 'sync' })
const metadataPanel = ref<HTMLDetailsElement | null>(null)
watch(selected, (value) => emit('editing', !!value), { flush: 'sync' })
function editComponent(item: ReferenceComponent) {
  selected.value = key(item)
  choose()
  if (metadataPanel.value) {
    metadataPanel.value.open = true
    metadataPanel.value.scrollIntoView({ block: 'nearest' })
  }
}
defineExpose({ editComponent })
const key = (r: ReferenceComponent) => JSON.stringify([r.role, r.name])
function choose() {
  const r = props.library?.components.find((r) => key(r) === selected.value)
  if (!r) return
  Object.assign(edits, {
    architecture: r.architecture || 'unknown',
    family: r.family || 'unknown',
    version: r.version || '',
    sha256: r.sha256 || '',
    size: r.size_bytes == null ? '' : String(r.size_bytes),
    source_url: r.source_url || '',
    license_name: r.license_name || '',
    license_url: r.license_url || '',
    notes: r.notes || '',
  })
  message.value = ''
}
watch(
  () => props.engineUrl,
  () => {
    reads.cancel()
    selected.value = ''
    busy.value = false
    error.value = ''
    message.value = ''
  },
)
async function change(sync: boolean) {
  if (props.disabled || busy.value || !props.engineUrl) return
  const request = reads.begin(),
    engine = props.engineUrl
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    const r = props.library?.components.find((r) => key(r) === selected.value)
    if (!sync && !r) throw new Error('請選擇要登記的元件。')
    const body = sync
      ? { comfy_url: engine }
      : {
          engine_url: engine,
          role: r!.role,
          name: r!.name,
          ...edits,
          size_bytes: parseFileSize(edits.size),
        }
    if ('size' in body) delete (body as Record<string, unknown>).size
    const result = await apiJson<ReferenceCatalog>(
      '/api/reference-components/' + (sync ? 'sync' : 'metadata'),
      {
        method: sync ? 'POST' : 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: request.signal,
      },
    )
    if (!request.isCurrent() || engine !== props.engineUrl) return
    if (result.engine_url !== engine || result.sync_error)
      throw new Error(result.sync_error || '回傳引擎不同，請重新載入。')
    message.value = sync
      ? '參考元件清單已同步；仍需手動登記架構與家族。'
      : '元件登記已保存；不代表已驗證權重。'
    emit('updated')
  } catch (cause) {
    if (request.isCurrent() && !request.signal.aborted)
      error.value = cause instanceof Error ? cause.message : '更新失敗'
  } finally {
    if (request.isCurrent()) busy.value = false
  }
}
onDeactivated(() => {
  reads.cancel()
  busy.value = false
})
onBeforeUnmount(reads.dispose)
</script>
<template>
  <details ref="metadataPanel" class="panel component-editor">
    <summary>同步與登記參考元件</summary>
    <p>先安裝固定節點與權重，再同步清單。登記是人工來源紀錄；不讀取或下載權重。</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="library?.sync_error" class="notice warning">{{ library.sync_error }}</p>
    <button
      type="button"
      class="secondary"
      :disabled="disabled || busy || !engineUrl"
      v-if="!managed"
      @click="change(true)"
      >同步 adapter 與編碼器清單</button
    >
    <fieldset :disabled="disabled || busy">
      <label for="reference-metadata-component">登記元件</label>
      <select id="reference-metadata-component" v-model="selected" @change="choose">
        <option value="">選擇已同步元件</option>
        <option v-for="r in library?.components" :key="key(r)" :value="key(r)"
          >{{ referenceRoles.find((s) => s.role === r.role)?.label }} · {{ r.name
          }}{{ r.listed ? '' : '（已不在清單）' }}</option
        >
      </select>
      <template v-if="selected"
        ><button type="button" class="secondary" :disabled="busy" @click="selected = ''"
          >結束元件編輯</button
        >
        <label for="reference-metadata-family">元件家族</label
        ><select id="reference-metadata-family" v-model="edits.family"
          ><option value="unknown">未知</option
          ><option value="sdxl-plus-vit-h">SDXL Plus ViT-H adapter</option
          ><option value="clip-vit-h-14">CLIP Vision ViT-H/14</option
          ><option value="other">其他</option></select
        >
        <label for="reference-metadata-architecture">架構</label
        ><select id="reference-metadata-architecture" v-model="edits.architecture"
          ><option value="unknown">未知</option
          ><option value="sdxl">SDXL（adapter）</option
          ><option value="other">其他（ViT-H 編碼器）</option></select
        >
        <label for="reference-metadata-version">版本</label
        ><input id="reference-metadata-version" v-model="edits.version" maxlength="100" />
        <label for="reference-metadata-hash">SHA256</label
        ><input id="reference-metadata-hash" v-model="edits.sha256" maxlength="64" />
        <label for="reference-metadata-size">檔案大小（bytes）</label
        ><input id="reference-metadata-size" v-model="edits.size" inputmode="numeric" />
        <label for="reference-metadata-source">來源 URL</label
        ><input
          id="reference-metadata-source"
          v-model="edits.source_url"
          maxlength="2048"
          type="url"
        />
        <label for="reference-metadata-license">授權名稱</label
        ><input id="reference-metadata-license" v-model="edits.license_name" maxlength="200" />
        <label for="reference-metadata-license-url">授權 URL</label
        ><input
          id="reference-metadata-license-url"
          v-model="edits.license_url"
          maxlength="2048"
          type="url"
        />
        <label for="reference-metadata-notes">備註</label
        ><textarea id="reference-metadata-notes" v-model="edits.notes" maxlength="4000" rows="3" />
        <button type="button" class="secondary" @click="change(false)">保存參考元件登記</button>
      </template>
    </fieldset>
  </details>
</template>
<style scoped>
.component-editor {
  margin: 18px 0;
  line-height: 1.8;
  font-size: 13px;
  overflow-wrap: anywhere;
}
summary {
  cursor: pointer;
  font-weight: 600;
}
fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
label {
  display: block;
  margin: 14px 0 6px;
}
input,
select,
textarea {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  font: inherit;
  color: var(--text-primary);
  background: var(--surface-input);
  border: 1px solid var(--border-control);
  border-radius: 7px;
  padding: 10px;
}
button {
  margin-top: 14px;
}
</style>
