import React from "react";

interface Props {
  score: number;       // 0..100
  band: "low" | "medium" | "high";
  size?: number;
}

const COLOR_BY_BAND = {
  low: "#15803d",
  medium: "#b45309",
  high: "#b91c1c",
};

/** Semi-circular risk gauge — pure SVG, no extra deps. */
const RiskScoreGauge: React.FC<Props> = ({ score, band, size = 220 }) => {
  const s = Math.max(0, Math.min(100, score));
  const radius = size / 2 - 12;
  const cx = size / 2;
  const cy = size / 2;
  const start = Math.PI;             // 180°
  const end = 2 * Math.PI;           // 360°
  const t = s / 100;
  const angle = start + (end - start) * t;

  const x1 = cx + radius * Math.cos(start);
  const y1 = cy + radius * Math.sin(start);
  const x2 = cx + radius * Math.cos(end);
  const y2 = cy + radius * Math.sin(end);
  const xa = cx + radius * Math.cos(angle);
  const ya = cy + radius * Math.sin(angle);

  const trackPath = `M ${x1} ${y1} A ${radius} ${radius} 0 0 1 ${x2} ${y2}`;
  const fillPath = `M ${x1} ${y1} A ${radius} ${radius} 0 0 1 ${xa} ${ya}`;
  const color = COLOR_BY_BAND[band];

  return (
    <svg width={size} height={size / 1.6} viewBox={`0 0 ${size} ${size / 1.6}`}>
      <path d={trackPath} fill="none" stroke="#e2e8f0" strokeWidth={16} strokeLinecap="round" />
      <path d={fillPath} fill="none" stroke={color} strokeWidth={16} strokeLinecap="round" />
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize={36} fontWeight={700} fill={color}>
        {s}
      </text>
      <text x={cx} y={cy + 22} textAnchor="middle" fontSize={13} fill="#475569">
        Risk score · <tspan fontWeight={600}>{band.toUpperCase()}</tspan>
      </text>
    </svg>
  );
};

export default RiskScoreGauge;
