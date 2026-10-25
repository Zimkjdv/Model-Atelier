<script setup lang="ts">
import { ref } from 'vue'
import TrainingDatasets from './TrainingDatasets.vue'
import TrainingControl from './TrainingControl.vue'
const emit = defineEmits<{ dirty: [value: boolean] }>()
const tab = ref('datasets'),
  dirty = ref(false)
function changed(value: boolean) {
  dirty.value = value
  emit('dirty', value)
}
function select(value: string) {
  if (
    value === tab.value ||
    (dirty.value && !window.confirm('訓練工作區尚有未保存內容或正在處理，確定切換？'))
  )
    return
  tab.value = value
}
</script>
<template>
  <div class="training-tabs"
    ><button
      class="secondary"
      type="button"
      :aria-pressed="tab === 'datasets'"
      @click="select('datasets')"
      >資料審查</button
    ><button
      class="secondary"
      type="button"
      :aria-pressed="tab === 'control'"
      @click="select('control')"
      >訓練執行</button
    ></div
  >
  <TrainingDatasets v-if="tab === 'datasets'" @dirty="changed" /><TrainingControl
    v-else
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
