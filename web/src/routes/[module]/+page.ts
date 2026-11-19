import { error } from '@sveltejs/kit';
import { get, type View } from '#lib/api.js';
import { modules } from '#lib/modules.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	if (!modules.some((module) => module.id === params.module)) {
		error(404, `There is no module "${params.module}".`);
	}
	return { view: await get<View>(params.module, fetch) };
};
