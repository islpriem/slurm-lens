<script lang="ts">
	import './layout.css';
	import favicon from '#lib/assets/favicon.svg';
	import { resolve } from '$app/paths';
	import Status from '#lib/components/Status.svelte';
	import * as Sidebar from '#lib/components/ui/sidebar/index.js';
	import { modules } from '#lib/modules.js';
	import type { LayoutProps } from './$types';

	let { data, children }: LayoutProps = $props();
	const current = $derived(modules.find((module) => module.id === data.module));
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>slurm-lens{current ? ` · ${current.title}` : ''}</title>
</svelte:head>

<Sidebar.Provider>
	<Sidebar.Root>
		<Sidebar.Header class="px-4 py-3 font-semibold">slurm-lens</Sidebar.Header>
		<Sidebar.Content>
			<Sidebar.Group>
				<Sidebar.Menu>
					{#each modules as module (module.id)}
						<Sidebar.MenuItem>
							<Sidebar.MenuButton isActive={module === current}>
								{#snippet child({ props })}
									<a href={resolve('/[module]', { module: module.id })} {...props}><module.icon /><span>{module.title}</span></a>
								{/snippet}
							</Sidebar.MenuButton>
						</Sidebar.MenuItem>
					{/each}
				</Sidebar.Menu>
			</Sidebar.Group>
		</Sidebar.Content>
	</Sidebar.Root>
	<Sidebar.Inset>
		<header class="flex h-12 items-center gap-2 border-b px-4">
			<Sidebar.Trigger />
			<span class="text-sm font-medium">{current?.title}</span>
			<Status status={data.status} />
		</header>
		<main class="p-4 md:p-6">{@render children()}</main>
	</Sidebar.Inset>
</Sidebar.Provider>
