<script lang="ts">
	import type { Snippet } from 'svelte';
	import * as Card from '#lib/components/ui/card/index.js';

	let { title, class: className, children }: { title: string; class?: string; children: Snippet } =
		$props();
</script>

<Card.Root class={className}>
	<Card.Header><Card.Title class="text-sm font-medium">{title}</Card.Title></Card.Header>
	<Card.Content>{@render children()}</Card.Content>
</Card.Root>
