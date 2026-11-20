<script lang="ts" generics="T">
	// a few options next to each other, one of them chosen
	let {
		options,
		value,
		onchange
	}: { options: { value: T; label: string }[]; value: T; onchange: (value: T) => void } = $props();
</script>

<div class="bg-muted inline-flex rounded-md p-0.5 text-xs">
	{#each options as option (option.label)}
		<button
			class={[
				'rounded px-2.5 py-1 transition-colors',
				option.value === value ? 'bg-background text-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground'
			]}
			onclick={() => onchange(option.value)}>{option.label}</button
		>
	{/each}
</div>
