<script setup lang="ts">
import { ref } from 'vue'
import TrainingDatasets from './TrainingDatasets.vue'
import TrainingControl from './TrainingControl.vue'
const emit = defineEmits<{ dirty: [value: boolean] }>()
const stage = ref(0)
const stages = ['審查資料', '匯出資料包', '準備訓練', '執行與產物']
const subtitles = ['補齊描述與來源', '建立固定版本', '凍結設定', '追蹤結果']
const tab = ref('datasets'),
  dirty = ref(false)
function changed(value: boolean) {
  dirty.value = value
  emit('dirty', value)
}
function selectStage(index: number) {
  const value = index < 2 ? 'datasets' : 'control'
  if (value === tab.value) {
    stage.value = index
    return
  }
  if (dirty.value && !window.confirm('訓練工作區尚有未保存內容或正在處理，確定切換？')) return
  stage.value = index
  tab.value = value
}
</script>
<template>
  <div class="page-intro"
    ><p>從資料品質開始，每個階段都清楚說明下一步。</p
    ><button class="secondary" @click="selectStage(3)">查看歷史報告</button></div
  ><div class="training-tabs" role="group" aria-label="訓練階段"
    ><button
      v-for="(label, index) in stages"
      :key="label"
      type="button"
      :aria-pressed="stage === index"
      :aria-label="index + 1 + ' ' + label"
      @click="selectStage(index)"
      ><span class="step-number">{{ index + 1 }}</span
      ><span
        >{{ label }}<small>{{ subtitles[index] }}</small></span
      ></button
    ></div
  ><TrainingDatasets v-if="tab === 'datasets'" :stage="stage" @dirty="changed" /><TrainingControl
    v-else
    :stage="stage"
    @dirty="changed"
  />
</template>
<style scoped>
.training-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
}
.training-tabs button[aria-pressed='true'] {
  outline: 2px solid #a7c296;
}
</style>
