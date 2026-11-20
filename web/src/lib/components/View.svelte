<script lang="ts">
	import type { Component } from 'svelte';
	import { format, type Chart, type View } from '#lib/api.js';
	import Bars from '#lib/charts/Bars.svelte';
	import Box from '#lib/charts/Box.svelte';
	import Heatmap from '#lib/charts/Heatmap.svelte';
	import Lines from '#lib/charts/Lines.svelte';
	import Pie from '#lib/charts/Pie.svelte';
	import Ranking from '#lib/charts/Ranking.svelte';
	import DataTable from './DataTable.svelte';
	import Panel from './Panel.svelte';

	let { view }: { view: View } = $props();

	const charts: Record<Chart['kind'], Component<{ chart: Chart }>> = {
		line: Lines,
		area: Lines,
		dot: Lines,
		bar: Bars,
		pie: Pie,
		box: Box,
		heatmap: Heatmap,
		ranking: Ranking
	};
	const status = { ok: 'bg-emerald-500', warn: 'bg-amber-500', fail: 'bg-red-500' };
</script>

<div class="grid gap-4">
	{#if view.tiles.length}
		<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
			{#each view.tiles as tile (tile.title)}
				<Panel title={tile.title}>
					<p class="flex items-center gap-2 text-xl font-semibold">
						{#if tile.status}<span class={['size-2.5 rounded-full', status[tile.status]]}></span>{/if}
						{format(tile.value)}
					</p>
					<p class="text-muted-foreground truncate text-sm" title={tile.note}>{tile.note}</p>
				</Panel>
			{/each}
		</div>
	{/if}

	<div class="grid gap-4 xl:grid-cols-2">
		{#each view.panels as panel (panel.title)}
			{#if panel.kind === 'table'}
				<Panel title={panel.title} class={panel.wide ? 'xl:col-span-2' : ''}>
					<DataTable table={panel} />
				</Panel>
			{:else}
				{@const Chart = charts[panel.kind]}
				<Panel title={panel.title} note={panel.note} stats={panel.stats} class={panel.wide ? 'xl:col-span-2' : ''}>
					<Chart chart={panel} />
				</Panel>
			{/if}
		{/each}
	</div>
</div>
