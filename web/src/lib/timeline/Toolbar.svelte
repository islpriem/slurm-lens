<script lang="ts">
	import Pause from '@lucide/svelte/icons/pause';
	import Play from '@lucide/svelte/icons/play';
	import StepBack from '@lucide/svelte/icons/step-back';
	import StepForward from '@lucide/svelte/icons/step-forward';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { dateTime, duration, GRAY, type Gantt } from '#lib/api.js';
	import Choice from '#lib/components/Choice.svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { loading } from '#lib/loading.svelte.js';

	let { gantt, color = $bindable() }: { gantt: Gantt; color: 'user' | 'account' } = $props();

	const AHEAD = [24, 48, 120].map((hours) => ({ value: hours, label: hours === 24 ? '1 day' : `${hours / 24} days` }));
	const COLORS = [
		{ value: 'account' as const, label: 'Accounts' },
		{ value: 'user' as const, label: 'Users' }
	];
	const times = $derived(gantt.snapshots.map((time) => +new Date(time)));
	const last = $derived(times.length - 1);
	const index = $derived(times.indexOf(+new Date(gantt.at)));
	const ahead = $derived(Number(page.url.searchParams.get('ahead') ?? 48));
	let preview = $state<number>(); // the position of the slider while it is dragged
	let playing = $state(false);

	/** Another snapshot or horizon; the latest snapshot is the default and needs no parameter. */
	function show(changes: { at?: number; ahead?: number }, replace = false) {
		const url = new URL(page.url.href);
		if (changes.at != null) {
			if (changes.at >= last) url.searchParams.delete('at');
			else url.searchParams.set('at', gantt.snapshots[changes.at]);
		}
		if (changes.ahead) url.searchParams.set('ahead', String(changes.ahead));
		return goto(url, { reset: false, replace });
	}

	// replay: the next snapshot as soon as the current one is shown
	$effect(() => {
		if (!playing || loading.active) return;
		if (index >= last) return void (playing = false);
		const timer = setTimeout(() => show({ at: index + 1 }, true), 600);
		return () => clearTimeout(timer);
	});

	const shown = $derived(preview ?? index);
	const kinds = [
		{ label: 'ran', style: 'background: var(--muted-foreground)' },
		{ label: 'runs, at most until its time limit', style: 'background: var(--muted-foreground); opacity: 0.4' },
		{
			label: 'planned by the scheduler',
			style: 'background: repeating-linear-gradient(-45deg, var(--muted-foreground) 0 1.5px, transparent 1.5px 4px)'
		}
	];
</script>

<Card.Root class="gap-3 py-3">
	<Card.Content class="flex-row flex-wrap items-center gap-x-6 gap-y-3 px-4">
		<div class="flex min-w-72 flex-1 items-center gap-1">
			<Button variant="ghost" size="icon-sm" disabled={index <= 0} onclick={() => show({ at: index - 1 })} aria-label="One snapshot back">
				<StepBack />
			</Button>
			<Button variant="ghost" size="icon-sm" disabled={index >= last} onclick={() => (playing = !playing)}
				aria-label={playing ? 'Pause' : 'Replay'}>
				{#if playing}<Pause />{:else}<Play />{/if}
			</Button>
			<Button variant="ghost" size="icon-sm" disabled={index >= last} onclick={() => show({ at: index + 1 })} aria-label="One snapshot forward">
				<StepForward />
			</Button>
			<input
				type="range"
				min="0"
				max={last}
				value={shown}
				disabled={last < 1}
				class="accent-primary mx-2 flex-1"
				aria-label="Snapshot"
				oninput={(event) => (preview = +event.currentTarget.value)}
				onchange={(event) => {
					show({ at: +event.currentTarget.value });
					preview = undefined;
				}}
			/>
			<div class="w-40 text-xs leading-tight">
				<p class="font-medium tabular-nums">{dateTime(gantt.snapshots[shown] ?? gantt.at)}</p>
				<p class="text-muted-foreground">
					{shown >= last || shown < 0 ? 'latest snapshot' : `${duration(times[last] - times[shown])} earlier`}
				</p>
			</div>
		</div>
		<label class="text-muted-foreground flex items-center gap-2 text-xs">
			Ahead <Choice options={AHEAD} value={ahead} onchange={(hours) => show({ ahead: hours })} />
		</label>
		<label class="text-muted-foreground flex items-center gap-2 text-xs">
			Colors <Choice options={COLORS} value={color} onchange={(by) => (color = by)} />
		</label>
	</Card.Content>
	<Card.Content class="text-muted-foreground flex-row flex-wrap items-center gap-x-4 gap-y-1 px-4 text-xs">
		{#each kinds as kind (kind.label)}
			<span class="flex items-center gap-1.5"><span class="h-2.5 w-4 rounded-sm" style={kind.style}></span>{kind.label}</span>
		{/each}
		<span class="flex items-center gap-1.5"><span class="bg-primary h-3 w-0.5"></span>snapshot</span>
		<span class="bg-border mx-1 h-3 w-px"></span>
		{#each Object.entries(gantt.colors[color]) as [name, fill] (name)}
			<span class="flex items-center gap-1.5"><span class="size-2.5 rounded-full" style:background={fill}></span>{name}</span>
		{/each}
		<span class="flex items-center gap-1.5"><span class="size-2.5 rounded-full" style:background={GRAY}></span>others</span>
	</Card.Content>
</Card.Root>
