<script lang="ts">
	import { quantile } from 'd3';
	import { number, type Chart } from '#lib/api.js';

	// one row per series, one cell per x, the darker the more
	let { chart }: { chart: Chart } = $props();

	const left = 40;
	let width = $state(600);
	const cell = $derived(Math.min(36, (width - left) / chart.x.length));
	const values = $derived(chart.series.flatMap((s) => s.y as number[]));
	// a few extreme cells would leave all others pale, so the color is full from the 95th percentile on
	const top = $derived(quantile(values, 0.95) || 1);
	// the color shines through more the larger the value, on light and dark backgrounds
	const color = $derived(chart.series[0]?.color ?? 'currentColor');
	const opacity = (value: number) => 0.08 + 0.92 * Math.min(1, value / top);
</script>

<div bind:clientWidth={width}>
	<svg {width} height={cell * chart.series.length + 22} class="text-muted-foreground text-xs">
		{#each chart.series as s, row (s.name)}
			<text x={left - 8} y={(row + 0.5) * cell} dy="0.35em" text-anchor="end">{s.name}</text>
			{#each s.y as value, i (i)}
				<rect x={left + i * cell + 1} y={row * cell + 1} width={cell - 2} height={cell - 2} rx="3" fill={color}
					fill-opacity={opacity(value as number)}>
					<title>{s.name} {chart.x[i]}: {number(value as number)}{chart.unit}</title>
				</rect>
			{/each}
		{/each}
		{#each chart.x as label, i (label)}
			{#if i % 3 === 0}
				<text x={left + i * cell + cell / 2} y={cell * chart.series.length + 15} text-anchor="middle">{label}</text>
			{/if}
		{/each}
	</svg>
	<div class="text-muted-foreground mt-2 flex items-center justify-end gap-2 text-xs">
		<span>{number(Math.min(...values))}</span>
		<span class="h-2 w-32 rounded-full" style:background="linear-gradient(to right, color-mix(in srgb, {color} 8%, transparent), {color})"></span>
		<span>{number(top)}{chart.unit} and more</span>
	</div>
</div>
