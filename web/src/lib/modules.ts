import type { Component } from 'svelte';
import Activity from '@lucide/svelte/icons/activity';
import ChartColumn from '@lucide/svelte/icons/chart-column';

export type Module = { id: string; title: string; icon: Component };

// one sidebar item per module; the backend computes its view under /api/<id>
export const modules: Module[] = [
	{ id: 'health', title: 'Health', icon: Activity },
	{ id: 'stats', title: 'Statistics', icon: ChartColumn }
];
