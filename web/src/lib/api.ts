import { error } from '@sveltejs/kit';

// what the backend computes, see src/slurm_lens/api/view.py
export type Series = { name: string; color: string; y: (number | null)[] };
export type Chart = {
	title: string;
	kind: 'line' | 'dot' | 'bar';
	x: string[];
	series: Series[];
	y_max: number | null;
	log: boolean;
	wide: boolean;
};
export type Tile = { title: string; value: string | number | null; note: string };
export type View = { tiles: Tile[]; charts: Chart[] };
export type Status = { generated_at: string; synced_at: string | null; healthy: boolean };

export async function get<T>(path: string, fetcher = fetch): Promise<T> {
	const response = await fetcher(`/api/${path}`);
	if (!response.ok) {
		const { detail } = await response.json().catch(() => ({}));
		error(response.status, detail ?? response.statusText);
	}
	return response.json();
}

export const dateTime = (value: string | null) =>
	value ? new Date(value).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }) : '–';

export const time = (value: string) => new Date(value).toLocaleTimeString('en-GB', { timeStyle: 'medium' });

export const number = (value: number | null) => (value == null ? '–' : value.toLocaleString('en-GB'));
