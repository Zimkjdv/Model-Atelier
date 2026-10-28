<script setup lang="ts">
import { apiJson as api } from './apiClient'
import { createRequestScope } from './requestScope'
import { onMounted, onUnmounted, ref } from 'vue'
import { pages, useNavigation } from './navigation'
import ModelLibrary from './ModelLibrary.vue'
import CreationStudio from './CreationStudio.vue'
import FluxStudio from './FluxStudio.vue'
import InpaintStudio from './InpaintStudio.vue'
import ControlStudio from './ControlStudio.vue'
import ReferenceStudio from './ReferenceStudio.vue'
import { referenceWorkflowId } from './adapterSettings'
import { isControlWorkflow } from './controlSettings'
import { isInpaintWorkflow } from './inpaintSettings'
import { fluxWorkflowId } from './fluxSettings'
import { isFluxExtension } from './fluxExtensions'
import AssetLibrary from './AssetLibrary.vue'
import ArtworkLibrary from './ArtworkLibrary.vue'
import LocalModelPaths from './LocalModelPaths.vue'
import DiagnosticsPanel from './DiagnosticsPanel.vue'
import TrainingWorkspace from './TrainingWorkspace.vue'
import type { EngineReport } from './environmentTypes'
import SystemWorkspace from './SystemWorkspace.vue'
import PageTabs from './PageTabs.vue'
import UiIcon from './UiIcon.vue'
import type { HostSystem as System } from './systemTypes'
const system = ref<System | null>(null),
  engine = ref<EngineReport | null>(null)
const artworkNotesDirty = ref(false)
const trainingDirty = ref(false)
const assetDirty = ref(false)
const {
  page,
  studioMode,
  galleryJob,
  galleryComparison,
  notice: routeNotice,
  navigate,
  focusMain,
} = useNavigation(
  () =>
    (page.value !== '訓練工作區' ||
      !trainingDirty.value ||
      window.confirm('訓練標註尚未保存或正在處理，確定離開訓練工作區？')) &&
    (page.value !== '參考素材' ||
      !assetDirty.value ||
      window.confirm('素材資料尚未保存或正在處理，確定離開？')) &&
    (page.value !== '作品庫' ||
      !artworkNotesDirty.value ||
      window.confirm('作品筆記或評分尚未保存，或批次操作正在處理，確定離開目前畫面？')),
)
const systemStale = ref(false),
  savedUrl = ref('')
const restoreRequest = ref<{ artworkId: string; token: number } | null>(null)
const fluxRestoreRequest = ref<{ artworkId: string; token: number } | null>(null)
const inpaintRestoreRequest = ref<{ artworkId: string; token: number } | null>(null)
const controlRestoreRequest = ref<{ artworkId: string; token: number } | null>(null)
const referenceRestoreRequest = ref<{ artworkId: string; token: number } | null>(null)
let restoreToken = 0
function restoreArtwork(artworkId: string, workflowId?: string | null) {
  const mode =
    workflowId === referenceWorkflowId
      ? 'reference'
      : workflowId === fluxWorkflowId || isFluxExtension(workflowId)
        ? 'flux'
        : isControlWorkflow(workflowId)
          ? 'control'
          : isInpaintWorkflow(workflowId)
            ? 'inpaint'
            : 'checkpoint'
  if (!navigate('創作工作台', mode)) return
  const value = { artworkId, token: ++restoreToken }
  if (mode === 'flux') fluxRestoreRequest.value = value
  else if (mode === 'reference') referenceRestoreRequest.value = value
  else if (mode === 'control') controlRestoreRequest.value = value
  else if (mode === 'inpaint') inpaintRestoreRequest.value = value
  else restoreRequest.value = value
}
const url = ref(''),
  error = ref(''),
  message = ref(''),
  busy = ref(false),
  saving = ref(false)
let timer: ReturnType<typeof setInterval> | undefined
const refreshRequests = createRequestScope()
let alive = true,
  settingsEpoch = 0
