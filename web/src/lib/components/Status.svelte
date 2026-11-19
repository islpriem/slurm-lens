<script lang="ts">
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import { invalidateAll } from '$app/navigation';
	import { dateTime, time, type Status } from '#lib/api.js';
	import { Button } from '#lib/components/ui/button/index.js';

	let { status }: { status: Status } = $props();
	let refreshing = $state(false);

	async function refresh() {
		refreshing = true;
		await invalidateAll();
		refreshing = false;
	}
</script>

<div class="text-muted-foreground ml-auto flex items-center gap-3 text-xs">
	<span class="hidden sm:inline">Generated {time(status.generated_at)}</span>
	<span class="hidden sm:inline">Synced {dateTime(status.synced_at)}</span>
	<span class="flex items-center gap-1.5">
		<span class={['size-2 rounded-full', status.healthy ? 'bg-emerald-500' : 'bg-red-500']}></span>
		{status.healthy ? 'Healthy' : 'Unhealthy'}
	</span>
	<Button variant="ghost" size="icon-sm" onclick={refresh} disabled={refreshing} aria-label="Refresh">
		<RefreshCw class={refreshing ? 'animate-spin' : ''} />
	</Button>
</div>
