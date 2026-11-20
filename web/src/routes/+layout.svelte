<script lang="ts">
	import './layout.css';
	import favicon from '#lib/assets/favicon.svg';
	import { resolve } from '$app/paths';
	import Settings from '#lib/components/Settings.svelte';
	import * as Sidebar from '#lib/components/ui/sidebar/index.js';
	import { groups, modules } from '#lib/modules.js';
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
		<header class="flex h-12 items-center gap-2 border-b px-4">
			<Sidebar.Trigger />
			<span class="text-sm font-medium">{current?.title}</span>
			<span class="text-muted-foreground hidden truncate text-sm md:inline">{current?.description}</span>
		</header>
		<main class="p-4 md:p-6">{@render children()}</main>
	</Sidebar.Inset>
</Sidebar.Provider>
