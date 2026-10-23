<script setup lang="ts">
import { onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from 'vue'
import { apiJson } from './apiClient'
import { createRequestScope } from './requestScope'

const props = defineProps<{ family: 'inpaint' | 'control' | 'reference' }>()
type Support = {
  note: string
  workflows: {
    id: string
    name: string
    capabilities: {
      draft: boolean
      settings_export: boolean
      settings_import: boolean
      comparison_plan: boolean
      restore_saved_settings: boolean
      download_workflow: boolean
    }
  }[]
}
const support = ref<Support | null>(null)
const error = ref('')
const reads = createRequestScope()
let activated = false
async function load() {
  const read = reads.begin()
  error.value = ''
  try {
    const value = await apiJson<Support>(
      '/api/reference-workflows/support?family=' + props.family,
      { signal: read.signal },
    )
    if (read.isCurrent()) support.value = value
  } catch (cause) {
    if (read.isCurrent()) error.value = cause instanceof Error ? cause.message : '無法讀取支援範圍'
  }
}
onMounted(load)
onActivated(() => {
  if (activated) void load()
  activated = true
})
onDeactivated(reads.cancel)
onBeforeUnmount(reads.dispose)
const status = (enabled: boolean) => (enabled ? '已提供' : '尚未支援')
</script>

<template>
  <details class="format-support">
    <summary>草稿、設定交換與比較的支援範圍</summary>
    <p v-if="error" role="alert"
      >{{ error }} <button type="button" @click="load">重新讀取支援範圍</button></p
    >
    <template v-else-if="support">
      <p>{{ support.note }}</p>
      <ul>
        <li v-for="workflow in support.workflows" :key="workflow.id">
          <strong>{{ workflow.name }}</strong
          >：一般草稿{{ status(workflow.capabilities.draft) }}； 設定匯出{{
            status(workflow.capabilities.settings_export)
          }}／匯入{{ status(workflow.capabilities.settings_import) }}； 比較方案{{
            status(workflow.capabilities.comparison_plan)
          }}。 已保存設定載入{{
            status(workflow.capabilities.restore_saved_settings)
          }}；完整工作流程下載{{ status(workflow.capabilities.download_workflow) }}。
        </li>
      </ul>
      <p
        >未提交的表單及未保存的遮罩筆畫仍只保留於本頁。新生成使用
        v2；載入舊版設定不會改寫原任務、原版本或待確認請求。</p
      >
    </template>
    <p v-else role="status">正在讀取支援範圍…</p>
  </details>
</template>

<style scoped>
.format-support {
  margin: 16px 0;
  font-size: 13px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
summary {
  cursor: pointer;
  color: var(--text-notice);
}
</style>