async function refresh(force = false) {
  if (!alive || (!force && (busy.value || saving.value))) return
  const request = refreshRequests.begin()
  const expectedUrl = savedUrl.value
  busy.value = true
  error.value = ''
  const results = await Promise.allSettled([
    api<System>('system', { signal: request.signal }),
    api<EngineReport>('engine', { signal: request.signal }),
  ])
  if (!alive || !request.isCurrent()) return
  if (results[0].status === 'fulfilled') system.value = results[0].value
  systemStale.value = results[0].status !== 'fulfilled'
  if (systemStale.value) error.value = '平台硬體資訊更新失敗，下方保留的舊資料可能已過期。'
  if (results[1].status === 'fulfilled') {
    const incoming = results[1].value
    if (incoming.diagnostics?.matches_selected_engine === false) {
      const reason = '引擎設定已在其他視窗變更，請重新確認連線設定。'
      engine.value = { ...incoming, connected: false, error: reason }
      error.value += ' ' + reason
    } else if (expectedUrl && incoming.url !== expectedUrl) {
      engine.value = null
      error.value += ' 引擎回報位址與已保存設定不同，請重新確認連線設定。'
    } else {
      engine.value = incoming
      if (!savedUrl.value) {
        savedUrl.value = incoming.url
        if (!url.value) url.value = incoming.url
      }
    }
  } else {
    engine.value = null
    error.value += ' 引擎狀態無法更新。'
  }
  busy.value = false
}
async function save() {
  if (saving.value || !alive) return
  ++settingsEpoch
  refreshRequests.cancel()
  engine.value = null
  busy.value = false
  saving.value = true
  message.value = ''
  try {
    const value = await api<{ comfy_url: string }>('settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comfy_url: url.value }),
    })
    if (!alive) return
    savedUrl.value = value.comfy_url
    url.value = value.comfy_url
    message.value = '設定已保存'
    await refresh(true)
  } catch (e) {
    if (alive) {
      message.value = e instanceof Error ? e.message : '保存失敗'
      await refresh(true)
    }
  } finally {
    if (alive) saving.value = false
  }
}
onMounted(async () => {
  const epoch = settingsEpoch
  try {
    const value = await api<{ comfy_url: string }>('settings')
    if (alive && epoch === settingsEpoch) {
      savedUrl.value = value.comfy_url
      if (!url.value) url.value = value.comfy_url
    }
  } catch {
    if (alive && epoch === settingsEpoch) message.value = '無法載入設定，請確認後端已啟動。'
  }
  if (!alive) return
  await refresh()
  if (!alive) return
  timer = setInterval(() => {
    if (document.visibilityState === 'visible') void refresh()
  }, 15000)
})
onUnmounted(() => {
  alive = false
  ++settingsEpoch
  refreshRequests.dispose()
  clearInterval(timer)
})

