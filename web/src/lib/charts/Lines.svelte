<script lang="ts">
	import { axisBottom, axisLeft, extent, line, max, scaleLinear, scaleLog, scaleTime, select, timeFormat } from 'd3';
	import type { Chart } from '#lib/api.js';
	import Legend from './Legend.svelte';

	let { chart, height = 240 }: { chart: Chart; height?: number } = $props();

	const margin = { top: 8, right: 12, bottom: 24, left: 48 };
	// the day at midnight, otherwise the time (d3 would use a 12 hour clock)
	const tick = (d: Date) => timeFormat(d.getHours() || d.getMinutes() ? '%H:%M' : '%d %b')(d);
	let width = $state(600);
	const times = $derived(chart.x.map((x) => new Date(x)));
	const top = $derived(chart.y_max ?? max(chart.series.flatMap((s) => s.y), (v) => v) ?? 1);
	const x = $derived(
		scaleTime()
			.domain(extent(times) as [Date, Date])
			.range([margin.left, width - margin.right])
	);
	const y = $derived(
		(chart.log ? scaleLog().domain([1, top]) : scaleLinear().domain([0, top]))
			.nice()
			.range([height - margin.bottom, margin.top])
	);
	const path = $derived(
		line<number | null>()
			.defined((v) => v != null)
			.x((_, i) => x(times[i]))
			.y((v) => y(v!))
	);
</script>

<div bind:clientWidth={width}>
	<svg {width} {height} class="text-muted-foreground overflow-visible text-xs">
		<g
			transform="translate(0,{height - margin.bottom})"
			{@attach (g: SVGGElement) =>
				void select(g).call(axisBottom<Date>(x).ticks(width / 110).tickFormat(tick))}
		/>
		<g
			transform="translate({margin.left},0)"
			{@attach (g: SVGGElement) => void select(g).call(axisLeft(y).ticks(5, chart.log ? '~s' : undefined))}
		/>
		{#each chart.series as s (s.name)}
			{#if chart.kind === 'dot'}
				{#each s.y as v, i (i)}
					{#if v != null}
						<circle cx={x(times[i])} cy={y(v)} r="2.5" fill={s.color} />
					{/if}
				{/each}
			{:else}
				<path d={path(s.y)} fill="none" stroke={s.color} stroke-width="1.5" />
			{/if}
		{/each}
	</svg>
	<Legend items={chart.series} />
</div>
