<script lang="ts">
	import View from '#lib/components/View.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

{#if data.view}
	<View view={data.view} />
{:else if data.module.page}
	<data.module.page />
{/if}
