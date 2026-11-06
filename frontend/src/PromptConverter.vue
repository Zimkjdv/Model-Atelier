<script setup lang="ts">
import {
  computed,
  nextTick,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  ref,
  useId,
  watch,
} from 'vue'
import { api } from './apiClient'
import { createRequestScope } from './requestScope'
import { useUnsavedChanges } from './unsavedChanges'
import UiIcon from './UiIcon.vue'

type Settings = { base_url: string; model: string }
type Result = Settings & { prompt: string; elapsed_ms: number }
const props = withDefaults(
  defineProps<{
    currentPrompt: string
    editorId: string
    contextKey: string
    profile?: 'general' | 'pony' | 'animagine' | 'flux'
    disabled?: boolean
    readOnly?: boolean
  }>(),
  { profile: 'general', disabled: false, readOnly: false },
)
const emit = defineEmits<{ apply: [prompt: string] }>()
const uid = useId()
const dialog = ref<HTMLDialogElement | null>(null)
const source = ref(''),
  terms = ref('')
const style = ref<'natural' | 'tags'>(
  props.profile === 'pony' || props.profile === 'animagine' ? 'tags' : 'natural',
)
const baseUrl = ref('http://127.0.0.1:11434'),
  model = ref('qwen3.5:2b')
const savedSettings = ref(''),
  ready = ref(false),
  loading = ref(false),
  busy = ref(false)
const result = ref<Result | null>(null),
  error = ref(''),
  message = ref(''),
  status = ref('')
const applied = ref('')
const configuration = computed(() => ({ base_url: baseUrl.value, model: model.value }))
const configChanged = computed(() => JSON.stringify(configuration.value) !== savedSettings.value)
const inputSignature = computed(() => JSON.stringify([source.value, terms.value, style.value]))
useUnsavedChanges(
  computed(
    () =>
      !!result.value ||
      (ready.value && configChanged.value) ||
      ((!!source.value || !!terms.value) && inputSignature.value !== applied.value),
  ),
)
const reads = createRequestScope(),
  conversions = createRequestScope()
