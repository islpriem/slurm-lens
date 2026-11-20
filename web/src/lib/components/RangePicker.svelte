<script lang="ts">
	import CalendarRange from '@lucide/svelte/icons/calendar-range';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import * as Popover from '#lib/components/ui/popover/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { settings, update, type Range } from '#lib/settings.svelte.js';

	const PRESETS: { label: string; range: Range }[] = [
		{ label: 'Last 24 hours', range: { hours: 24 } },
		{ label: 'Last 7 days', range: { hours: 7 * 24 } },
		{ label: 'Last 30 days', range: { hours: 30 * 24 } },
		{ label: 'Last 90 days', range: { hours: 90 * 24 } },
		{ label: 'Everything', range: {} }
	];

	// datetime-local inputs hold local times without a zone, e.g. 2026-11-20T14:30
	const input = (iso?: string) => {
		if (!iso) return '';
		const date = new Date(iso);
		return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
	};
	const short = (local: string) =>
		local ? new Date(local).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }) : 'now';

	let open = $state(false);
	let from = $state(input(settings.range.from));
	let to = $state(input(settings.range.to));
	const preset = $derived(PRESETS.find((p) => JSON.stringify(p.range) === JSON.stringify(settings.range)));

	function pick(range: Range) {
		open = false;
		update({ range });
	}

	function apply(event: SubmitEvent) {
		event.preventDefault();
		pick({ from: new Date(from).toISOString(), to: to ? new Date(to).toISOString() : undefined });
	}
</script>

<Popover.Root bind:open>
	<Popover.Trigger>
		{#snippet child({ props })}
			<Button {...props} variant="outline" size="xs" class="min-w-0 font-normal">
				<CalendarRange /><span class="truncate">{preset?.label ?? `${short(from)} – ${short(to)}`}</span>
			</Button>
		{/snippet}
	</Popover.Trigger>
	<Popover.Content side="right" align="end" class="grid w-64 gap-3">
		<div class="grid">
			{#each PRESETS as { label, range } (label)}
				<Button variant={preset?.label === label ? 'secondary' : 'ghost'} size="sm" class="justify-start"
					onclick={() => pick(range)}>{label}</Button>
			{/each}
		</div>
		<Separator />
		<form class="grid gap-2" onsubmit={apply}>
			<Label class="grid gap-1 text-xs">From<Input type="datetime-local" bind:value={from} required /></Label>
			<Label class="grid gap-1 text-xs">To<Input type="datetime-local" bind:value={to} /></Label>
			<Button type="submit" size="sm">Apply</Button>
		</form>
	</Popover.Content>
</Popover.Root>
