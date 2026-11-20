<script lang="ts">
	import { arc, pie, type PieArcDatum } from 'd3';
	import { number, type Chart, type Series } from '#lib/api.js';

	// a donut with one slice per series, the total in the middle and the shares next to it
	let { chart }: { chart: Chart } = $props();

	const slices = $derived(
		pie<Series>()
			.value((s) => s.y[0] as number)
			.sort(null)(chart.series)
	);
	const total = $derived(slices.reduce((sum, slice) => sum + slice.value, 0));
	const shape = arc<PieArcDatum<Series>>().innerRadius(64).outerRadius(96).padAngle(0.015).cornerRadius(2);
	const share = (value: number) => `${Math.round((100 * value) / (total || 1))} %`;
</script>

<div class="flex flex-wrap items-center justify-center gap-x-12 gap-y-4">
	<svg viewBox="-100 -100 200 200" class="size-44 shrink-0">
		{#each slices as slice (slice.data.name)}
			<path d={shape(slice)} fill={slice.data.color}>
				<title>{slice.data.name}: {number(slice.value)}{chart.unit} ({share(slice.value)})</title>
			</path>
		{/each}
		<text text-anchor="middle" dy="0.1em" class="fill-foreground text-[26px] font-semibold">{number(total)}</text>
		<text text-anchor="middle" dy="1.9em" class="fill-muted-foreground text-[11px]">in total</text>
	</svg>
	<ul class="grid gap-2 text-xs">
		{#each slices as slice (slice.data.name)}
			<li class="grid grid-cols-[auto_1fr_auto_2.5rem] items-center gap-2">
				<span class="size-2.5 rounded-full" style:background={slice.data.color}></span>
				<span class="text-muted-foreground pr-4">{slice.data.name}</span>
				<span class="tabular-nums">{number(slice.value)}</span>
				<span class="text-right font-medium tabular-nums">{share(slice.value)}</span>
			</li>
		{/each}
	</ul>
</div>
