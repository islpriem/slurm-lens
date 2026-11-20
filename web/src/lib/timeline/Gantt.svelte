<script lang="ts">
	import { bisectRight, scaleLinear } from 'd3';
	import { jobColor, PLANNED, RUNNING, type Gantt } from '#lib/api.js';
	import { tick, timeTicks } from '#lib/charts/axis.js';
	import { settings } from '#lib/settings.svelte.js';

	// One row per GPU, grouped by node. Jobs that ran are solid, jobs running at the snapshot are
	// light until their time limit, jobs the scheduler plans to start are hatched.
	let {
		gantt,
		color,
		shades,
		partitions,
		selected = $bindable()
	}: {
		gantt: Gantt;
		color: 'user' | 'account';
		shades: boolean;
		partitions: string[]; // only nodes in one of them, all if empty
		selected?: number;
	} = $props();

	const ROW = 10; // height of a GPU
	const GAP = 8; // between two nodes
	const LEFT = 116; // room for the names of the nodes
	const FAINT = 0.55; // the other jobs while one is selected

	let width = $state(800);
	let canvas = $state<HTMLCanvasElement>();
	let hover = $state<{ bar: number; x: number; y: number }>();

	// the top of every GPU (undefined if its node is filtered out) and of every node that is shown
	const layout = $derived.by(() => {
		const tops: (number | undefined)[] = [];
		const groups = [];
		let y = GAP / 2;
		for (const node of gantt.nodes) {
			const shown = !partitions.length || node.partitions.some((p) => partitions.includes(p));
			for (let gpu = 0; gpu < node.gpus; gpu++) tops.push(shown ? y + gpu * ROW : undefined);
			if (!shown) continue;
			groups.push({ node, top: y, bottom: y + node.gpus * ROW });
			y += node.gpus * ROW + GAP;
		}
		// the rows that are shown, from the top, to find the one under the pointer
		const rows = tops.flatMap((top, row) => (top == null ? [] : [row]));
		return { tops, rows, ys: rows.map((row) => tops[row]!), groups, height: Math.max(0, y - GAP / 2) };
	});
	const fills = $derived(gantt.jobs.map((_, job) => jobColor(gantt, job, color, shades)));
	const x = $derived(
		scaleLinear()
			.domain([+new Date(gantt.start), +new Date(gantt.end)])
			.range([LEFT, width - 12])
	);
	const now = $derived(x(+new Date(gantt.at)));
	const ticks = $derived(timeTicks(x));
	// the bars of every row, to find the one under the pointer
	const byRow = $derived.by(() => {
		const rows: number[][] = layout.tops.map(() => []);
		gantt.bars.forEach((bar, i) => rows[bar[1]].push(i));
		return rows;
	});
	const chosen = $derived(selected == null ? -1 : gantt.jobs.findIndex(([id]) => id === selected));

	// hatching for planned jobs, one pattern per color
	const patterns = new Map<string, CanvasPattern | null>();
	function stripes(context: CanvasRenderingContext2D, fill: string) {
		if (!patterns.has(fill)) {
			const tile = Object.assign(document.createElement('canvas'), { width: 6, height: 6 });
			const draw = tile.getContext('2d')!;
			draw.fillStyle = draw.strokeStyle = fill;
			draw.globalAlpha = 0.25;
			draw.fillRect(0, 0, 6, 6);
			draw.globalAlpha = 1;
			draw.lineWidth = 1.5;
			draw.beginPath();
			for (const offset of [-6, 0, 6]) {
				draw.moveTo(offset, 6);
				draw.lineTo(offset + 6, 0);
			}
			draw.stroke();
			patterns.set(fill, context.createPattern(tile, 'repeat'));
		}
		return patterns.get(fill)!;
	}

	function paint(context: CanvasRenderingContext2D, i: number, alpha: number) {
		const [job, row, start, end, kind] = gantt.bars[i];
		if (layout.tops[row] == null) return;
		const fill = fills[job];
		const [left, top] = [x(start), layout.tops[row] + 1];
		// a hairline between two jobs on the same GPU, if there is room for it
		const [w, h] = [x(end) - left > 3 ? x(end) - left - 1 : Math.max(1, x(end) - left), ROW - 2];
		context.globalAlpha = alpha * (kind === RUNNING ? 0.4 : 1);
		context.fillStyle = kind === PLANNED ? stripes(context, fill) : fill;
		context.fillRect(left, top, w, h);
		if (kind === PLANNED) {
			context.strokeStyle = fill;
			context.lineWidth = 1;
			context.strokeRect(left + 0.5, top + 0.5, w - 1, h - 1);
		}
		context.globalAlpha = 1;
	}

	function outline(context: CanvasRenderingContext2D, job: number, stroke: string, glow: boolean) {
		const bars = gantt.bars.flatMap((bar, i) => (bar[0] === job ? [i] : []));
		if (glow) {
			// the selected job shines in its color above all others
			context.shadowColor = fills[job];
			context.shadowBlur = 14;
			bars.forEach((i) => paint(context, i, 1));
			context.shadowBlur = 0;
		}
		context.strokeStyle = stroke;
		context.lineWidth = glow ? 1.5 : 1;
		for (const i of bars) {
			const [, row, start, end] = gantt.bars[i];
			const top = layout.tops[row];
			if (top != null) context.strokeRect(x(start), top + 0.5, Math.max(1, x(end) - x(start)), ROW - 1);
		}
	}

	$effect(() => {
		if (!canvas) return;
		void settings.dark; // the colors of the theme change with it
		const theme = getComputedStyle(canvas);
		const context = canvas.getContext('2d')!;
		const ratio = devicePixelRatio;
		[canvas.width, canvas.height] = [width * ratio, layout.height * ratio];
		context.scale(ratio, ratio);
		context.font = `11px ${theme.fontFamily}`;
		context.textBaseline = 'middle';
		// a band every other node, its name on the left, red if it is unavailable
		layout.groups.forEach(({ node, top, bottom }, i) => {
			if (i % 2) {
				context.fillStyle = theme.getPropertyValue('--muted');
				context.fillRect(0, top - GAP / 2, width, bottom - top + GAP);
			}
			const unavailable = node.state === 'unavailable';
			context.fillStyle = theme.getPropertyValue(unavailable ? '--destructive' : '--muted-foreground');
			context.fillText(node.name, 8, top + ROW / 2);
			if (node.gpus > 1) context.fillText(node.model, 8, top + ROW * 1.6);
		});
		context.strokeStyle = theme.getPropertyValue('--border');
		for (const t of ticks) context.strokeRect(Math.round(x(t)) + 0.5, 0, 0, layout.height);
		// all jobs, faint while one is selected; then the selected and the hovered job on top
		gantt.bars.forEach((bar, i) => paint(context, i, chosen < 0 || bar[0] === chosen ? 1 : FAINT));
		const foreground = theme.getPropertyValue('--foreground');
		if (chosen >= 0) outline(context, chosen, foreground, true);
		if (hover && gantt.bars[hover.bar][0] !== chosen) outline(context, gantt.bars[hover.bar][0], foreground, false);
		// the snapshot
		context.fillStyle = theme.getPropertyValue('--primary');
		context.fillRect(now - 1, 0, 2, layout.height);
	});

	/** The bar under the pointer, a few pixels around short ones. */
	function find(event: MouseEvent) {
		const i = bisectRight(layout.ys, event.offsetY) - 1;
		if (i < 0 || event.offsetY > layout.ys[i] + ROW) return undefined;
		const row = layout.rows[i];
		const [time, slack] = [x.invert(event.offsetX), x.invert(event.offsetX + 3) - x.invert(event.offsetX)];
		return byRow[row].find((i) => gantt.bars[i][2] - slack <= time && time <= gantt.bars[i][3] + slack);
	}

	function move(event: MouseEvent) {
		const bar = find(event);
		hover = bar == null ? undefined : { bar, x: event.offsetX, y: event.offsetY };
	}

	function click(event: MouseEvent) {
		// a click on the selected job, or next to all jobs, ends the selection
		const bar = find(event);
		const job = bar == null ? undefined : gantt.jobs[gantt.bars[bar][0]][0];
		selected = job === selected ? undefined : job;
	}

	const time = (ms: number) => new Date(ms).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
	const what = ['ran', 'runs, at most until its time limit', 'planned by the scheduler'];
