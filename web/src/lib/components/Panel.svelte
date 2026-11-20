<script lang="ts">
	import type { Snippet } from 'svelte';
	import * as Card from '#lib/components/ui/card/index.js';

	let {
		title,
		note = '',
		stats = {},
		class: className,
		children
	}: { title: string; note?: string; stats?: Record<string, string>; class?: string; children: Snippet } =
		$props();
</script>

<Card.Root class={className}>
	<Card.Header>
		<Card.Title class="text-sm font-medium">{title}</Card.Title>
		{#if note}<Card.Description class="text-xs">{note}</Card.Description>{/if}
		{#if Object.keys(stats).length}
			<dl class="mt-2 flex flex-wrap gap-x-8 gap-y-2">
				{#each Object.entries(stats) as [label, value] (label)}
					<div>
						<dd class="text-base font-semibold tabular-nums">{value}</dd>
						<dt class="text-muted-foreground text-xs">{label}</dt>
					</div>
				{/each}
			</dl>
		{/if}
	</Card.Header>
	<!-- charts that are smaller than their row stay in the middle of the card -->
	<Card.Content class="flex flex-1 flex-col justify-center">{@render children()}</Card.Content>
</Card.Root>
