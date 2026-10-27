<script setup lang="ts">
defineProps<{ width: number; height: number }>()
</script>
<template>
  <section class="studio-preview" aria-label="創作畫布"
    ><div class="stage-dimensions">{{ width }} × {{ height }}</div
    ><div class="empty-canvas" :style="{ aspectRatio: width + ' / ' + height }"
      ><span>準備下一張作品</span
      ><p>設定好後按「生成圖片」。<br />任務完成後，明確匯入作品庫保存原圖。</p></div
    ></section
  >
</template>
