<script lang="ts">
	import { asset } from '$app/paths';
</script>

<div class="text-muted-foreground max-w-2xl space-y-6 text-sm leading-relaxed [&_h2]:text-foreground [&_h2]:mb-2 [&_h2]:font-medium">
	<div class="text-foreground flex items-center gap-3 text-lg font-semibold">
		<img src={asset('slurmlens.svg')} alt="" class="size-10" />SlurmLens
	</div>
	<p class="text-foreground">
		SlurmLens shows how a Slurm cluster is used: how much of the GPUs and nodes is allocated, what
		waits in the queue and why, how jobs start and end, and who uses what.
	</p>

	<section>
		<h2>How it works</h2>
		<p>
			A collector asks slurmrestd every few minutes for the queue, the nodes, the configuration and
			the fairshare tree. It only reads, with the token of a normal user. The accounting records are
			fetched in fixed windows, so the job history has no gaps. Everything is stored in PostgreSQL,
			the web server computes the statistics from there and the browser draws them.
		</p>
	</section>

	<section>
		<h2>Reading the pages</h2>
		<ul class="list-disc space-y-1 pl-5">
			<li>The period in the sidebar is used by every chart over time. Charts with “now” in the title show the latest snapshot.</li>
			<li>Allocation comes from the accounting records and is averaged per hour. The newest hours are missing until their window is complete.</li>
			<li>In box plots the box is the middle half of the values, the line in it the median and the whiskers go from the 5th to the 95th percentile.</li>
			<li>Days and hours of the day are in the time zone of your browser.</li>
			<li>With pseudonyms, users and accounts are numbered by their GPU hours over the whole history (U1, A1, …). The switch in the sidebar shows the real names.</li>
			<li>Tables can be sorted by clicking on a column.</li>
		</ul>
	</section>

	<section>
		<h2>Status</h2>
		<p>Work in progress.</p>
	</section>

	<p>
		Made by Felix Triebel, open source on
		<a class="text-foreground underline underline-offset-4" href="https://github.com/islpriem/slurm-lens">GitHub</a>.
	</p>
</div>
