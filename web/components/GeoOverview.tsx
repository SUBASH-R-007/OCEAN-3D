/* oxlint-disable react/react-compiler, jsx-a11y/prefer-tag-over-role -- Compiler invariant in nested clipped SVG paths; SVG role=img supplies an accessible name. */
import { useEffect, useState } from 'react';
import { loadCoastline, clipSegment, type Coastline } from '@/lib/geography';
import type { Volume, Profile } from '@/lib/ocean';
export default function GeoOverview({
  field,
  profiles,
}: {
  field: Volume;
  profiles: Profile[];
}) {
  const [coast, setCoast] = useState<Coastline>([]);
  useEffect(() => {
    let active = true;
    loadCoastline()
      .then((c) => {
        if (active) setCoast(c);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  const b = [
      Math.min(30, field.axes.longitude[0]),
      Math.min(-30, field.axes.latitude[0]),
      Math.max(120, field.axes.longitude.at(-1)!),
      Math.max(30, field.axes.latitude.at(-1)!),
    ],
    x = (lo: number) => ((lo - b[0]) / (b[2] - b[0])) * 180 + 10,
    y = (la: number) => ((b[3] - la) / (b[3] - b[1])) * 130 + 10;
  const path = coast
    .flatMap((line) =>
      line.slice(1).flatMap((p, i) => {
        const clip = clipSegment(line[i], p, b);
        return clip
          ? [
              `M${x(clip[0][0])},${y(clip[0][1])}L${x(clip[1][0])},${y(clip[1][1])}`,
            ]
          : [];
      }),
    )
    .join(' ');
  const west = field.axes.longitude[0],
    east = field.axes.longitude.at(-1)!,
    south = field.axes.latitude[0],
    north = field.axes.latitude.at(-1)!;
  return (
    <div className="geo-overview">
      <svg
        viewBox="0 0 200 157"
        role="img"
        aria-label="Indian Ocean geographic overview with current model extent"
      >
        <title>
          Natural Earth coastline; outlined rectangle is the displayed regional
          volume
        </title>
        {[0, 10, 20].map((lat) => (
          <line
            key={lat}
            x1="10"
            x2="190"
            y1={y(lat)}
            y2={y(lat)}
            stroke="#23404e"
            strokeDasharray="2 4"
          />
        ))}
        <path d={path} fill="none" stroke="#819da6" strokeWidth=".8" />
        <rect
          x={x(west)}
          y={y(north)}
          width={Math.max(2, x(east) - x(west))}
          height={Math.max(2, y(south) - y(north))}
          fill="#56d9cf26"
          stroke="#5cdfd4"
          strokeWidth="1.4"
        />
        {profiles
          .filter(
            (p) =>
              p.longitude >= b[0] &&
              p.longitude <= b[2] &&
              p.latitude >= b[1] &&
              p.latitude <= b[3],
          )
          .map((p) => (
            <circle
              key={p.id}
              cx={x(p.longitude)}
              cy={y(p.latitude)}
              r="1.6"
              fill={p.synthetic ? '#efb77c' : '#7fdaff'}
            />
          ))}
        <text x={x(78)} y={y(22)}>
          INDIA
        </text>
        <text x={x(55)} y={y(-20)}>
          INDIAN OCEAN
        </text>
        <text x="182" y="19">
          N ↑
        </text>
      </svg>
      <span>Natural Earth 1:110m · geographic context</span>
    </div>
  );
}
