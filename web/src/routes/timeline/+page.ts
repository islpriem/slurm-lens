import { get, type Gantt } from '#lib/api.js';
import { query } from '#lib/settings.svelte.js';
import type { PageLoad } from './$types';

// the snapshot (at) and how far ahead to look are in the url, so a view can be shared
export const load: PageLoad = async ({ fetch, url, depends }) => {
	depends('app:settings');
	const params = new URLSearchParams(query());
	for (const key of ['at', 'ahead']) {
		const value = url.searchParams.get(key);
		if (value) params.set(key, value);
	}
	return { gantt: await get<Gantt>(`timeline?${params}`, fetch) };
};
