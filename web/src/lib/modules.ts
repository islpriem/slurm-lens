import type { Component } from 'svelte';
import Activity from '@lucide/svelte/icons/activity';
import Hourglass from '@lucide/svelte/icons/hourglass';
import Info from '@lucide/svelte/icons/info';
import ListChecks from '@lucide/svelte/icons/list-checks';
import Microchip from '@lucide/svelte/icons/microchip';
import Server from '@lucide/svelte/icons/server';
import Users from '@lucide/svelte/icons/users';
import About from './components/About.svelte';

export type Module = { id: string; title: string; description: string; icon: Component; page?: Component };

// the sidebar; a module without an own page shows what its router under /api/<id> computes
export const groups: { title: string; modules: Module[] }[] = [
	{
		title: 'Statistics',
		modules: [
			{ id: 'gpus', title: 'GPUs', description: 'How much of each GPU model is allocated', icon: Microchip },
			{ id: 'nodes', title: 'Nodes', description: 'State of the nodes and how full they are', icon: Server },
			{ id: 'queue', title: 'Queue', description: 'What waits, why and for how long', icon: Hourglass },
			{ id: 'jobs', title: 'Jobs', description: 'How large jobs are, how they start and end', icon: ListChecks },
			{ id: 'users', title: 'Users and accounts', description: 'Who uses the GPUs and who waits', icon: Users }
		]
	},
	{
		title: 'Service',
		modules: [
			{ id: 'health', title: 'Health', description: 'Whether the data collection works', icon: Activity },
			{ id: 'about', title: 'About', description: 'What this is and how it works', icon: Info, page: About }
		]
	}
];

export const modules = groups.flatMap((group) => group.modules);
