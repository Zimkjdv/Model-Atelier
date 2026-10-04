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
      <h3>平台環境</h3><p>Python {{ item.platform.python }} · {{ item.platform.source }}</p>
      <ul><li v-for="entry in item.platform.packages" :key="entry.name">{{ entry.name }}：{{ entry.version || '未知' }}</li></ul>
    </template>
  </details>
</template>
<style scoped>
.runtime-snapshot{margin:18px 0;font-size:12px;overflow-wrap:anywhere}summary{cursor:pointer;color:var(--text-notice)}dl{display:grid;grid-template-columns:minmax(90px,1fr) minmax(0,1.4fr);gap:10px}dt{color:var(--text-muted)}dd{margin:0;min-width:0}ul{padding-left:20px;line-height:1.8}h3{font-size:13px}@media(max-width:500px){dl{grid-template-columns:1fr;gap:6px}dd{margin-bottom:6px}}
</style>
