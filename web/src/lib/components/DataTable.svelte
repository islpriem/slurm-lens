<script lang="ts">
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import { format, type Cell, type Table } from '#lib/api.js';
	import * as T from '#lib/components/ui/table/index.js';

	let { table }: { table: Table } = $props();

	// columns with numbers are aligned right and sorted largest first
	const numeric = $derived(table.columns.map((_, j) => table.rows.some((row) => typeof row[j] === 'number')));
	let sort = $state<{ column: number; descending: boolean }>();
	// empty cells always last
	const compare = (a: Cell, b: Cell) =>
		a == null || b == null ? 0 : typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b));
	const rows = $derived.by(() => {
		if (!sort) return table.rows;
		const { column, descending } = sort;
		return table.rows.toSorted(
			(a, b) => Number(a[column] == null) - Number(b[column] == null) || compare(a[column], b[column]) * (descending ? -1 : 1)
		);
	});

	function order(column: number) {
		sort = sort?.column === column ? { column, descending: !sort.descending } : { column, descending: numeric[column] };
	}
</script>

<div class="max-h-[30rem] overflow-auto">
	<T.Root class="text-xs">
		<T.Header class="bg-card sticky top-0 z-10">
			<T.Row>
				{#each table.columns as column, j (column)}
					<T.Head class={numeric[j] ? 'text-right' : ''}>
						<button class="hover:text-foreground inline-flex items-center gap-1" onclick={() => order(j)}>
							{column}
							{#if sort?.column === j}
								{#if sort.descending}<ArrowDown class="size-3" />{:else}<ArrowUp class="size-3" />{/if}
							{/if}
						</button>
					</T.Head>
				{/each}
			</T.Row>
		</T.Header>
		<T.Body>
			{#each rows as row, i (i)}
				<T.Row>
					{#each row as cell, j (j)}
						<T.Cell class={numeric[j] ? 'text-right tabular-nums' : 'max-w-xs truncate'} title={String(cell ?? '')}>
							{format(cell)}
						</T.Cell>
					{/each}
				</T.Row>
			{/each}
		</T.Body>
	</T.Root>
</div>
