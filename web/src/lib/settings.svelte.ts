import { browser } from '$app/env';
import { invalidate } from '$app/navigation';
import { reload } from './loading.svelte.js';

// hours back from now, or a fixed start and end (ISO); everything if none is set
export type Range = { hours?: number; from?: string; to?: string };

const KEY = 'slurm-lens';
const stored = browser ? JSON.parse(localStorage.getItem(KEY) ?? '{}') : {};

// how the timeline colors its jobs and which partitions it shows (none chosen: all)
export type Timeline = { color: 'user' | 'account'; shades: boolean; partitions: string[] };

// kept in the browser, so they survive a reload; app.html reads `dark` before the page shows
export const settings: { pseudonyms: boolean; range: Range; dark: boolean; timeline: Timeline } = $state({
	pseudonyms: true,
	range: { hours: 7 * 24 },
	dark: false,
	...stored,
	timeline: { color: 'account', shades: false, partitions: [], ...stored.timeline }
});

/** Changes the settings; the view loads again if they change what the backend computes. */
export function update(changes: Partial<typeof settings>) {
	Object.assign(settings, changes);
	localStorage.setItem(KEY, JSON.stringify(settings));
	if ('pseudonyms' in changes || 'range' in changes) return reload(invalidate('app:settings'));
}

/** The settings as query string for the backend, with the time zone of the browser. */
export function query() {
	const { hours, from, to } = settings.range;
	const start = hours ? new Date(Date.now() - hours * 3600_000).toISOString() : from;
	const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
	const params = new URLSearchParams({ pseudonyms: String(settings.pseudonyms), zone });
	if (start) params.set('start', start);
	if (to) params.set('end', to);
	return params.toString();
}
