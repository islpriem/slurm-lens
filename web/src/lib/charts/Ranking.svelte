<script lang="ts">
	import { number, type Chart } from '#lib/api.js';

	// a list of bars with value and share, one row per x
	let { chart }: { chart: Chart } = $props();

	const rows = $derived(
		chart.x.map((name, i) => {
			const series = chart.series.find((s) => s.y[i] != null)!;
			return { name, color: series.color, value: series.y[i] as number };
		})
	);
	const total = $derived(rows.reduce((sum, row) => sum + row.value, 0) || 1);
	const largest = $derived(Math.max(1, ...rows.map((row) => row.value)));
</script>

<ul class="grid gap-2.5 text-xs">
	{#each rows as row (row.name)}
		<li class="grid grid-cols-[minmax(4rem,11rem)_1fr_5rem_2.5rem] items-center gap-3">
			<span class="truncate" title={row.name}>{row.name}</span>
			<span class="bg-muted h-2 overflow-hidden rounded-full">
				<span class="block h-full rounded-full" style:width="{(100 * row.value) / largest}%" style:background={row.color}
				></span>
			</span>
			<span class="text-muted-foreground text-right tabular-nums">{number(row.value)}{chart.unit}</span>
			<span class="text-right font-medium tabular-nums">{Math.round((100 * row.value) / total)} %</span>
		</li>
	{/each}
</ul>
