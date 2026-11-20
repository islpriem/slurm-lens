import { get, type Status } from '#lib/api.js';
import type { LayoutLoad } from './$types';

// the pages are rendered in the browser only, the API serves the built files
export const ssr = false;

// runs again for every page, refresh and change of the settings, like the view itself
export const load: LayoutLoad = async ({ fetch, url, depends }) => {
	depends('app:settings');
	return { module: url.pathname.split('/')[1], status: await get<Status>('health/status', fetch) };
};
