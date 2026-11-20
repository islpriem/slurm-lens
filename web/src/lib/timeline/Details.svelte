<script lang="ts">
	import X from '@lucide/svelte/icons/x';
	import { format, get, type Details } from '#lib/api.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import { query } from '#lib/settings.svelte.js';

	// what a job asked for, what the scheduler thought at the snapshot and how it ran
	let {
		job,
		at,
		status,
		color,
		onclose
	}: { job?: number; at: string; status: string; color: string; onclose: () => void } = $props();

	const details = $derived(
		job == null ? undefined : get<Details>(`timeline/jobs/${job}?${query()}&at=${encodeURIComponent(at)}`)
	);
</script>

<Card.Root class="xl:sticky xl:top-4">
	{#if details}
		{#await details}
			<Card.Header><Card.Description>Loading job {job} …</Card.Description></Card.Header>
		{:then { title, sections }}
			<Card.Header>
				<Card.Title class="flex items-center gap-2 text-base">
					<span class="size-3 rounded-full" style:background={color}></span>{title}
				</Card.Title>
				<Card.Description>{status}</Card.Description>
				<Card.Action>
					<Button variant="ghost" size="icon-sm" onclick={onclose} aria-label="Close"><X /></Button>
				</Card.Action>
			</Card.Header>
			<Card.Content class="grid gap-5">
				{#each sections as section (section.title)}
					<section>
						<h3 class="text-muted-foreground mb-1.5 text-xs font-medium tracking-wide uppercase">{section.title}</h3>
						<dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
							{#each section.rows as [name, value] (name)}
								<dt class="text-muted-foreground">{name}</dt>
								<dd class="text-right break-words tabular-nums">{format(value)}</dd>
							{/each}
						</dl>
					</section>
				{/each}
			</Card.Content>
		{:catch error}
			<Card.Header><Card.Description class="text-destructive">{error.body?.message ?? error.message}</Card.Description></Card.Header>
		{/await}
	{:else}
		<Card.Header>
			<Card.Title class="text-sm font-medium">Job details</Card.Title>
			<Card.Description>
				Click on a job to see what it asked for, what the scheduler planned at the snapshot and how it ran.
			</Card.Description>
		</Card.Header>
	{/if}
</Card.Root>
