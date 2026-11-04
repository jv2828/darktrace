import React, { useMemo, useState } from 'react';
import { getIndicatorConfig, formatIndicatorDetails } from '../../lib/indicatorTypes';

/**
 * HighlightedText component for rendering raw post text with overlaid, interactive
 * indicator annotations.
 *
 * Slices the text into pure React text nodes and styled <mark> elements.
 * Strictly avoids dangerouslySetInnerHTML.
 *
 * @param {object} props
 * @param {string} props.text - Full raw string to display
 * @param {Array<object>} props.indicators - Extracted indicators with span_start and span_end
 * @param {function} [props.onIndicatorClick] - Optional callback when an indicator mark is clicked
 * @param {string} [props.className] - Container CSS classes
 */
export default function HighlightedText({
  text = '',
  indicators = [],
  onIndicatorClick,
  className = '',
}) {
  const [activeTooltip, setActiveTooltip] = useState(null);

  // Compute non-overlapping slice segments
  const segments = useMemo(() => {
    if (!text || typeof text !== 'string') {
      return [{ type: 'text', content: text || '', key: 'empty' }];
    }

    // Filter only indicators that have valid span bounds within text length
    const validIndicators = (indicators || [])
      .filter(
        (ind) =>
          ind &&
          typeof ind.span_start === 'number' &&
          typeof ind.span_end === 'number' &&
          ind.span_start >= 0 &&
          ind.span_end <= text.length &&
          ind.span_start < ind.span_end
      )
      .slice();

    // Sort by span_start ascending, then span_end descending (longest first)
    validIndicators.sort((a, b) => a.span_start - b.span_start || b.span_end - a.span_end);

    const nonOverlapping = [];
    let lastEnd = 0;

    for (const ind of validIndicators) {
      if (ind.span_start < lastEnd) {
        // Overlap detected: guard against invalid spans
        console.warn(
          `[HighlightedText] Skipping overlapping indicator ${ind.indicator_type} [${ind.span_start}, ${ind.span_end}) because previous ended at ${lastEnd}`
        );
        continue;
      }
      nonOverlapping.push(ind);
      lastEnd = ind.span_end;
    }

    const segs = [];
    let currentIdx = 0;

    nonOverlapping.forEach((ind, index) => {
      // 1. Text before this indicator
      if (ind.span_start > currentIdx) {
        segs.push({
          type: 'text',
          content: text.slice(currentIdx, ind.span_start),
          key: `txt-${currentIdx}-${ind.span_start}`,
        });
      }

      // 2. Highlighted indicator slice
      segs.push({
        type: 'indicator',
        indicator: ind,
        content: text.slice(ind.span_start, ind.span_end),
        key: `ind-${ind.id || index}-${ind.span_start}-${ind.span_end}`,
      });

      currentIdx = ind.span_end;
    });

    // 3. Trailing text after the last indicator
    if (currentIdx < text.length) {
      segs.push({
        type: 'text',
        content: text.slice(currentIdx),
        key: `txt-${currentIdx}-${text.length}`,
      });
    }

    return segs;
  }, [text, indicators]);

  return (
    <div
      className={`font-mono text-sm leading-relaxed whitespace-pre-wrap break-words rounded-lg p-4 bg-slate-950/80 border border-slate-800 text-slate-200 select-text ${className}`}
    >
      {segments.map((seg) => {
        if (seg.type === 'text') {
          return <React.Fragment key={seg.key}>{seg.content}</React.Fragment>;
        }

        const { indicator, content, key } = seg;
        const config = getIndicatorConfig(indicator.indicator_type);
        const detailStr = formatIndicatorDetails(indicator);
        const isHovered = activeTooltip === key;

        return (
          <span
            key={key}
            className="relative inline-block my-0.5 group"
            onMouseEnter={() => setActiveTooltip(key)}
            onMouseLeave={() => setActiveTooltip(null)}
          >
            <mark
              onClick={() => onIndicatorClick && onIndicatorClick(indicator)}
              className={`cursor-pointer rounded px-1 py-0.5 font-medium transition-colors ${config.highlightClass} ${
                onIndicatorClick ? 'hover:ring-1 hover:ring-current' : ''
              }`}
              title={`${config.label} (${indicator.confidence || 'high'})`}
            >
              {content}
            </mark>

            {/* Accessible interactive hover tooltip */}
            {isHovered && (
              <span
                role="tooltip"
                className="absolute z-30 bottom-full left-1/2 -translate-x-1/2 mb-2 w-max max-w-xs px-2.5 py-1.5 text-xs rounded-md shadow-xl bg-slate-900 border border-slate-700 text-slate-100 flex flex-col gap-0.5 pointer-events-none"
              >
                <span className="flex items-center gap-1.5 font-semibold">
                  <span
                    className="w-2 h-2 rounded-full inline-block"
                    style={{ backgroundColor: config.dotColor }}
                  />
                  <span>{config.label}</span>
                  <span
                    className={`ml-auto text-[10px] px-1 py-0.2 rounded uppercase font-bold ${
                      indicator.confidence === 'high'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : indicator.confidence === 'medium'
                        ? 'bg-amber-500/20 text-amber-400'
                        : 'bg-rose-500/20 text-rose-400'
                    }`}
                  >
                    {indicator.confidence || 'high'}
                  </span>
                </span>
                {detailStr && (
                  <span className="text-[11px] text-slate-400 font-normal">
                    {detailStr}
                  </span>
                )}
                {indicator.normalised_value && indicator.normalised_value !== content && (
                  <span className="text-[10px] text-slate-400 font-mono truncate">
                    Norm: {indicator.normalised_value}
                  </span>
                )}
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}

