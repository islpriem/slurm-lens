<script lang="ts">
	import { area, axisBottom, axisLeft, bisectCenter, extent, line, max, pointer, scaleLinear, scaleTime, timeFormat } from 'd3';
	import { dateTime, number, type Chart } from '#lib/api.js';
	import { axis, grid, margin } from './axis.js';
	import Legend from './Legend.svelte';

	// lines, stacked areas or dots over time
	let { chart, height = 240 }: { chart: Chart; height?: number } = $props();

	// the day at midnight, otherwise the time (d3 would use a 12 hour clock)
	const tick = (d: Date) => timeFormat(d.getHours() || d.getMinutes() ? '%H:%M' : '%d %b')(d);
	let width = $state(600);
	let hover = $state<number>(); // index of the time under the pointer
	const times = $derived(chart.x.map((x) => new Date(x)));
	// areas are stacked: every series starts at the sum of the ones before
	const layers = $derived.by(() => {
		let base = times.map(() => 0);
		return chart.series.map((s) => {
			const y = s.y as (number | null)[];
			if (chart.kind !== 'area') return { ...s, lower: base, upper: y };
			const lower = base;
			base = base.map((b, i) => b + (y[i] ?? 0));
			return { ...s, lower, upper: base };
		});
	});
	const top = $derived(chart.y_max ?? max(layers.flatMap((l) => l.upper), (v) => v) ?? 1);
	const x = $derived(
		scaleTime()
			.domain(extent(times) as [Date, Date])
			.range([margin.left, width - margin.right])
	);
	// d3 starts the day ticks again with every month, a tick close to the one before is left out
	const ticks = $derived(x.ticks(width / 110).filter((t, i, all) => !i || x(t) - x(all[i - 1]) > 50));
	const y = $derived(
		scaleLinear()
			.domain([0, top])
			.nice()
			.range([height - margin.bottom, margin.top])
	);
	const path = $derived(
		line<number | null>()
			.defined((v) => v != null)
			.x((_, i) => x(times[i]))
			.y((v) => y(v!))
	);
	const fill = (lower: number[]) =>
		area<number | null>()
			.x((_, i) => x(times[i]))
			.y0((_, i) => y(lower[i]))
			.y1((v) => y(v!));

	function move(event: PointerEvent) {
		hover = times.length ? bisectCenter(times, x.invert(pointer(event)[0])) : undefined;
	}
</script>

<div class="relative" bind:clientWidth={width}>
	<svg
		{width}
		{height}
		class="text-muted-foreground overflow-visible text-xs"
		role="img"
		onpointermove={move}
		onpointerleave={() => (hover = undefined)}
	>
		<g
			transform="translate({margin.left},0)"
			{@attach grid(axisLeft(y).ticks(5).tickFormat((v) => number(+v)), width - margin.left - margin.right)}
		/>
		<g
			transform="translate(0,{height - margin.bottom})"
			{@attach axis(axisBottom<Date>(x).tickValues(ticks).tickFormat(tick))}
		/>
		{#each layers as layer (layer.name)}
			{#if chart.kind === 'dot'}
				{#each layer.upper as v, i (i)}
					{#if v != null}<circle cx={x(times[i])} cy={y(v)} r="2.5" fill={layer.color} />{/if}
				{/each}
			{:else if chart.kind === 'area'}
				<path d={fill(layer.lower)(layer.upper)} fill={layer.color} fill-opacity="0.85" />
			{:else}
				<path d={path(layer.upper)} fill="none" stroke={layer.color} stroke-width="1.5" />
			{/if}
		{/each}
		{#if hover !== undefined}
			<line x1={x(times[hover])} x2={x(times[hover])} y1={margin.top} y2={height - margin.bottom} stroke="currentColor" />
		{/if}
	</svg>
	{#if hover !== undefined}
		{@const left = x(times[hover]) < width / 2}
		<div
			class="bg-popover text-popover-foreground pointer-events-none absolute top-0 z-10 rounded-md border px-2 py-1 text-xs shadow-sm"
			style:left={left ? `${x(times[hover]) + 8}px` : null}
			style:right={left ? null : `${width - x(times[hover]) + 8}px`}
		>
			<p class="text-muted-foreground mb-1">{dateTime(chart.x[hover])}</p>
			{#each chart.series.filter((s) => s.y[hover!] != null) as s (s.name)}
				<p class="flex items-center gap-1.5">
					<span class="size-2 rounded-full" style:background={s.color}></span>{s.name}
					<span class="ml-auto pl-3 tabular-nums">{number(s.y[hover] as number)}{chart.unit}</span>
				</p>
			{/each}
		</div>
	{/if}
	<Legend items={chart.series} />
</div>
