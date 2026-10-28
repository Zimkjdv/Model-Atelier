<script setup lang="ts">
withDefaults(defineProps<{ width: number; height: number; title?: string; family?: string }>(), {
  title: '文字創作',
  family: '',
})
</script>
<template>
  <section
    class="studio-preview"
    aria-label="創作畫布"
    :style="{ '--canvas-ratio': width / height }"
  >
    <div class="stage-heading"
      ><div class="comparison-chips"
        ><span>{{ title }}</span
        ><span v-if="family">{{ family }}</span></div
      ><div class="stage-dimensions">{{ width }} × {{ height }}</div></div
    >
    <div class="empty-canvas" :style="{ aspectRatio: width + ' / ' + height }"
      ><span>準備下一張作品</span
      ><p>設定好後按「生成圖片」。<br />任務完成後，明確匯入作品庫保存原圖。</p></div
    >
    <p class="stage-caption">預覽依實際輸出尺寸顯示，不同模型的結果比例可能不同。</p>
  </section>
</template>
