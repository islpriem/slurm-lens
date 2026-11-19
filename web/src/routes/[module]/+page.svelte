<script lang="ts">
	import View from '#lib/components/View.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<View view={data.view} />
