<script lang="ts">
	import { axisBottom, axisLeft, max, scaleBand, scaleLinear, select } from 'd3';
	import type { Chart } from '#lib/api.js';
	import Legend from './Legend.svelte';

	let { chart, height = 240 }: { chart: Chart; height?: number } = $props();

	const margin = { top: 8, right: 12, bottom: 24, left: 48 };
	let width = $state(600);
	const x = $derived(scaleBand(chart.x, [margin.left, width - margin.right]).padding(0.2));
	const inner = $derived(scaleBand(chart.series.map((s) => s.name), [0, x.bandwidth()]).padding(0.05));
	const y = $derived(
		scaleLinear()
			.domain([0, chart.y_max ?? max(chart.series.flatMap((s) => s.y), (v) => v) ?? 1])
			.nice()
			.range([height - margin.bottom, margin.top])
	);
	// at most one label per 70 px
	const step = $derived(Math.ceil(chart.x.length / Math.max(1, width / 70)));
</script>

<div bind:clientWidth={width}>
	<svg {width} {height} class="text-muted-foreground overflow-visible text-xs">
		<g
			transform="translate(0,{height - margin.bottom})"
			{@attach (g: SVGGElement) =>
				void select(g).call(axisBottom(x).tickValues(chart.x.filter((_, i) => i % step === 0)))}
		/>
		<g
			transform="translate({margin.left},0)"
			{@attach (g: SVGGElement) => void select(g).call(axisLeft(y).ticks(5))}
		/>
		{#each chart.series as s (s.name)}
			{#each s.y as v, i (i)}
				{#if v != null}
					<rect
						x={(x(chart.x[i]) ?? 0) + (inner(s.name) ?? 0)}
						y={y(v)}
						width={inner.bandwidth()}
						height={y(0) - y(v)}
						fill={s.color}
					/>
				{/if}
			{/each}
		{/each}
	</svg>
	<Legend items={chart.series} />
</div>
