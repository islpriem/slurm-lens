import { get, type Status } from '#lib/api.js';
import type { LayoutLoad } from './$types';

// runs again for every module, refresh and change of the settings, like the view itself
export const load: LayoutLoad = async ({ fetch, params, depends }) => {
	depends('app:settings');
	return { module: params.module, status: await get<Status>('health/status', fetch) };
};
