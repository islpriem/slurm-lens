<script lang="ts">
	import { page } from '$app/state';
</script>

<p class="text-destructive text-sm">{page.status}: {page.error?.message}</p>
