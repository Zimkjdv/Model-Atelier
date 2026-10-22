<script setup lang="ts">
import type { RuntimeMetadata } from './runtimeMetadata'
import { metadataTime } from './modelMetadata'
defineProps<{ item?: RuntimeMetadata | null }>()
</script>
<template>
  <details class="runtime-snapshot">
    <summary>提交時引擎與依賴版本</summary>
    <p v-if="!item" class="footnote">沒有保存當時環境版本，保持未知；不以目前平台或引擎回填。</p>
    <template v-else>
      <p class="footnote">{{ metadataTime(item.captured_at) }} · 提交前觀察值，不保證排隊後引擎未更新或跨環境圖片完全相同。</p>
      <dl><dt>流程規格</dt><dd>{{ item.workflow.id }}</dd><dt>完整流程 SHA256</dt><dd>{{ item.workflow.sha256 }}</dd>
      <dt>原引擎來源</dt><dd>{{ item.engine.source }}</dd><dt>ComfyUI</dt><dd>{{ item.engine.comfyui || '未知' }}</dd>
      <dt>引擎 Python</dt><dd>{{ item.engine.python || '未知' }}</dd><dt>引擎 PyTorch</dt><dd>{{ item.engine.pytorch || '未知' }}</dd>
      <dt>引擎 CUDA／驅動／Git revision</dt><dd>{{ item.engine.cuda || '未知' }}／{{ item.engine.driver || '未知' }}／{{ item.engine.git_revision || '未知' }}</dd></dl>
      <p class="footnote">{{ item.engine.note }} {{ item.workflow.note }}</p>
      <ul><li v-for="entry in item.engine.packages" :key="entry.name">{{ entry.name }}：已安裝 {{ entry.installed || '未知' }} · 要求 {{ entry.required || '未知' }}</li></ul>
      <template v-if="item.execution_context?.schema_version===1"><h3>效能測試條件 · 推論</h3>
        <p>流程 {{item.execution_context.workflow_id}} · {{item.execution_context.geometry.width ?? '未知'}} × {{item.execution_context.geometry.height ?? '未知'}} · batch {{item.execution_context.geometry.batch_size ?? '未知'}}（{{item.execution_context.geometry.source}}）</p>
        <p v-for="entry in item.execution_context.parameters" :key="entry.node_id">節點 {{entry.node_id}} {{entry.class_type}}：{{JSON.stringify(entry.settings)}}</p>
        <p v-for="model in item.execution_context.models" :key="model.role+model.name">{{model.role}} · {{model.name || '未知'}} · 版本 {{model.version || '未知'}} · {{model.architecture || '架構未知'}}</p>
        <p>提交時 LoRA：{{item.execution_context.loras===null?'未保存':item.execution_context.loras.length+' 個（有序來源見 LoRA 快照）'}}</p>
        <p>啟動設定來源：{{item.execution_context.launch_policy.source}}</p>
        <p>精度旗標：{{item.execution_context.launch_policy.reported ? item.execution_context.launch_policy.precision_flags.join('、') || '未明示' : '未知'}}</p>
        <p>記憶體／卸載旗標：{{item.execution_context.launch_policy.reported ? item.execution_context.launch_policy.memory_flags.join('、') || '未明示' : '未知'}}</p>
        <p>實際運算精度／卸載：未知 · 冷／熱快取：未知</p><p>{{item.execution_context.note}}</p>
      </template><p v-else class="footnote">此歷史沒有結構化效能條件快照；保留原流程與版本，不以目前環境回填。</p>
      <h3>平台環境</h3><p>Python {{ item.platform.python }} · {{ item.platform.source }}</p>
      <ul><li v-for="entry in item.platform.packages" :key="entry.name">{{ entry.name }}：{{ entry.version || '未知' }}</li></ul>
    </template>
  </details>
</template>
<style scoped>
.runtime-snapshot{margin:18px 0;font-size:12px;overflow-wrap:anywhere}summary{cursor:pointer;color:var(--text-notice)}dl{display:grid;grid-template-columns:minmax(90px,1fr) minmax(0,1.4fr);gap:10px}dt{color:var(--text-muted)}dd{margin:0;min-width:0}ul{padding-left:20px;line-height:1.8}h3{font-size:13px}@media(max-width:500px){dl{grid-template-columns:1fr;gap:6px}dd{margin-bottom:6px}}
</style>
