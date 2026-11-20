<script lang="ts">
	import { jobColor, PLANNED, RUNNING } from '#lib/api.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import Details from '#lib/timeline/Details.svelte';
	import Gantt from '#lib/timeline/Gantt.svelte';
	import Toolbar from '#lib/timeline/Toolbar.svelte';
	import { settings } from '#lib/settings.svelte.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
	let selected = $state<number>(); // job id, it stays selected while going through the snapshots

	const job = $derived(data.gantt.jobs.findIndex(([id]) => id === selected));
	const status = $derived.by(() => {
		const kinds = data.gantt.bars.filter((bar) => bar[0] === job).map((bar) => bar[4]);
		if (kinds.includes(PLANNED)) return 'planned by the scheduler at the snapshot';
		if (kinds.includes(RUNNING)) return 'running at the snapshot';
		return kinds.length ? 'ran before the snapshot' : 'not on the GPUs in this period';
	});
</script>

<svelte:window onkeydown={(event) => event.key === 'Escape' && (selected = undefined)} />

<div class="grid gap-4">
	<Toolbar gantt={data.gantt} />
	<div class="grid items-start gap-4 xl:grid-cols-3">
		<Card.Root class="py-3 xl:col-span-2">
			<Card.Content class="px-3">
				<Gantt gantt={data.gantt} {...settings.timeline} bind:selected />
			</Card.Content>
		</Card.Root>
		<Details
			job={selected}
			at={data.gantt.at}
			{status}
			color={job >= 0 ? jobColor(data.gantt, job, settings.timeline.color, settings.timeline.shades) : 'transparent'}
			onclose={() => (selected = undefined)}
		/>
	</div>
</div>
