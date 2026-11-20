import { error } from '@sveltejs/kit';
import { hsl } from 'd3';

// what the backend computes, see src/slurm_lens/api/view.py
export type Cell = string | number | null;
export type Value = number | number[] | null; // box plots: low, q1, median, q3, high
export type Series = { name: string; color: string; y: Value[] };
export type Chart = {
	kind: 'line' | 'area' | 'dot' | 'bar' | 'pie' | 'box' | 'heatmap' | 'ranking';
	title: string;
	x: string[]; // times (ISO) or categories, numbers for lines over numbers
	series: Series[];
	unit: string; // after every value, e.g. " %"
	x_unit: string;
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
// the timeline, see src/slurm_lens/api/timeline.py
export const RAN = 0, RUNNING = 1, PLANNED = 2;
export type Gantt = {
	at: string;
	start: string;
	end: string;
	snapshots: string[];
	nodes: { name: string; model: string; gpus: number; partitions: string[]; state: string | null }[];
	jobs: [id: number, user: string, account: string][];
	bars: [job: number, row: number, start: number, end: number, kind: number][];
	colors: { user: Record<string, string>; account: Record<string, string> };
};
export const GRAY = '#bdbcb6';
/**
 * The color of a job by its user or account; only the ones with the most GPU time have one. With
 * shades every user gets a lighter or darker variant, so that neighbours of the same color differ.
 */
export function jobColor(gantt: Gantt, job: number, by: 'user' | 'account', shades = false) {
	const [, user, account] = gantt.jobs[job];
	const color = gantt.colors[by][by === 'user' ? user : account] ?? GRAY;
	return shades ? shade(color, user) : color;
}

/** The same lighter or darker variant of a color for the same name. */
function shade(color: string, name: string) {
	let hash = 2166136261; // FNV-1a
	for (const char of name) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
	const tone = hsl(color);
	tone.l = Math.min(0.85, Math.max(0.2, tone.l + ((hash >>> 0) / 2 ** 32 - 0.5) * 0.36));
	return tone.formatHex();
}
export type Details = { title: string; sections: { title: string; rows: [string, Cell][] }[] };
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

/** '45 min', '3 h 20 min' or '2 days 5 h' for milliseconds. */
export function duration(ms: number) {
	const minutes = Math.round(ms / 60_000);
	const [days, hours] = [Math.floor(minutes / 1440), Math.floor(minutes / 60) % 24];
	const parts = days ? [[days, 'days'], [hours, 'h']] : [[Math.floor(minutes / 60), 'h'], [minutes % 60, 'min']];
	return parts.filter(([n]) => n).map((part) => part.join(' ')).join(' ') || '0 min';
}
