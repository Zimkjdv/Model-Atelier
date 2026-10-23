<script setup lang="ts">
import { purposeLabel, type ReferenceSnapshot } from './referenceSettings'
defineProps<{ items?: ReferenceSnapshot[] | null; jobId?: string; processedReady?: boolean }>()
</script>
<template>
  <details v-if="items?.length" class="reference-snapshot">
    <summary>提交時的參考素材與前處理</summary>
    <p class="footnote">保留當時的輸入與處理設定，不隨素材名稱、用途或套件版本更新而改動。</p>
    <article v-for="item in items" :key="item.id"><p>{{ item.input_role === 'mask' ? '遮罩：' : item.input_role === 'structure' ? '結構素材：' : item.input_role === 'source' ? '原圖：' : '' }}{{ item.title }} · {{ purposeLabel(item.purpose) }} · {{ item.width }} × {{ item.height }}</p>
      <dl><dt>素材 ID</dt><dd>{{ item.id }}</dd><dt>素材 SHA256</dt><dd>{{ item.sha256 }}</dd><dt>素材正規化</dt><dd>{{ item.preprocessing ? 'v' + item.preprocessing.version + ' · Pillow ' + item.preprocessing.library_version : '未知' }}</dd>
        <dt>{{ item.input_role === 'mask' ? '遮罩前處理' : '原圖前處理' }}</dt><dd>v{{ item.generation_preprocessing.version }} · Pillow {{ item.generation_preprocessing.library_version }}</dd><dt>縮放與輸出</dt><dd>{{ item.generation_preprocessing.resize === 'fit' ? (item.input_role === 'mask' ? '等比補黑' : '等比補白') : '拉伸' }} · {{ item.input_role === 'mask' ? '二值 RGB PNG · 灰階 128 · 白色編輯／黑色保留' : '白底 RGB PNG' }} · {{ item.generation_preprocessing.width }} × {{ item.generation_preprocessing.height }}</dd><dt>處理後 SHA256</dt><dd>{{ item.generation_preprocessing.sha256 }}</dd></dl>
      <p v-if="item.control_preprocessing?.kind" class="footnote">原引擎 {{item.control_preprocessing.id}} · {{item.control_preprocessing.kind}} · 所需套件修訂 {{item.control_preprocessing.expected_package_revision}} · 實際節點版本 {{item.control_preprocessing.node_version || '未知'}}。實際條件 PNG 可在姿勢／深度條件圖區保存。</p>
      <p v-else-if="item.control_preprocessing" class="footnote">原引擎原生 Canny v{{item.control_preprocessing.version}} · 閾值 {{item.control_preprocessing.low_threshold}}／{{item.control_preprocessing.high_threshold}} · 節點版本 {{item.control_preprocessing.node_version || '未知'}}。此處是前處理參數；v2 任務的實際邊緣 PNG 可在「查看原任務的 Canny 邊緣圖」中另行保存。</p>
      <template v-if="item.blend_preprocessing"><p class="footnote">原任務合成遮罩：內側半徑 {{item.blend_preprocessing.radius}} 輸出像素 · {{item.blend_preprocessing.method}} v{{item.blend_preprocessing.version}} · Pillow {{item.blend_preprocessing.library_version}}。這是歷史參數，不隨目前表單改動。</p><p class="footnote">合成 PNG SHA256：{{item.blend_preprocessing.sha256}}</p><a v-if="jobId && processedReady" :href="'/api/jobs/'+jobId+'/reference-blend-mask'" target="_blank" rel="noopener">查看原合成遮罩 ↗</a><a v-if="jobId && processedReady" :href="'/api/jobs/'+jobId+'/reference-blend-mask?download=true'">下載合成遮罩 ↓</a></template>
      <template v-if="item.dedicated_inpaint"><p class="footnote">專用修補 {{item.dedicated_inpaint.id}} · 所需節點修訂 {{item.dedicated_inpaint.required_node_revision}} · 實際版本 {{item.dedicated_inpaint.node_version || '未知'}}</p><p v-for="weight in item.dedicated_inpaint.weights" :key="weight.filename" class="footnote">{{weight.filename}} · {{weight.version}} · SHA256 {{weight.sha256}}</p></template>
      <a :href="'/api/assets/' + item.id + '/image'" target="_blank" rel="noopener">查看本機素材 ↗</a>
      <a v-if="jobId && processedReady" :href="'/api/jobs/' + jobId + (item.input_role === 'mask' ? '/reference-mask' : '/reference-image')" target="_blank" rel="noopener">查看已保存的處理後輸入 ↗</a>
    </article>
  </details>
</template>
<style scoped>
.reference-snapshot{margin:14px 0;padding:12px;border:1px solid var(--border-control);border-radius:8px;font-size:12px;overflow-wrap:anywhere}summary{cursor:pointer}dl{display:grid;grid-template-columns:minmax(90px,.7fr) minmax(0,1fr);gap:10px}dt{color:var(--text-secondary)}dd{margin:0}a{color:#c5dfba;display:inline-block;margin:8px 14px 0 0}.footnote{line-height:1.7}@media(max-width:500px){dl{grid-template-columns:1fr;gap:6px}dd{margin-bottom:6px}}
</style>
