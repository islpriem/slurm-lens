<script lang="ts">
	import { axisBottom, axisLeft, max, scaleBand, scaleLinear } from 'd3';
	import { number, type Chart } from '#lib/api.js';
	import { axis, categories, grid, margin } from './axis.js';
	import Legend from './Legend.svelte';

	// grouped or stacked bars, standing or lying
	let { chart }: { chart: Chart } = $props();

	let width = $state(600);
	const lying = $derived(chart.horizontal);
	// lying bars get a row each and room for their labels
	const height = $derived(lying ? 28 * chart.x.length + margin.top + margin.bottom : 240);
	const left = $derived(lying ? Math.min(180, 12 + 6.5 * Math.max(...chart.x.map((x) => x.length))) : margin.left);
	// every bar with its category, series and the values it spans
	const bars = $derived.by(() => {
		const base = chart.x.map(() => 0);
		return chart.series.flatMap((s) =>
			(s.y as (number | null)[]).map((value, i) => {
				const from = chart.stacked ? base[i] : 0;
				if (chart.stacked) base[i] += value ?? 0;
				return { s, i, value, from, to: from + (value ?? 0) };
			})
		);
	});
	const band = $derived(
		scaleBand(chart.x, lying ? [margin.top, height - margin.bottom] : [left, width - margin.right]).padding(0.2)
	);
	const labels = $derived(categories(chart.x, lying ? Infinity : band.step()));
	const bottom = $derived(height - labels.bottom);
	const inner = $derived(
		scaleBand(chart.stacked ? [''] : chart.series.map((s) => s.name), [0, band.bandwidth()]).padding(0.05)
	);
	const value = $derived(
		scaleLinear()
			.domain([0, chart.y_max ?? max(bars, (b) => b.to) ?? 1])
			.nice()
			.range(lying ? [left, width - margin.right] : [bottom, margin.top])
	);

	function rect({ s, i, from, to }: (typeof bars)[number]) {
		const position = band(chart.x[i])! + inner(chart.stacked ? '' : s.name)!;
		const [low, high] = [value(from), value(to)];
		return lying
			? { x: low, y: position, width: high - low, height: inner.bandwidth() }
			: { x: position, y: high, width: inner.bandwidth(), height: low - high };
	}
</script>

<div bind:clientWidth={width}>
	<svg {width} {height} class="text-muted-foreground overflow-visible text-xs">
		{#if lying}
			<g
				transform="translate(0,{height - margin.bottom})"
				{@attach grid(axisBottom(value).ticks(width / 90).tickFormat((v) => number(+v)), height - margin.top - margin.bottom)}
			/>
			<g transform="translate({left},0)" {@attach axis(axisLeft(band).tickSize(0).tickPadding(6))} />
		{:else}
			<g transform="translate({left},0)" {@attach grid(axisLeft(value).ticks(5).tickFormat((v) => number(+v)), width - left - margin.right)} />
			<g transform="translate(0,{bottom})" {@attach axis(axisBottom(band).tickValues(labels.labels), labels.tilt)} />
		{/if}
		{#each bars as bar, k (k)}
			{#if bar.value}
				<rect {...rect(bar)} fill={bar.s.color} rx="1.5">
					<title>{chart.x[bar.i]}, {bar.s.name}: {number(bar.value)}{chart.unit}</title>
				</rect>
			{/if}
		{/each}
	</svg>
	<Legend items={chart.series} />
</div>