let active = true
function invalidate() {
  conversions.cancel()
  busy.value = false
  result.value = null
  message.value = ''
}
watch(
  () => [
    source.value,
    terms.value,
    style.value,
    props.currentPrompt,
    props.contextKey,
    props.profile,
    props.disabled,
    props.readOnly,
    baseUrl.value,
    model.value,
  ],
  invalidate,
  { flush: 'sync' },
)
watch(
  () => props.disabled || props.readOnly,
  (locked) => {
    if (locked) closeDialog()
  },
  { flush: 'sync' },
)
watch(
  () => props.profile,
  (value) => {
    style.value = value === 'pony' || value === 'animagine' ? 'tags' : 'natural'
  },
)
watch(
  configuration,
  () => {
    status.value = ''
    reads.cancel()
    loading.value = false
  },
  { flush: 'sync' },
)
async function settings(save = false) {
  if (loading.value || busy.value) return
  const read = reads.begin()
  loading.value = true
  error.value = ''
  if (save) invalidate()
  try {
    const value = await api<Settings>(
      'prompt-converter/settings',
      save ? 'PUT' : 'GET',
      save ? configuration.value : undefined,
      read.signal,
    )
    if (!read.isCurrent() || !active) return
    // Assignment can trigger the configuration watcher, so finish the read first.
    loading.value = false
    baseUrl.value = value.base_url
    model.value = value.model
    savedSettings.value = JSON.stringify(value)
    ready.value = true
    if (save) message.value = '已保存本機 LLM 設定。'
  } catch (cause) {
    if (read.isCurrent()) error.value = cause instanceof Error ? cause.message : '設定讀取失敗。'
  } finally {
    if (read.isCurrent()) loading.value = false
  }
}
async function check() {
  if (loading.value || busy.value || configChanged.value || !ready.value) return
  const read = reads.begin()
  loading.value = true
  error.value = ''
  status.value = ''
  try {
    const value = await api<Settings & { available: boolean }>(
      'prompt-converter/status',
      'GET',
      undefined,
      read.signal,
    )
    if (read.isCurrent() && active) status.value = `本機模型可用：${value.model}`
  } catch (cause) {
    if (read.isCurrent()) error.value = cause instanceof Error ? cause.message : '連線檢查失敗。'
  } finally {
    if (read.isCurrent()) loading.value = false
  }
}
async function convert() {
  if (
    busy.value ||
    loading.value ||
    props.disabled ||
    props.readOnly ||
    !source.value.trim() ||
    !ready.value ||
    configChanged.value
  )
    return
  const read = conversions.begin()
  const signature = JSON.stringify([
    inputSignature.value,
    props.contextKey,
    props.currentPrompt,
    props.profile,
  ])
  busy.value = true
  result.value = null
  error.value = ''
  message.value = ''
  try {
    const value = await api<Result>(
      'prompt-converter/convert',
      'POST',
      {
        description: source.value,
        style: style.value,
        profile: props.profile,
        protected_terms: terms.value
          .split('\n')
          .map((term) => term.trim())
          .filter(Boolean),
      },
      read.signal,
    )
    if (
      !read.isCurrent() ||
      !active ||
      props.disabled ||
      signature !==
        JSON.stringify([inputSignature.value, props.contextKey, props.currentPrompt, props.profile])
    )
      return
    if (
      !value ||
      typeof value.prompt !== 'string' ||
      !value.prompt.trim() ||
      value.prompt.length > 20000 ||
      typeof value.model !== 'string' ||
      !Number.isFinite(value.elapsed_ms)
    )
      throw new Error('轉換回覆格式無效，原提示詞已保留。')
    result.value = value
  } catch (cause) {
    if (read.isCurrent()) error.value = cause instanceof Error ? cause.message : '轉換失敗。'
  } finally {
    if (read.isCurrent()) busy.value = false
  }
}
async function apply() {
  if (!result.value?.prompt.trim() || busy.value || props.disabled || props.readOnly) return
  const prompt = result.value.prompt
  applied.value = inputSignature.value
  emit('apply', prompt)
  result.value = null
  closeDialog()
  await nextTick()
  if (active && props.currentPrompt === prompt) message.value = '已套用英文，可繼續編輯。'
}
function openDialog() {
  if (props.disabled || props.readOnly || !dialog.value || dialog.value.open) return
  dialog.value.showModal()
  void settings()
}
function cancelWaiting() {
  conversions.cancel()
  reads.cancel()
  busy.value = false
  loading.value = false
}
function closeDialog() {
  dialog.value?.close()
  cancelWaiting()
}
function deactivate() {
  active = false
  closeDialog()
  invalidate()
  reads.cancel()
  loading.value = false
}
onActivated(() => {
  if (!active) {
    active = true
  }
})
onDeactivated(deactivate)
onBeforeUnmount(() => {
  deactivate()
  reads.dispose()
  conversions.dispose()
})
</script>

