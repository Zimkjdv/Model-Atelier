<script setup lang="ts">
import type { TemplateContext } from './templateContext'
defineProps<{ item?: TemplateContext | null }>()
</script>
<template>
  <details v-if="item" class="template-snapshot">
    <summary>起始模板：{{ item.title }} · v{{ item.selection.template_version }}</summary>
    <p
      >{{ item.modified ? '從此模板修改後生成' : '符合提交時的原配方設定' }}。模板發佈時說明：{{
        item.quality_note
      }}</p
    >
    <p class="footnote"
      >保留提交時的來源與原配方，後續模板更新不會改寫此紀錄；不代表生成品質驗收。</p
    >
    <dl
      ><dt>模板 ID／版本</dt
      ><dd>{{ item.selection.template_id }} / {{ item.selection.template_version }}</dd>
      <dt>來源文件</dt><dd>{{ item.source }}</dd
      ><dt>配置證據文件</dt><dd>{{ item.reference }}</dd> <dt>配方 SHA256</dt
      ><dd>{{ item.recipe_sha256 }}</dd>
      <template v-if="item.changed_fields.length"
        ><dt>變更欄位</dt><dd>{{ item.changed_fields.join('、') }}</dd></template
      >
    </dl>
    <details
      ><summary>提交時的原配方</summary><pre>{{ JSON.stringify(item.baseline, null, 2) }}</pre>
    </details>
  </details>
</template>
<style scoped>
.template-snapshot {
  margin-block: 16px;
  overflow-wrap: anywhere;
}
dd {
  margin: 4px 0 12px;
}
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 280px;
  overflow: auto;
}
</style>
