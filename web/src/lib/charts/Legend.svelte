<script lang="ts">
	let { items }: { items: { name: string; color: string }[] } = $props();
</script>

{#if items.length > 1}
	<div class="text-muted-foreground mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
		{#each items as item (item.name)}
			<span class="flex items-center gap-1.5">
				<span class="size-2.5 rounded-full" style:background={item.color}></span>{item.name}
			</span>
		{/each}
	</div>
{/if}
