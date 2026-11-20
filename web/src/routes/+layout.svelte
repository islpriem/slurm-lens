<script lang="ts">
	import './layout.css';
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import { onMount } from 'svelte';
	import { asset, resolve } from '$app/paths';
	import Settings from '#lib/components/Settings.svelte';
	import * as Sidebar from '#lib/components/ui/sidebar/index.js';
	import { loading } from '#lib/loading.svelte.js';
	import { groups, modules } from '#lib/modules.js';
	import { settings } from '#lib/settings.svelte.js';
	import type { LayoutProps } from './$types';

	let { data, children }: LayoutProps = $props();
	const current = $derived(modules.find((module) => module.id === data.module));

	$effect(() => {
		document.documentElement.classList.toggle('dark', settings.dark);
	});
	// app.html shows a splash until the first page is there
	onMount(() => document.getElementById('splash')?.remove());
</script>

<svelte:head>
	<title>{current ? `${current.title} · SlurmLens` : 'SlurmLens'}</title>
</svelte:head>

<Sidebar.Provider>
	<Sidebar.Root>
		<!-- in one line with the title of the page: same padding, height and font -->
		<Sidebar.Header class="px-4 pt-5 pb-2">
			<a href={resolve('/')} class="flex h-8 items-center gap-2 text-xl font-semibold tracking-tight">
				<img src={asset('slurmlens.svg')} alt="" class="size-7" />SlurmLens
			</a>
		</Sidebar.Header>
		<Sidebar.Content>
			{#each groups as group (group.title)}
				<Sidebar.Group>
					<Sidebar.GroupLabel>{group.title}</Sidebar.GroupLabel>
					<Sidebar.Menu>
						{#each group.modules as module (module.id)}
							<Sidebar.MenuItem>
								<Sidebar.MenuButton isActive={module === current}>
									{#snippet child({ props })}
										<a href={resolve('/[module]', { module: module.id })} {...props}>
											<module.icon /><span>{module.title}</span>
										</a>
									{/snippet}
								</Sidebar.MenuButton>
							</Sidebar.MenuItem>
						{/each}
					</Sidebar.Menu>
				</Sidebar.Group>
			{/each}
		</Sidebar.Content>
		<Sidebar.Footer><Settings status={data.status} /></Sidebar.Footer>
	</Sidebar.Root>
	<Sidebar.Inset>
		<header class="flex items-center gap-3 px-4 pt-4 md:px-6 md:pt-5">
			<Sidebar.Trigger class="-ml-1" />
			<h1 class="text-xl font-semibold tracking-tight">{current?.title}</h1>
			{#if loading.active}<LoaderCircle class="text-muted-foreground size-5 animate-spin" />{/if}
		</header>
		<!-- while a view loads, the old one stays greyed out and cannot be clicked -->
		<div class={['p-4 transition-opacity md:p-6', loading.active && 'pointer-events-none opacity-40']} aria-busy={loading.active}>
			{@render children()}
		</div>
	</Sidebar.Inset>
</Sidebar.Provider>
