import type { Component } from 'svelte';
import Activity from '@lucide/svelte/icons/activity';
import ChartGantt from '@lucide/svelte/icons/chart-gantt';
import Hourglass from '@lucide/svelte/icons/hourglass';
import Info from '@lucide/svelte/icons/info';
import ListChecks from '@lucide/svelte/icons/list-checks';
import Microchip from '@lucide/svelte/icons/microchip';
import Server from '@lucide/svelte/icons/server';
import Users from '@lucide/svelte/icons/users';
import About from './components/About.svelte';

export type Module = { id: string; title: string; icon: Component; page?: Component };

// the sidebar; a module without an own page or route shows what its router under /api/<id> computes
export const groups: { title: string; modules: Module[] }[] = [
	{
		title: 'Statistics',
		modules: [
			{ id: 'gpus', title: 'GPUs', icon: Microchip },
			{ id: 'nodes', title: 'Nodes', icon: Server },
			{ id: 'queue', title: 'Queue', icon: Hourglass },
			{ id: 'jobs', title: 'Jobs', icon: ListChecks },
			{ id: 'users', title: 'Users and accounts', icon: Users }
		]
	},
	{
		title: 'Exploration',
		modules: [{ id: 'timeline', title: 'Timeline', icon: ChartGantt }]
	},
	{
		title: 'Service',
		modules: [
			{ id: 'health', title: 'Health', icon: Activity },
			{ id: 'about', title: 'About', icon: Info, page: About }
		]
	}
];

export const modules = groups.flatMap((group) => group.modules);
