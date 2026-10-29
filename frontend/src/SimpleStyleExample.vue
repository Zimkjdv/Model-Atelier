<script setup lang="ts">
import { computed } from 'vue'
import loraBefore from '../../docs/guide/images/examples/lora-baseline.png?url'
import loraAfter from '../../docs/guide/images/examples/lora-style.png?url'
import referenceBefore from '../../docs/guide/images/examples/reference-zero.png?url'
import referenceAfter from '../../docs/guide/images/examples/reference-style.png?url'
import loraRecipe from '../../docs/guide/examples/lora-style-v1.json?url'
import referenceRecipe from '../../docs/guide/examples/reference-style-v1.json?url'
const props = defineProps<{ task: 'lora' | 'reference' }>()
const examples = computed(() =>
  props.task === 'lora'
    ? [
        { image: loraBefore, label: '無 LoRA（提示詞已含 pixel art）' },
        { image: loraAfter, label: '單一像素 LoRA，MODEL 1／CLIP 1' },
      ]
    : [
        { image: referenceBefore, label: '同一參考流程，權重 0' },
        { image: referenceAfter, label: '同一參考流程，權重 0.6' },
      ],
)
</script>
<template>
  <details class="simple-style-example">
    <summary>查看真實作用對照與限制</summary>
    <figure v-for="item in examples" :key="item.label"
      ><a :href="item.image" target="_blank" rel="noopener"
        ><img :src="item.image" :alt="item.label" /></a
      ><figcaption>{{ item.label }}</figcaption></figure
    >
    <p v-if="task === 'lora'"
      >歷史 RTX 3060 固定對照。基準本來已有像素風；LoRA
      改變色塊、臉型與眼色，手部／書本仍有瑕疵。固定原生鍵名版本、強度 1／1；不組合其他 LoRA
      或圖片參考。</p
    >
    <p v-else
      >RTX 3060 固定對照使用自產示範圖。0.6
      將藍色髮束與戶外葉片帶入紅髮書店人物；畫風可能連同內容一起轉移。固定單圖 SDXL Plus
      ViT-H，不組合 LoRA、FaceID、結構引導或局部修補。</p
    >
    <p class="footnote"
      >配方與對照不保證鎖定角色身份、完全複製作者畫風，或在其他提示詞／環境有同樣效果。</p
    >
    <a :href="task === 'lora' ? loraRecipe : referenceRecipe" download
      >下載對照的完整設定與實測紀錄</a
    >
  </details>
</template>
<style scoped>
.simple-style-example {
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
