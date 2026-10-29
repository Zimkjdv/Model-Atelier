<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, ref, watch } from 'vue'
import type { ControlForm } from './controlSettings'
import type { ReferenceAsset } from './referenceSettings'
import {
  cannyPreviewIdentity,
  cannyPreviewInput,
  cannyPreviewProblem,
  checkedCannyPreview,
  type CannyPreviewInfo,
} from './cannyPreview'
const props = defineProps<{ form: ControlForm; source?: ReferenceAsset; disabled: boolean }>()
const image = ref(''),
  info = ref<CannyPreviewInfo | null>(null),
  error = ref(''),
  busy = ref(false)
const identity = computed(() => cannyPreviewIdentity(props.form, props.source)),
  blocked = computed(() => cannyPreviewProblem(props.form, props.source))
let ticket = 0,
  controller: AbortController | null = null,
  active = true
function reset() {
  ++ticket
  controller?.abort()
  busy.value = false
  error.value = ''
  info.value = null
  if (image.value) URL.revokeObjectURL(image.value)
  image.value = ''
}
function imageFailed() {
  reset()
  error.value = '預覽圖片無法解碼，請重做預覽。'
}
async function preview() {
  if (!active || busy.value || props.disabled || blocked.value || !props.source) return
  reset()
  const current = ++ticket,
    key = identity.value,
    form = JSON.parse(JSON.stringify(props.form)),
    source = { ...props.source },
    abort = new AbortController()
  controller = abort
  busy.value = true
  try {
    const response = await fetch('/api/control/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cannyPreviewInput(form)),
      signal: abort.signal,
    })
    const result = await checkedCannyPreview(response, form, source)
    if (current !== ticket || !active || key !== identity.value || blocked.value || props.disabled)
      return
    image.value = URL.createObjectURL(result.blob)
    info.value = result.info
  } catch (e) {
    if (current === ticket && !abort.signal.aborted)
      error.value = e instanceof Error ? e.message : '預覽失敗。'
  } finally {
    if (current === ticket) busy.value = false
  }
}
watch(() => [identity.value, blocked.value, props.disabled, props.form.control_kind], reset, {
  flush: 'sync',
})
onDeactivated(() => {
  active = false
  reset()
})
onActivated(() => {
  active = true
})
onBeforeUnmount(() => {
  active = false
  reset()
})
</script>
<template>
  <section
    class="canny-preview"
    :aria-label="form.control_kind ? '結構來源圖預覽' : '送出前 Canny 預覽'"
  >
    <div class="stage-heading"
      ><div class="comparison-chips"
        ><span>結構引導</span
        ><span>{{
          form.control_kind === 'pose'
            ? 'Pose 姿勢'
            : form.control_kind === 'depth'
              ? 'Depth 深度'
              : 'Canny 輪廓'
        }}</span
        ><span>{{ image && !form.control_kind ? 'CPU 預覽' : '來源圖' }}</span></div
      ><span class="stage-dimensions">{{ form.width }} × {{ form.height }}</span></div
    >
    <div class="control-preview-actions">
      <button
        v-if="!form.control_kind"
        type="button"
        class="secondary"
        :disabled="busy || disabled || !!blocked"
        @click="preview"
        >{{ busy ? '計算 Canny 中…' : '預覽 Canny 邊緣' }}</button
      >
      <span class="footnote">{{
        !form.control_kind
          ? '本機 CPU 計算，不建立生成任務。'
          : '條件圖由原引擎生成，完成後可在任務與作品查看。'
      }}</span>
    </div>
    <p v-if="busy" role="status">正在本機 CPU 計算；可繼續修改設定，過期回覆不會顯示。</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
    <div
      class="control-source-stage"
      :style="{
        '--canvas-ratio': form.width / form.height,
        aspectRatio: form.width + ' / ' + form.height,
      }"
    >
      <img
        v-if="image && !form.control_kind"
        :src="image"
        alt="目前未提交設定的本機 CPU Canny 二值邊緣預覽"
        @error="imageFailed"
      />
      <img
        v-else-if="source && !source.archived"
        :src="'/api/assets/' + source.id + '/image'"
        :alt="'結構來源圖：' + source.title"
      />
      <div v-else class="control-source-empty"
        ><strong>選擇結構來源圖</strong><p>先在左側選圖，再確認結構方式與控制模型。</p></div
      >
    </div>
    <p class="stage-caption">{{
      image && !form.control_kind
        ? '本機近似預覽；不是原任務實際條件圖。'
        : '顯示原始素材；此處尚未產生結構條件或生成結果。'
    }}</p>
    <p v-if="blocked && source && !form.control_kind" class="footnote">{{ blocked }}</p>
    <details class="control-preview-details"
      ><summary>預覽方式與限制</summary>
      <p v-if="form.control_kind"
        >本機預覽僅提供 Canny；Pose／Depth
        條件由原引擎生成，完成後可從任務與作品查看。此處顯示原始素材。</p
      >
      <p v-if="!form.control_kind"
        >以目前來源、尺寸、縮放與閾值在本機 CPU 計算。無需模型或引擎，不建立生成任務。最多 1,048,576
        像素，45 秒逾時會停止。</p
      >
      <p v-if="!form.control_kind"
        >這是本機近似預覽，不是原任務輸出；不同 CPU／GPU
        或引擎版本可能產生差異。原任務實際邊緣仍從完成任務另行保存。</p
      >
      <p v-if="image"
        >{{ form.width }} × {{ form.height }} · 閾值 {{ form.canny_low }}／{{ form.canny_high }} ·
        {{
          form.reference_resize === 'fit' ? '等比補白' : '拉伸'
        }}。修改來源、尺寸、縮放或閾值後會清除預覽。</p
      >
      <p v-else-if="!form.control_kind">尚無目前設定的預覽；按下按鈕才計算，不會自動產生圖片。</p>
    </details>
    <details v-if="info"
      ><summary>本次 CPU 預覽來源</summary
      ><p
        >{{ info.method }} · float32 CPU<br />Torch {{ info.torch }} · Kornia {{ info.kornia }} ·
        Pillow {{ info.pillow }}</p
      ><p>原生 Canny 原碼 SHA256：{{ info.native_sha256 }}</p
      ><p>處理後輸入 SHA256：{{ info.input_sha256 }}</p
      ><p>預覽 PNG SHA256：{{ info.sha256 }}</p></details
    >
  </section>
</template>
<style scoped>
.canny-preview {
  min-width: 0;
  overflow-wrap: anywhere;
}
.control-preview-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin: 14px 0;
}
.control-source-stage {
  width: min(100%, calc((100vh - 350px) * var(--canvas-ratio)));
  margin: 0 auto;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--panel);
}
.control-source-stage img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.control-source-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  text-align: center;
}
.control-preview-details {
  font-size: 13px;
}
</style>
