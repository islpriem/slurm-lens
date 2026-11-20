import { select, type Axis, type AxisDomain } from 'd3';

export const margin = { top: 8, right: 12, bottom: 24, left: 48 };

/** A d3 axis as attachment: <g {@attach axis(axisBottom(x))} />, its labels tilted if asked. */
export const axis =
	<D extends AxisDomain>(scale: Axis<D>, tilt = false) =>
	(g: SVGGElement) => {
		const labels = select(g).call(scale).selectAll('text');
		if (tilt) labels.attr('transform', 'rotate(-35)').attr('text-anchor', 'end').attr('dx', '-0.3em').attr('dy', '0.3em');
	};

/** A value axis with light grid lines across a plot of the given size instead of a domain line. */
export const grid =
	<D extends AxisDomain>(scale: Axis<D>, size: number) =>
	(g: SVGGElement) => {
		select(g)
			.call(scale.tickSize(-size).tickPadding(6))
			.call((g) => g.select('.domain').remove())
			.call((g) => g.selectAll('.tick line').attr('stroke-opacity', 0.12));
	};

/**
 * How to label a category axis with `step` pixels per category: all labels, tilted if they are
 * too long for their place, or with many categories only as many as fit.
 */
export function categories(labels: string[], step: number) {
	const longest = 6.5 * Math.max(0, ...labels.map((label) => label.length));
	if (longest <= step) return { labels, tilt: false, bottom: margin.bottom };
	if (labels.length <= 30) return { labels, tilt: true, bottom: 12 + 0.6 * longest };
	const every = Math.ceil(longest / step);
	return { labels: labels.filter((_, i) => i % every === 0), tilt: false, bottom: margin.bottom };
}
