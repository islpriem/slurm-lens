import { error } from '@sveltejs/kit';

// what the backend computes, see src/slurm_lens/api/view.py
export type Cell = string | number | null;
export type Value = number | number[] | null; // box plots: low, q1, median, q3, high
export type Series = { name: string; color: string; y: Value[] };
export type Chart = {
	kind: 'line' | 'area' | 'dot' | 'bar' | 'pie' | 'box' | 'heatmap' | 'ranking';
	title: string;
	x: string[];
	series: Series[];
	unit: string; // after every value, e.g. " %"
	note: string;
	stats: Record<string, string>;
	y_max: number | null;
	stacked: boolean;
	horizontal: boolean;
	wide: boolean;
};
export type Table = { kind: 'table'; title: string; columns: string[]; rows: Cell[][]; wide: boolean };
export type Tile = { title: string; value: Cell; note: string; status: 'ok' | 'warn' | 'fail' | null };
export type View = { tiles: Tile[]; panels: (Chart | Table)[] };
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

/** The time of day if it is today, otherwise with the date. */
export const when = (value: string | null) => {
	if (!value) return 'never';
	const date = new Date(value);
	const today = date.toDateString() === new Date().toDateString();
	return date.toLocaleString('en-GB', today ? { timeStyle: 'short' } : { dateStyle: 'medium', timeStyle: 'short' });
};

export const time = (value: string) => new Date(value).toLocaleTimeString('en-GB', { timeStyle: 'medium' });

/** Fewer decimals the larger the number, e.g. 0.25, 12.5, 1,234. */
export const number = (value: number) =>
	value.toLocaleString('en-GB', { maximumFractionDigits: Math.abs(value) >= 100 ? 0 : Math.abs(value) >= 10 ? 1 : 2 });

/** Numbers, times (ISO strings from the backend) and text, as they are shown. */
export const format = (value: Cell) =>
	value == null ? '–' : typeof value === 'number' ? number(value) : /^\d{4}-\d\d-\d\dT/.test(value) ? dateTime(value) : value;
