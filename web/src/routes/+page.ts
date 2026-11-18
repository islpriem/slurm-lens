import { redirect } from '@sveltejs/kit';
import { resolve } from '$app/paths';
import { modules } from '#lib/modules.js';

export function load() {
	redirect(307, resolve('/[module]', { module: modules[0].id }));
}