const navIcons = [
  'studio',
  'gallery',
  'experiments',
  'assets',
  'models',
  'training',
  'system',
  'settings',
]
const navLabels = ['創作', '作品庫', '比較', '素材', '模型', '訓練', '系統', '設定']
const settingsTab = ref('connection')
const transferRequest = ref<{ family: 'checkpoint' | 'flux'; token: number } | null>(null)
function openSettingsTransfer(family: 'checkpoint' | 'flux') {
  if (navigate('創作工作台', family)) transferRequest.value = { family, token: Date.now() }
}
const settingsItems = [
  { id: 'connection', label: '引擎連線' },
  { id: 'paths', label: '模型路徑' },
  { id: 'appearance', label: '外觀與語言' },
  { id: 'privacy', label: '資料與隱私' },
  { id: 'diagnostics', label: '診斷' },
]
const purposeRequest = ref<{ image: boolean; token: number } | null>(null)
const imagePurpose = ref(false)
const modelRequest = ref<{ name: string; engineUrl: string; token: number } | null>(null)
function useModel(architecture: string, name?: string, engineUrl?: string) {
  if (!navigate('創作工作台', architecture === 'flux' ? 'flux' : 'checkpoint')) return
  if (architecture !== 'flux' && name && engineUrl)
    modelRequest.value = { name, engineUrl, token: Date.now() }
}
const assetRequest = ref<{ id: string; purpose: string; token: number } | null>(null)
function useAsset(id: string, purpose: string) {
  const mode =
    purpose === 'composition'
      ? 'control'
      : purpose === 'style' || purpose === 'character'
        ? 'reference'
        : 'checkpoint'
  if (!navigate('創作工作台', mode)) return
  assetRequest.value = { id, purpose, token: Date.now() }
}
function selectPurpose(image: boolean) {
  imagePurpose.value = image
  purposeRequest.value = { image, token: Date.now() }
  navigate('創作工作台', studioMode.value === 'flux' ? 'flux' : 'checkpoint')
}
function openConnection() {
  settingsTab.value = 'connection'
  navigate('設定')
}
function settingsPaths() {
  settingsTab.value = 'paths'
  navigate('設定')
}
async function testConnection() {
  if (saving.value) return
  saving.value = true
  message.value = ''
  try {
    const result = await api<{ connected: boolean; error?: string }>('engine/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comfy_url: url.value }),
    })
    message.value = result.connected
      ? '測試連線成功（尚未保存）'
      : result.error || '測試連線失敗，原設定未變更。'
  } catch (e) {
    message.value = e instanceof Error ? e.message : '測試失敗，原設定未變更。'
  } finally {
    saving.value = false
  }
}
</script>
<template>
  <div
    class="layout atelier-shell"
    :class="{ 'system-page': page === '系統資訊', 'studio-page': page === '創作工作台' }"
  >
    <a class="skip-link" href="#main-content" @click.prevent="focusMain">跳至主要內容</a>
    <aside class="rail"
      ><a
        class="brand"
        title="Model Atelier · 系統資訊"
        href="#/system"
        @click.prevent="navigate('系統資訊')"
        ><span class="brand-icon">M</span></a
      ><nav aria-label="主要導覽"
        ><button
          v-for="(item, i) in pages"
          :key="item"
          :class="{ active: page === item, 'nav-management': item === '系統資訊' }"
          :aria-label="item"
          :aria-current="page === item ? 'page' : undefined"
          :title="item"
          @click="navigate(item)"
          ><UiIcon :name="navIcons[i]!" />{{ navLabels[i] }}</button
        ></nav
      ></aside
    >
    <main id="main-content" tabindex="-1"
      ><header class="app-topbar"
        ><h1>{{ page === '作品庫' && galleryComparison ? '作品比較' : page }}</h1
        ><div class="top-tools"
          ><span class="connection-status"
            ><span class="dot" :class="{ online: engine?.connected }"></span
            >{{ engine?.connected ? '引擎已連線' : engine ? '引擎未連線' : '連線狀態未知' }}</span
          ><button class="secondary" @click="openConnection">連線設定</button></div
        ></header
      >
      <section
        class="content"
        :class="{ 'studio-content': page === '創作工作台', 'system-content': page === '系統資訊' }"
      >
        <p v-if="routeNotice" class="notice" role="status">{{ routeNotice }}</p>
        <template v-if="page === '創作工作台'"
          ><div class="studio-navigation"
            ><div class="workflow-switch" role="group" aria-label="創作工作流程"
              ><button
                :aria-pressed="
                  (studioMode === 'checkpoint' || studioMode === 'flux') && !imagePurpose
                "
                @click="selectPurpose(false)"
                ><UiIcon name="text" />文字創作</button
              ><button
                :aria-pressed="
                  (studioMode === 'checkpoint' || studioMode === 'flux') && imagePurpose
                "
                @click="selectPurpose(true)"
                ><UiIcon name="redraw" />圖片重繪</button
              ><button
                :aria-pressed="studioMode === 'inpaint'"
                @click="navigate('創作工作台', 'inpaint')"
                ><UiIcon name="inpaint" />局部修補</button
              ><button
                :aria-pressed="studioMode === 'control'"
                @click="navigate('創作工作台', 'control')"
                ><UiIcon name="control" />結構引導</button
              ><button
                :aria-pressed="studioMode === 'reference'"
                @click="navigate('創作工作台', 'reference')"
                ><UiIcon name="reference" />風格參考</button
              ></div
            ><p class="workflow-hint">{{
              studioMode === 'inpaint'
                ? '只修改選定的區域。'
                : studioMode === 'control'
                  ? '依照參考圖的結構創作。'
                  : studioMode === 'reference'
                    ? '參考一張圖的畫風或角色特徵。'
                    : imagePurpose
                      ? '以一張圖片作為創作起點。'
                      : '從一句描述開始。'
            }}</p
            ><details
              v-if="studioMode === 'checkpoint' || studioMode === 'flux'"
              class="architecture-switch"
              ><summary>模型架構</summary
              ><div
                role="group"
                aria-label="模型執行架構"
                @click="
                  ($event.currentTarget as HTMLElement).closest('details')?.removeAttribute('open')
                "
                ><button
                  class="secondary"
                  :aria-pressed="studioMode === 'checkpoint'"
                  @click="navigate('創作工作台', 'checkpoint')"
                  >Checkpoint／SDXL</button
                ><button
                  class="secondary"
                  :aria-pressed="studioMode === 'flux'"
                  @click="navigate('創作工作台', 'flux')"
                  >FLUX.1 [schnell]</button
                ></div
              ></details
            ></div
          ></template
        >
        <KeepAlive
          ><CreationStudio
            :transfer-request="
              transferRequest?.family === 'checkpoint' ? transferRequest.token : undefined
            "
            v-if="(page === '創作工作台' && studioMode === 'checkpoint') || page === '實驗比較'"
            :workspace="page === '實驗比較' ? 'experiments' : 'studio'"
            :purpose-request="purposeRequest"
            @purpose="imagePurpose = $event"
            :asset-request="assetRequest?.purpose === 'unspecified' ? assetRequest : null"
            :model-request="modelRequest"
            :restore-request="restoreRequest"
            @models="navigate('模型庫')"
            @assets="navigate('參考素材')"
            @gallery="navigate('作品庫', studioMode, $event)"
            @studio="navigate('創作工作台', 'checkpoint')" /><FluxStudio
            :transfer-request="
              transferRequest?.family === 'flux' ? transferRequest.token : undefined
            "
            :purpose-request="purposeRequest"
            v-else-if="page === '創作工作台' && studioMode === 'flux'"
            :restore-request="fluxRestoreRequest"
            @models="navigate('模型庫')"
            @assets="navigate('參考素材')"
            @gallery="navigate('作品庫', studioMode, $event)" /><InpaintStudio
            v-else-if="page === '創作工作台' && studioMode === 'inpaint'"
            :restore-request="inpaintRestoreRequest"
            @models="navigate('模型庫')"
            @assets="navigate('參考素材')"
            @gallery="navigate('作品庫', studioMode, $event)" /><ControlStudio
            :asset-request="assetRequest?.purpose === 'composition' ? assetRequest : null"
            v-else-if="page === '創作工作台' && studioMode === 'control'"
            :restore-request="controlRestoreRequest"
            @models="navigate('模型庫')"
            @assets="navigate('參考素材')"
            @gallery="navigate('作品庫', studioMode, $event)" /><ReferenceStudio
            :asset-request="
              assetRequest?.purpose === 'style' || assetRequest?.purpose === 'character'
                ? assetRequest
                : null
            "
            v-else-if="page === '創作工作台' && studioMode === 'reference'"
            :restore-request="referenceRestoreRequest"
            @models="navigate('模型庫')"
            @assets="navigate('參考素材')"
            @gallery="navigate('作品庫', studioMode, $event)"
        /></KeepAlive>
        <SystemWorkspace
          v-if="page === '系統資訊'"
          :system="system"
          :engine="engine"
          :selected-url="savedUrl"
          :stale="systemStale"
          :busy="busy"
          :error="error"
          @refresh="refresh()"
          @settings="openConnection"
          @paths="settingsPaths"
        />
        <template v-else-if="page === '設定'"
          ><div class="page-intro"><p>只放你需要設定一次的事，日常創作時不會用到。</p></div
          ><div class="settings-workspace"
            ><PageTabs
              id="settings"
              v-model="settingsTab"
              label="設定分類"
              :items="settingsItems"
              vertical /><div
              ><section
                v-show="settingsTab === 'connection'"
                id="settings-panel-connection"
                role="tabpanel"
                aria-labelledby="settings-tab-connection"
                ><form class="panel settings" @submit.prevent="save"
                  ><h2>引擎連線</h2
                  ><p
                    >先啟動
                    ComfyUI，再填入服務位址。設定保存在平台資料庫，可使用本機或你管理的遠端執行主機。</p
                  ><label for="url">引擎位址</label
                  ><input
                    id="url"
                    v-model="url"
                    :disabled="saving"
                    required
                    type="url"
                    placeholder="http://127.0.0.1:8188"
                  /><div class="actions"
                    ><button
                      type="button"
                      class="secondary"
                      :disabled="saving || !url"
                      @click="testConnection"
                      >測試（不保存）</button
                    ><button class="primary" :disabled="saving">{{
                      saving ? '保存中…' : '保存並套用'
                    }}</button></div
                  ><p role="status">{{ message }}</p
                  ><p v-if="engine">{{ engine.connected ? 'ComfyUI 連線成功' : engine.error }}</p
                  ><p class="footnote"
                    >測試不修改設定；保存後套用選定引擎，不會啟動或重新啟動
                    ComfyUI。連線成功後仍需確認模型與必要元件。</p
                  ><button type="button" class="secondary" @click="navigate('系統資訊')"
                    >查看引擎執行環境</button
                  ></form
                ></section
              ><section
                v-show="settingsTab === 'paths'"
                id="settings-panel-paths"
                role="tabpanel"
                aria-labelledby="settings-tab-paths"
                ><LocalModelPaths :selected-engine-url="savedUrl" /></section
              ><section
                v-show="settingsTab === 'appearance'"
                id="settings-panel-appearance"
                role="tabpanel"
                aria-labelledby="settings-tab-appearance"
                class="panel appearance-panel"
                ><div class="appearance-heading"
                  ><h2>外觀與語言</h2><span class="chip">目前預設</span></div
                ><dl class="appearance-options"
                  ><div class="appearance-option"
                    ><dt
                      ><label for="appearance-theme">外觀</label
                      ><small id="appearance-theme-description">介面的背景與重點配色</small></dt
                    ><dd class="appearance-value appearance-theme"
                      ><span class="appearance-swatch" aria-hidden="true"></span
                      ><select id="appearance-theme" aria-describedby="appearance-theme-description"
                        ><option value="dark">深色</option></select
                      ></dd
                    ></div
                  ><div class="appearance-option"
                    ><dt
                      ><label for="appearance-language">介面語言</label
                      ><small id="appearance-language-description"
                        >平台選單與操作文字的顯示語言</small
                      ></dt
                    ><dd class="appearance-value"
                      ><select
                        id="appearance-language"
                        aria-describedby="appearance-language-description"
                        ><option value="zh-TW">繁體中文</option></select
                      ></dd
                    ></div
                  ></dl
                ><p class="appearance-note"
                  >目前僅提供深色與繁體中文，其他主題及語言尚未開放。</p
                ></section
              ><section
                v-show="settingsTab === 'privacy'"
                id="settings-panel-privacy"
                role="tabpanel"
                aria-labelledby="settings-tab-privacy"
                class="panel"
                ><h2>資料與隱私</h2
                ><p
                  >作品、素材與設定保存在平台的資料目錄。使用遠端引擎時，生成需要的提示詞與輸入圖會送往你選定的引擎。</p
                ><p
                  >封存可隨時還原，不會刪除圖片或釋放容量。完整備份沿用專案的停機備份流程；快取清除尚未開放。</p
                ><h3>創作設定匯出／匯入</h3
                ><p>前往工作台查看目前參數，再明確匯出 JSON；進入頁面不會保存、套用或生成。</p
                ><div class="settings-export-links"
                  ><button class="secondary" @click="openSettingsTransfer('checkpoint')"
                    >Checkpoint 設定匯出／匯入</button
                  ><button class="secondary" @click="openSettingsTransfer('flux')"
                    >FLUX 設定匯出／匯入</button
                  ></div
                ><p class="footnote"
                  >設定 JSON
                  會包含創作使用的引擎位址與參數，不包含平台整體設定、作品、素材圖片或模型權重。完整備份請使用專案既有的停機備份流程；附加與局部編輯流程的交換能力以工作台說明為準。</p
                ><button class="secondary" @click="navigate('系統資訊')"
                  >查看資料位置與磁碟容量</button
                ></section
              ><section
                v-show="settingsTab === 'diagnostics'"
                id="settings-panel-diagnostics"
                role="tabpanel"
                aria-labelledby="settings-tab-diagnostics"
                ><DiagnosticsPanel /></section></div></div
        ></template>
        <ModelLibrary v-if="page === '模型庫'" @create="useModel" @settings="openConnection" />
        <AssetLibrary
          v-else-if="page === '參考素材'"
          @use="useAsset"
          @dirty="assetDirty = $event"
        />
        <TrainingWorkspace v-else-if="page === '訓練工作區'" @dirty="trainingDirty = $event" />
        <ArtworkLibrary
          v-else-if="page === '作品庫'"
          :job-id="galleryJob"
          :comparing="galleryComparison"
          @compare="navigate('作品庫', studioMode, galleryJob, $event)"
          @studio="navigate('創作工作台')"
          @restore="restoreArtwork"
          @dirty="artworkNotesDirty = $event"
        /> </section></main
  ></div>
</template>