</script>

<div>
	<svg {width} height="26" class="text-muted-foreground text-xs">
		{#each ticks as t (t)}
			<text x={x(t)} y="13" dy="0.35em" text-anchor="middle" fill="currentColor">{tick(new Date(t))}</text>
		{/each}
		<g transform="translate({now},0)">
			<rect x="-24" y="2" width="48" height="20" rx="10" class="fill-primary" />
			<text y="12" dy="0.35em" text-anchor="middle" class="fill-primary-foreground font-medium">
				{new Date(gantt.at).toLocaleTimeString('en-GB', { timeStyle: 'short' })}
			</text>
		</g>
	</svg>
	<!-- the width without the scrollbar -->
	<div class="relative max-h-[calc(100svh-15rem)] min-h-64 overflow-y-auto" bind:clientWidth={width}>
		<canvas
			bind:this={canvas}
			style:width="{width}px"
			style:height="{layout.height}px"
			class={['block', hover && 'cursor-pointer']}
			aria-label="Jobs on the GPUs over time"
			onpointermove={move}
			onpointerleave={() => (hover = undefined)}
			onclick={click}
		></canvas>
		{#if !layout.groups.length}
			<p class="text-muted-foreground p-6 text-sm">No GPU node is in the chosen partitions.</p>
		{/if}
		{#if hover}
			{@const [job, , start, end, kind] = gantt.bars[hover.bar]}
			{@const [id, user, account] = gantt.jobs[job]}
			<div
				class="bg-popover text-popover-foreground pointer-events-none absolute z-10 rounded-md border px-2.5 py-1.5 text-xs shadow-md"
				style:left={hover.x < width / 2 ? `${hover.x + 14}px` : null}
				style:right={hover.x < width / 2 ? null : `${width - hover.x + 14}px`}
				style:top="{hover.y + 12}px"
			>
				<p class="flex items-center gap-1.5 font-medium">
					<span class="size-2 rounded-full" style:background={fills[job]}></span>Job {id}
				</p>
				<p class="text-muted-foreground">{user} · {account}</p>
				<p>{what[kind]}</p>
				<p class="text-muted-foreground tabular-nums">{time(start)} – {time(end)}</p>
			</div>
		{/if}
	</div>
</div>
