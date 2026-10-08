<script setup lang="ts">
import type { ExperimentContext } from './experimentSettings'
defineProps<{item?:ExperimentContext|null}>()
</script>
<template>
  <details v-if="item" class="experiment-snapshot"><summary>原比較方案：{{ item.plan_title }} · {{ item.variant_id }}</summary><p>{{ item.case_id }} · {{ item.axis }} = {{ item.value }} · Seed {{ item.settings.seed }}</p><p v-if="item.target_lora">LoRA：{{ item.target_lora }}</p><p>方案 ID：{{ item.plan_id }}</p><p>方案 SHA256：{{ item.plan_sha256 }}</p><p class="footnote">這是提交當時的關聯；載入作品／任務設定不會自動沿用關聯或生成。</p></details>
</template>
<style scoped>
.experiment-snapshot{margin:12px 0;font-size:12px;overflow-wrap:anywhere}summary{cursor:pointer;color:var(--text-notice)}p{line-height:1.7}
</style>
