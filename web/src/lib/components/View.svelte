<script lang="ts">
	import { dateTime, number, type View } from '#lib/api.js';
	import Bars from '#lib/charts/Bars.svelte';
	import Lines from '#lib/charts/Lines.svelte';
	import Panel from './Panel.svelte';

	let { view }: { view: View } = $props();
</script>

<div class="grid gap-4">
	{#if view.tiles.length}
		<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
			{#each view.tiles as tile (tile.title)}
				<Panel title={tile.title}>
					<p class="text-xl font-semibold">
						{typeof tile.value === 'number' ? number(tile.value) : dateTime(tile.value)}
					</p>
					<p class="text-muted-foreground text-sm">{tile.note}</p>
				</Panel>
			{/each}
		</div>
	{/if}

	<div class="grid gap-4 xl:grid-cols-2">
		{#each view.charts as chart (chart.title)}
			<Panel title={chart.title} class={chart.wide ? 'xl:col-span-2' : ''}>
				{#if chart.kind === 'bar'}
					<Bars {chart} />
				{:else}
					<Lines {chart} />
				{/if}
			</Panel>
		{/each}
	</div>
</div>
