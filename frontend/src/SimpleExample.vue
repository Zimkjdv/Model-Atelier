<script setup lang="ts">
import { simpleExamples } from './simpleExamples'
import type { SimpleTemplateId } from './simpleCreation'
defineProps<{ id: SimpleTemplateId; modified: boolean }>()
</script>
<template>
  <details class="simple-example">
    <summary>真實範例、完整配方與觀察</summary>
    <figure>
      <a
        :href="simpleExamples[id].image"
        target="_blank"
        rel="noopener"
        :aria-label="'開啟 ' + id + ' 範例原圖'"
      >
        <img :src="simpleExamples[id].image" :alt="id + ' 原配方實際生成成果'" />
      </a>
      <figcaption
        >原配方 v{{ simpleExamples[id].template_version }} · 固定 Seed 9007199254740993</figcaption
      >
    </figure>
    <p>{{ simpleExamples[id].environment }}</p>
    <ul
      ><li v-for="note in simpleExamples[id].observations" :key="note">{{ note }}</li></ul
    >
    <p v-if="modified" role="status">目前設定已修改；此範例只對應原配方。</p>
    <p class="footnote"
      >這是固定環境的一張成果，不保證目前環境、其他 Seed
      或題材有相同結果，也不代表指定角色或作者畫風通過。</p
    >
    <a :href="simpleExamples[id].download" :download="id + '-example-v1.json'"
      >下載完整配方與實測紀錄（JSON）</a
    >
    <p class="footnote"
      >紀錄保留精確 Seed、原
      workflow、元件雜湊、版本及逐圖觀察；請用目前配方按鈕載入，不將此紀錄當成一般設定交換檔匯入。</p
    >
  </details>
</template>
<style scoped>
.simple-example {
  margin: 18px 0;
  overflow-wrap: anywhere;
}
figure {
  margin: 16px 0;
}
img {
  width: 100%;
  height: auto;
  border-radius: 8px;
}
figcaption {
  font-size: 12px;
  color: var(--ink2);
}
</style>
