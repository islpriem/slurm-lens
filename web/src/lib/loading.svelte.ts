import { navigating } from '$app/state';

// a refresh or other settings load the view again without a navigation
let reloads = $state(0);

/** Waits for work that loads the view again, so the page can show that it is loading meanwhile. */
export async function reload(work: Promise<unknown>) {
	reloads++;
	try {
		await work;
	} finally {
		reloads--;
	}
}

export const loading = {
	get active() {
		return navigating.to != null || reloads > 0;
	}
};
