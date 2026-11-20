<script lang="ts">
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import { invalidateAll } from '$app/navigation';
	import { time, when, type Status } from '#lib/api.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import { Separator } from '#lib/components/ui/separator/index.js';
	import { Switch } from '#lib/components/ui/switch/index.js';
	import { loading, reload } from '#lib/loading.svelte.js';
	import { settings, update } from '#lib/settings.svelte.js';
	import RangePicker from './RangePicker.svelte';

	let { status }: { status: Status } = $props();

	// every line: a label on the left, its value or control on the right
	const line = 'flex h-7 items-center justify-between gap-3';
</script>

<div class="bg-card text-muted-foreground rounded-lg border p-3 text-xs shadow-xs">
	<p class="text-foreground mb-1 font-medium">Settings</p>
	<div class={line}>
		<span>Period</span>
		<RangePicker />
	</div>
	<div class={line}>
		<Label for="pseudonyms" class="text-xs font-normal">Pseudonyms</Label>
		<Switch id="pseudonyms" size="sm" checked={settings.pseudonyms} onCheckedChange={(pseudonyms) => update({ pseudonyms })} />
	</div>
	<div class={line}>
		<Label for="dark" class="text-xs font-normal">Dark mode</Label>
		<Switch id="dark" size="sm" checked={settings.dark} onCheckedChange={(dark) => update({ dark })} />
	</div>
	<Separator class="my-2" />
	<div class={line}>
		<span>Collector</span>
		<span class="text-foreground flex items-center gap-1.5">
			<span class={['size-2 rounded-full', status.healthy ? 'bg-emerald-500' : 'bg-red-500']}></span>
			{status.healthy ? 'healthy' : 'unhealthy'}
		</span>
	</div>
	<div class={line}>
		<span>Synced</span>
		<span class="text-foreground tabular-nums">{when(status.synced_at)}</span>
	</div>
	<div class={line}>
		<span>Generated</span>
		<span class="text-foreground flex items-center gap-1 tabular-nums">
			{time(status.generated_at)}
			<Button variant="ghost" size="icon-xs" class="-mr-1" onclick={() => reload(invalidateAll())}
				disabled={loading.active} aria-label="Refresh">
				<RefreshCw class={loading.active ? 'animate-spin' : ''} />
			</Button>
		</span>
	</div>
</div>
