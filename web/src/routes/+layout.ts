import { get, type Status } from '#lib/api.js';
import type { LayoutLoad } from './$types';

// runs again for every module and refresh, so the header says when the view was generated
export const load: LayoutLoad = async ({ fetch, params }) => ({
	module: params.module,
	status: await get<Status>('health/status', fetch)
});