<template>
  <section class="prompt-converter prompt-editor" :data-converter="uid">
    <div class="prompt-editor-toolbar">
      <label :for="editorId" class="prompt-editor-title"
        >實際生成提示詞 <span aria-hidden="true">EN</span></label
      >
      <button
        v-if="!readOnly"
        type="button"
        class="secondary prompt-editor-assist"
        :disabled="disabled"
        @click="openDialog"
      >
        <UiIcon name="studio" :size="14" />中文轉英文
      </button>
    </div>
    <slot />
    <div :id="editorId + '-hint'" class="prompt-editor-caption">
      <span v-if="message" class="prompt-editor-applied" role="status"
        ><UiIcon name="check" :size="13" />{{ message }}</span
      >
      <span v-else>生成時使用這段英文。</span>
      <span class="prompt-editor-count">{{ currentPrompt.length.toLocaleString() }} / 20,000</span>
    </div>
    <dialog
      ref="dialog"
      class="converter-dialog"
      :aria-labelledby="uid + '-title'"
      :aria-describedby="uid + '-intro'"
      @cancel.prevent="closeDialog"
      @close="cancelWaiting"
    >
      <header class="converter-header">
        <div>
          <h2 :id="uid + '-title'"><UiIcon name="studio" :size="18" />提示詞助手</h2>
          <p :id="uid + '-intro'">轉成英文、確認內容，再套用到生成提示詞。</p>
        </div>
        <button
          type="button"
          class="secondary converter-close"
          aria-label="關閉中文轉換器"
          @click="closeDialog"
          >×</button
        >
      </header>
      <div class="converter-body">
        <div class="converter-compose">
          <div class="converter-column">
            <div class="converter-field-heading"
              ><label :for="uid + '-source'">中文畫面描述</label
              ><span>{{ source.length }} / 2,000</span></div
            >
            <textarea
              :id="uid + '-source'"
              v-model="source"
              class="converter-textarea"
              rows="5"
              maxlength="2000"
              autofocus
              placeholder="例如：一隻黑貓坐在窗邊，水彩風格，不戴項圈。"
            />
            <div class="converter-source-actions">
              <button
                type="button"
                class="primary converter-translate"
                :disabled="busy || loading || disabled || !source.trim() || !ready || configChanged"
                @click="convert"
              >
                <UiIcon
                  :name="busy ? 'refresh' : 'studio'"
                  :size="15"
                  :class="{ 'converter-spinning': busy }"
                />{{ busy ? '正在轉換…' : '轉成英文提示詞' }}
              </button>
              <button v-if="busy" type="button" class="secondary" @click="invalidate"
                >取消等待</button
              >
            </div>
          </div>
          <div class="converter-column">
            <div class="converter-field-heading">
              <label v-if="result" :for="uid + '-preview'">英文提示詞預覽（可修改）</label
              ><span v-else class="converter-output-title">英文轉換結果</span>
              <span v-if="result" class="converter-pending">待套用</span>
            </div>
            <template v-if="result">
              <textarea
                :id="uid + '-preview'"
                v-model="result.prompt"
                class="converter-textarea converter-preview"
                rows="5"
                maxlength="20000"
              />
              <p class="converter-result-meta"
                >{{ result.model }} · {{ (result.elapsed_ms / 1000).toFixed(1) }} 秒</p
              >
            </template>
            <div v-else class="converter-output-empty" role="status">
              <span class="converter-language-mark" aria-hidden="true">EN</span>
              <strong>{{ busy ? '正在整理英文提示詞…' : '英文結果會顯示在這裡' }}</strong>
              <span>{{
                busy ? '首次載入可能需要多等一會兒。' : '轉換後可以修改，再決定是否套用。'
              }}</span>
            </div>
          </div>
        </div>
        <p v-if="error" role="alert" class="converter-error">{{ error }}</p>
        <p v-if="configChanged && ready" class="converter-error"
          >LLM 設定已修改，請先保存再轉換。</p
        >
        <details class="converter-disclosure converter-options">
          <summary
            ><span class="converter-chevron" aria-hidden="true">›</span>格式與保留詞<span
              class="converter-summary-meta"
              >{{ style === 'tags' ? '動漫標籤' : '自然英文' }}</span
            ></summary
          >
          <div class="converter-option-fields">
            <div class="converter-field">
              <label :for="uid + '-style'">英文格式</label>
              <select :id="uid + '-style'" v-model="style"
                ><option value="natural">自然英文（一般／FLUX）</option
                ><option value="tags">逗號標籤（動漫模型）</option></select
              >
            </div>
            <div class="converter-field">
              <label :for="uid + '-terms'">必須保留的觸發詞（選填，每行一個）</label>
              <textarea
                :id="uid + '-terms'"
                v-model="terms"
                class="converter-terms"
                rows="2"
                maxlength="3000"
                placeholder="LoRA 觸發詞或不可翻譯的名稱"
              />
              <p class="converter-help"
                >保留詞會原樣加入英文結果；原英文中需要留下的詞也請填在這裡。</p
              >
            </div>
          </div>
          <p v-if="profile === 'pony'" class="converter-help"
            >Pony 品質前綴由程式加入：score_9, score_8_up, score_7_up。</p
          >
        </details>
        <details class="converter-disclosure converter-settings">
          <summary
            ><span class="converter-chevron" aria-hidden="true">›</span>本機 LLM 設定<span
              class="converter-summary-meta"
              >{{ model }}</span
            ></summary
          >
          <div class="converter-setting-fields">
            <div class="converter-field"
              ><label :for="uid + '-url'">Ollama 服務網址</label
              ><input
                :id="uid + '-url'"
                v-model="baseUrl"
                maxlength="200"
                :disabled="loading || busy"
                @keydown.enter.prevent
            /></div>
            <div class="converter-field"
              ><label :for="uid + '-model'">已安裝模型名稱</label
              ><input
                :id="uid + '-model'"
                v-model="model"
                maxlength="150"
                :disabled="loading || busy"
                @keydown.enter.prevent
            /></div>
          </div>
          <div class="converter-setting-actions">
            <button
              type="button"
              class="secondary"
              :disabled="loading || busy"
              @click="settings(true)"
              >保存 LLM 設定</button
            >
            <button
              type="button"
              class="secondary"
              :disabled="loading || busy || configChanged || !ready"
              @click="check"
              >檢查連線與模型</button
            >
            <button type="button" class="secondary" :disabled="loading || busy" @click="settings()"
              >重新讀取設定</button
            >
          </div>
          <p v-if="message" role="status" class="converter-help">{{ message }}</p>
          <p v-if="status" role="status" class="converter-help">{{ status }}</p>
          <p class="converter-help"
            >僅連接本機 Ollama。首次使用先安裝，再執行
            <code>ollama pull qwen3.5:2b</code>。設定由各工作台共用。</p
          >
          <p class="converter-help">CPU 執行、完成後卸載；最多等待 120 秒。</p>
        </details>
      </div>
      <footer class="converter-footer">
        <p>套用會取代原英文；轉換不會生成圖片。</p>
        <div class="converter-footer-actions">
          <button type="button" class="secondary" @click="closeDialog">返回編輯</button>
          <button
            type="button"
            class="primary"
            :disabled="!result?.prompt.trim() || busy || disabled"
            @click="apply"
            ><UiIcon name="check" :size="15" />套用英文提示詞</button
          >
        </div>
      </footer>
    </dialog>
  </section>
