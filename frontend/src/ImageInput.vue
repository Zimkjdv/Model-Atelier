<script setup lang="ts">
import { computed } from 'vue'
import { purposeLabel, type ReferenceAsset } from './referenceSettings'
const props = defineProps<{ modelValue: string | null; resize: 'fit' | 'stretch'; assets: ReferenceAsset[]; width: number; height: number; denoise: number }>()
const emit = defineEmits<{ 'update:modelValue': [value: string | null]; 'update:resize': [value: 'fit' | 'stretch']; 'update:denoise': [value: number] }>()
const selected = computed(() => props.assets.find(asset => asset.id === props.modelValue))
const ratio = computed(() => props.width > 0 && props.height > 0 ? props.width / props.height : 1)
</script>

<template>
  <section class="image-input" aria-label="圖生圖輸入">
    <h3>從一張圖片開始</h3>
    <label for="image-asset">輸入圖片</label>
    <select id="image-asset" :value="modelValue ?? ''" @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value || null)">
      <option value="">選擇一張參考素材</option>
      <option v-if="modelValue && !selected" :value="modelValue">原素材不存在（{{ modelValue }}）</option>
      <option v-for="asset in assets.filter(item => !item.archived || item.id === modelValue)" :key="asset.id" :value="asset.id" :disabled="asset.archived">{{ asset.title }} · {{ purposeLabel(asset.purpose) }}{{ asset.archived ? '（已封存）' : '' }}</option>
    </select>
    <p class="footnote">每次只套用這一張圖片；選擇後會替換草稿的其他素材關聯。用途標籤不會自動鎖定畫風或角色。</p>
    <p v-if="selected" class="footnote">原圖 {{ selected.width }} × {{ selected.height }} → 輸出 {{ width }} × {{ height }}</p>
    <label for="image-resize">輸入圖片縮放</label>
    <select id="image-resize" :value="resize" @change="emit('update:resize', ($event.target as HTMLSelectElement).value as 'fit' | 'stretch')"><option value="fit">等比縮放並補白</option><option value="stretch">拉伸至輸出尺寸</option></select>
    <p class="footnote">透明區域合成為白底。{{ resize === 'fit' ? '保留比例，置中並以白色填補空白。' : '填滿輸出畫布，原圖比例可能改變。' }}</p>
    <div v-if="selected && !selected.archived" class="input-preview" :style="{ aspectRatio: String(ratio), width: `min(100%, ${Math.min(320, 320 * ratio)}px)` }"><img :src="'/api/assets/' + selected.id + '/image'" :alt="'輸入預覽：' + selected.title" :style="{ objectFit: resize === 'fit' ? 'contain' : 'fill' }"></div>
    <p v-if="selected && !selected.archived" class="footnote">縮放示意；實際輸入以提交時保存的前處理 PNG 為準。</p>
    <label for="image-denoise">改動幅度（Denoise）</label>
    <input id="image-denoise" :value="denoise" type="number" min="0" max="1" step="any" required @input="emit('update:denoise', Number.parseFloat(($event.target as HTMLInputElement).value))">
    <p class="footnote">0～1：較低通常保留更多原圖，較高允許更多改動。這是 latent 圖生圖，不是獨立的風格參考強度。</p>
  </section>
</template>

<style scoped>
.image-input{margin-top:20px;padding:16px;border:1px solid var(--border-control);border-radius:10px;background:var(--surface-input)}h3{font-size:14px;margin:0 0 12px}label{display:block;margin:16px 0 8px;font-size:12px}select{width:100%;padding:12px;background:var(--surface-input);color:var(--text-primary);border:1px solid var(--border-control);border-radius:7px;font:inherit;font-size:13px}.input-preview{margin:14px auto;background:white;overflow:hidden;border-radius:6px}.input-preview img{display:block;width:100%;height:100%;object-position:center}.footnote{line-height:1.7}
</style>
