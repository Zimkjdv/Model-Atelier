<script setup lang="ts">
defineProps<{ dirty: boolean; saving?: boolean; saved?: boolean; pageOnly?: boolean }>()
</script>

<template>
  <p v-if="dirty || saving || saved" class="footnote save-state" role="status" aria-label="內容保存狀態">
    <template v-if="saving">正在保存，完成前請保留本頁。</template>
    <template v-else-if="dirty">有未保存變更；站內切換會保留，重新整理或關頁可能遺失。</template>
    <template v-else-if="saved">草稿已保存到本機。</template>
    <template v-else>設定僅保留於本頁，尚未保存為草稿。</template>
    <template v-if="pageOnly"> 此流程尚不提供完整草稿保存；保存素材不包含本頁設定。</template>

  </p>
</template>