</template>

<style scoped>
#app .atelier-shell .prompt-editor {
  margin: 0 0 18px;
  min-width: 0;
}
#app .atelier-shell .prompt-editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
#app .atelier-shell .prompt-editor-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}
.prompt-editor-title span {
  border: 1px solid var(--line2);
  border-radius: 4px;
  padding: 0 4px;
  color: var(--ink3);
  font-size: 10px;
  font-weight: 500;
}
#app .atelier-shell .prompt-editor-assist {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  margin: 0;
  padding: 5px 9px;
  border-radius: 8px;
  border-color: var(--line2);
  background: var(--asoft);
  color: var(--accent);
  font-size: 12px;
}
#app .atelier-shell .prompt-editor :slotted(textarea) {
  display: block;
  width: 100%;
  min-height: 144px;
  margin: 0;
  border-radius: 12px;
  padding: 12px 14px;
  box-sizing: border-box;
  line-height: 1.8;
}
#app .atelier-shell .prompt-editor-caption {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 7px;
  color: var(--ink3);
  font-size: 11px;
  line-height: 1.6;
}
.prompt-editor-count {
  margin-left: auto;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.prompt-editor-applied {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--accent);
}
#app .atelier-shell .converter-dialog {
  width: min(760px, calc(100vw - 32px));
  max-width: none;
  max-height: calc(100dvh - 40px);
  margin: auto;
  padding: 0;
  border: 1px solid var(--line2);
  border-radius: 20px;
  background: var(--panel);
  color: var(--ink);
  box-shadow: 0 28px 100px #0009;
  overflow: hidden;
  font: inherit;
}
.converter-dialog[open] {
  display: flex;
  flex-direction: column;
}
.converter-dialog::backdrop {
  background: #030806bd;
  backdrop-filter: blur(4px);
}
.converter-header {
  display: flex;
  height: auto;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px 18px;
  border-bottom: 1px solid var(--line);
  flex: none;
}
#app .atelier-shell .converter-dialog .converter-header h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 18px;
  line-height: 1.35;
}
#app .atelier-shell .converter-header p {
  margin: 0;
  color: var(--ink3);
  font-size: 12px;
}
#app .atelier-shell .converter-close {
  flex: none;
  width: 40px;
  height: 40px;
  min-height: 40px;
  padding: 0;
  margin: 0;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: transparent;
  font-size: 24px;
  line-height: 1;
}
.converter-body {
  padding: 20px 24px 12px;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.converter-compose {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-bottom: 18px;
}
.converter-column {
  display: flex;
  flex-direction: column;
  gap: 9px;
  min-width: 0;
}
.converter-field-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 22px;
}
#app .atelier-shell .converter-field-heading label,
.converter-output-title {
  margin: 0;
  padding: 0;
  font-size: 13px;
  font-weight: 600;
}
.converter-field-heading > span {
  color: var(--ink3);
  font-size: 11px;
}
#app .atelier-shell .converter-dialog .converter-textarea {
  width: 100%;
  min-height: 180px;
  max-height: 320px;
  margin: 0;
  padding: 13px 14px;
  border: 1px solid var(--line2);
  border-radius: 12px;
  background: var(--stage);
  color: var(--ink);
  font: inherit;
  font-size: 14px;
  line-height: 1.75;
  box-sizing: border-box;
}
#app .atelier-shell .converter-dialog .converter-preview {
  border-color: var(--accent);
}
#app .atelier-shell .converter-dialog .converter-textarea:focus {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}
.converter-source-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
#app .atelier-shell .converter-translate {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  margin: 0;
  min-height: 40px;
  padding: 8px 13px;
  font-size: 13px;
}
#app .atelier-shell .converter-dialog .converter-pending {
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--wsoft);
  color: var(--warm);
  font-size: 10px;
  white-space: nowrap;
}
.converter-output-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-sizing: border-box;
  min-height: 180px;
  border: 1px dashed var(--line2);
  border-radius: 12px;
  background: var(--stage);
  text-align: center;
  padding: 16px;
  color: var(--ink3);
}
.converter-output-empty strong {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink2);
}
.converter-output-empty > span:last-child {
  font-size: 11px;
}
.converter-language-mark {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--line);
  border-radius: 10px;
  font-size: 12px;
  letter-spacing: 1px;
  color: var(--accent);
}
#app .atelier-shell .converter-result-meta {
  margin: 0;
  font-size: 11px;
  color: var(--ink3);
}
#app .atelier-shell .converter-dialog .converter-disclosure {
  margin: 0;
  padding: 0;
  border: 0;
  border-top: 1px solid var(--line);
}
#app .atelier-shell .converter-disclosure > summary {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 2px 0;
  cursor: pointer;
  color: var(--ink2);
  font-size: 12px;
  list-style: none;
}
.converter-disclosure > summary::-webkit-details-marker {
  display: none;
}
.converter-chevron {
  font-size: 20px;
  line-height: 1;
  transition: transform 0.15s;
}
.converter-disclosure[open] > summary .converter-chevron {
  transform: rotate(90deg);
}
.converter-summary-meta {
  margin-left: auto;
  min-width: 0;
  max-width: 45%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: var(--ink3);
}
.converter-option-fields,
.converter-setting-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  padding: 4px 0 14px;
}
.converter-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}
#app .atelier-shell .converter-field label {
  margin: 0;
  padding: 0;
  font-size: 12px;
}
#app .atelier-shell .converter-field :is(input, select, textarea) {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  margin: 0;
  font-size: 13px;
  border-radius: 9px;
}
#app .atelier-shell .converter-field .converter-terms {
  min-height: 72px;
  max-height: 160px;
  padding: 9px 12px;
}
#app .atelier-shell .converter-dialog .converter-help {
  margin: 0 0 10px;
  font-size: 11px;
  color: var(--ink3);
  overflow-wrap: anywhere;
}
.converter-setting-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
#app .atelier-shell .converter-setting-actions button {
  margin: 0;
  padding: 7px 10px;
  min-height: 36px;
  font-size: 12px;
}
#app .atelier-shell .converter-dialog .converter-error {
  margin: 0 0 14px;
  padding: 10px 12px;
  border: 1px solid var(--border-warning);
  border-radius: 9px;
  background: var(--surface-warning);
  color: var(--text-warning);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.converter-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--line);
  background: var(--raised);
  flex: none;
}
#app .atelier-shell .converter-footer p {
  margin: 0;
  color: var(--ink3);
  font-size: 11px;
}
.converter-footer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
#app .atelier-shell .converter-footer-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 0;
  min-height: 40px;
  padding: 8px 12px;
  font-size: 13px;
}
.converter-spinning {
  animation: converter-spin 1.2s linear infinite;
}
@keyframes converter-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .converter-spinning {
    animation: none;
  }
  .converter-chevron {
    transition: none;
  }
}
@media (max-width: 640px) {
  #app .atelier-shell .converter-dialog {
    width: calc(100vw - 20px);
    max-height: calc(100dvh - 20px);
    border-radius: 14px;
  }
  .converter-header {
    padding: 16px;
    gap: 8px;
  }
  .converter-body {
    padding: 16px 16px 8px;
  }
  .converter-compose {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
    margin-bottom: 12px;
  }
  #app .atelier-shell .converter-dialog .converter-textarea {
    min-height: 112px;
    max-height: 220px;
    font-size: 13px;
  }
  .converter-output-empty {
    min-height: 112px;
  }
  .converter-option-fields,
  .converter-setting-fields {
    grid-template-columns: minmax(0, 1fr);
    gap: 12px;
  }
  .converter-footer {
    padding: 12px 16px;
    gap: 8px;
  }
  .converter-footer-actions {
    width: 100%;
  }
  .converter-footer-actions .primary {
    flex: 1;
  }
}
</style>
