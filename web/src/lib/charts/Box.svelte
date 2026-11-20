<script lang="ts">
	import { axisBottom, axisLeft, max, scaleBand, scaleLinear } from 'd3';
	import { number, type Chart } from '#lib/api.js';
	import { axis, grid, margin } from './axis.js';

	// lying box plots, one row per x; a value is [5th, 25th, 50th, 75th, 95th percentile].
	// Several series with values in the same rows are drawn side by side, each with its own axis.
	let { chart }: { chart: Chart } = $props();

	type Quantiles = [number, number, number, number, number];
	let width = $state(600);
	const boxes = $derived(
		chart.series.flatMap((s, f) => s.y.flatMap((q, i) => (Array.isArray(q) ? [{ s, f, i, q: q as Quantiles }] : [])))
	);
	const side = $derived(chart.x.some((_, i) => boxes.filter((b) => b.i === i).length > 1));
	const facets = $derived(side ? chart.series.map((s) => s.name) : ['']);
	const left = $derived(Math.min(200, 16 + 6.5 * Math.max(...chart.x.map((x) => x.length))));
	// a single box gets its median written on the right
	const right = $derived(side ? margin.right : 64);
	const top = $derived(side ? 24 : margin.top);
	const height = $derived(26 * chart.x.length + top + margin.bottom);
	const rows = $derived(scaleBand(chart.x, [top, height - margin.bottom]).padding(0.25));
	const facet = $derived((width - left - right) / facets.length);
	const highest = $derived(chart.y_max ?? max(boxes, (b) => b.q[4]) ?? 1);
	const scales = $derived(
		facets.map((_, f) =>
			scaleLinear()
				.domain([0, highest])
				.nice()
				.range([left + f * facet + (f ? 20 : 0), left + (f + 1) * facet])
		)
	);
</script>

<div bind:clientWidth={width}>
	<svg {width} {height} class="text-muted-foreground overflow-visible text-xs">
		{#each scales as x, f (f)}
			<g
				transform="translate(0,{height - margin.bottom})"
				{@attach grid(axisBottom(x).ticks(facet / 70).tickFormat((v) => number(+v)), height - top - margin.bottom)}
			/>
			{#if side}
				<text x={x.range()[0]} y="10" class="fill-foreground font-medium">
					<tspan fill={chart.series[f].color}>●</tspan> {facets[f]}
				</text>
			{/if}
		{/each}
		<g transform="translate({left},0)" {@attach axis(axisLeft(rows).tickSize(0).tickPadding(8))} />
		{#each boxes as { s, f, i, q } (`${f}-${i}`)}
			{@const x = scales[side ? f : 0]}
			{@const [p5, q1, median, q3, p95] = q.map((v) => x(v))}
			{@const y = rows(chart.x[i])!}
			{@const h = rows.bandwidth()}
			<g stroke={s.color}>
				<title>
					{chart.x[i]}{side ? `, ${s.name}` : ''}: median {number(q[2])}{chart.unit}, middle half {number(q[1])} to
					{number(q[3])}, 5th to 95th percentile {number(q[0])} to {number(q[4])}
				</title>
				<line x1={p5} x2={p95} y1={y + h / 2} y2={y + h / 2} />
				<line x1={p5} x2={p5} y1={y + 3} y2={y + h - 3} />
				<line x1={p95} x2={p95} y1={y + 3} y2={y + h - 3} />
				<rect x={q1} {y} width={Math.max(1, q3 - q1)} height={h} fill={s.color} fill-opacity="0.25" rx="2" />
				<line x1={median} x2={median} y1={y} y2={y + h} stroke-width="2.5" />
			</g>
			{#if !side}
				<text x={width - right + 10} y={y + h / 2} dy="0.35em" class="fill-foreground font-medium tabular-nums">
					{number(q[2])}{chart.unit}
				</text>
			{/if}
		{/each}
	</svg>
</div>
