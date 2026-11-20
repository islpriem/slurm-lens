import { error } from '@sveltejs/kit';
import { get, type View } from '#lib/api.js';
import { modules } from '#lib/modules.js';
import { query } from '#lib/settings.svelte.js';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params, depends }) => {
	depends('app:settings');
	const module = modules.find((module) => module.id === params.module);
	if (!module) error(404, `There is no module "${params.module}".`);
	return { module, view: module.page ? null : await get<View>(`${module.id}?${query()}`, fetch) };
};
