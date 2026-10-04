<script setup lang="ts">
import type { LoraMetadataSnapshot } from './modelMetadata'
import { architectureLabel, fileHash, fileSize, metadataTime, safeMetadataUrl } from './modelMetadata'
defineProps<{ items?: LoraMetadataSnapshot[] | null }>()
</script>
<template>
  <details class="lora-snapshot">
    <summary>提交時 LoRA 資料{{ items?.length ? ` · ${items.length} 個` : '' }}</summary>
    <p v-if="items == null" class="footnote">沒有保存當時 LoRA 登記快照，版本與檔案識別未知；請查看完整工作流程。不以目前模型庫回填原紀錄。</p>
    <p v-else-if="!items.length" class="footnote">此任務提交的流程沒有啟用 LoRA。</p>
    <template v-else>
      <p class="footnote">保存提交時的使用者登記及實際送出的設定，後續編輯不改寫快照；不代表實際權重、授權或效果已驗證。</p>
      <section v-for="(item, index) in items" :key="index" :aria-label="`LoRA 快照：${item.name}`">
        <h3>{{ item.name }}</h3><dl>
          <dt>登記版本</dt><dd>{{ item.version?.trim() || '未知' }}</dd>
          <dt>模型強度 / CLIP 強度</dt><dd>{{ item.strength_model }} / {{ item.strength_clip }}</dd>
          <dt>登記基礎架構</dt><dd>{{ architectureLabel(item.architecture) }}</dd>
          <dt>檔案大小</dt><dd>{{ fileSize(item.size_bytes) }}</dd>
          <dt>SHA-256（登記）</dt><dd class="file-hash">{{ fileHash(item.sha256) }}</dd>
          <dt>來源</dt><dd><a v-if="safeMetadataUrl(item.source_url)" :href="safeMetadataUrl(item.source_url)" target="_blank" rel="noopener noreferrer">查看當時登記來源 ↗</a><span v-else>未知</span></dd>
          <dt>授權名稱／標記</dt><dd>{{ item.license_name?.trim() || '未知' }}</dd>
          <dt>授權條款</dt><dd><a v-if="safeMetadataUrl(item.license_url)" :href="safeMetadataUrl(item.license_url)" target="_blank" rel="noopener noreferrer">查看當時登記條款 ↗</a><span v-else>未知</span></dd>
          <dt>登記資料更新</dt><dd>{{ metadataTime(item.metadata_updated_at) }}</dd>
          <dt>快照保存</dt><dd>{{ metadataTime(item.captured_at) }}</dd>
        </dl>
      </section>
    </template>
  </details>
</template>
<style scoped>
.lora-snapshot{margin:18px 0;font-size:12px;overflow-wrap:anywhere}.lora-snapshot summary{cursor:pointer;color:var(--text-notice)}h3{font-size:13px}dl{display:grid;grid-template-columns:minmax(90px,1fr) minmax(0,1.4fr);gap:10px}dt{color:var(--text-muted)}dd{margin:0;min-width:0}a{color:var(--text-notice)}.file-hash{font-family:monospace;line-height:1.7}@media(max-width:500px){dl{grid-template-columns:1fr;gap:6px}dd{margin-bottom:6px}}
</style>
