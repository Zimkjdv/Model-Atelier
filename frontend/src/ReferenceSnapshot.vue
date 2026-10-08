<script setup lang="ts">
import { purposeLabel, type ReferenceSnapshot } from './referenceSettings'
defineProps<{ items?: ReferenceSnapshot[] | null; jobId?: string; processedReady?: boolean }>()
</script>
<template>
  <details v-if="items?.length" class="reference-snapshot">
    <summary>提交時的參考素材與前處理</summary>
    <p class="footnote">保留當時的輸入與處理設定，不隨素材名稱、用途或套件版本更新而改動。</p>
    <article v-for="item in items" :key="item.id"><p>{{ item.input_role === 'mask' ? '遮罩：' : item.input_role === 'source' ? '原圖：' : '' }}{{ item.title }} · {{ purposeLabel(item.purpose) }} · {{ item.width }} × {{ item.height }}</p>
      <dl><dt>素材 ID</dt><dd>{{ item.id }}</dd><dt>素材 SHA256</dt><dd>{{ item.sha256 }}</dd><dt>素材正規化</dt><dd>{{ item.preprocessing ? 'v' + item.preprocessing.version + ' · Pillow ' + item.preprocessing.library_version : '未知' }}</dd>
        <dt>{{ item.input_role === 'mask' ? '遮罩前處理' : '原圖前處理' }}</dt><dd>v{{ item.generation_preprocessing.version }} · Pillow {{ item.generation_preprocessing.library_version }}</dd><dt>縮放與輸出</dt><dd>{{ item.generation_preprocessing.resize === 'fit' ? (item.input_role === 'mask' ? '等比補黑' : '等比補白') : '拉伸' }} · {{ item.input_role === 'mask' ? '二值 RGB PNG · 灰階 128 · 白色編輯／黑色保留' : '白底 RGB PNG' }} · {{ item.generation_preprocessing.width }} × {{ item.generation_preprocessing.height }}</dd><dt>處理後 SHA256</dt><dd>{{ item.generation_preprocessing.sha256 }}</dd></dl>
      <a :href="'/api/assets/' + item.id + '/image'" target="_blank" rel="noopener">查看本機素材 ↗</a>
      <a v-if="jobId && processedReady" :href="'/api/jobs/' + jobId + (item.input_role === 'mask' ? '/reference-mask' : '/reference-image')" target="_blank" rel="noopener">查看已保存的處理後輸入 ↗</a>
    </article>
  </details>
</template>
<style scoped>
.reference-snapshot{margin:14px 0;padding:12px;border:1px solid var(--border-control);border-radius:8px;font-size:12px;overflow-wrap:anywhere}summary{cursor:pointer}dl{display:grid;grid-template-columns:minmax(90px,.7fr) minmax(0,1fr);gap:10px}dt{color:var(--text-secondary)}dd{margin:0}a{color:#c5dfba;display:inline-block;margin:8px 14px 0 0}.footnote{line-height:1.7}@media(max-width:500px){dl{grid-template-columns:1fr;gap:6px}dd{margin-bottom:6px}}
</style>
