import type { Profile } from './ocean';

/** Straight joins of recorded cast positions, never a reconstructed dive path. */
export function missionSegments(profiles: Profile[], maxGapHours = 48) {
  const missions = new Map<string, Profile[]>();
  for (const p of profiles) {
    if (!p.trajectory_id || !Number.isFinite(Date.parse(p.time))) continue;
    const group = missions.get(p.trajectory_id) || [];
    group.push(p); missions.set(p.trajectory_id, group);
  }
  const segments: [Profile, Profile][] = [];
  for (const profiles of missions.values()) {
    const ordered = [...profiles].sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
    for (let i = 1; i < ordered.length; i++) {
      const a = ordered[i - 1], b = ordered[i];
      const gap = (Date.parse(b.time) - Date.parse(a.time)) / 3600000;
      if (gap > 0 && gap <= maxGapHours && Math.abs(a.longitude-b.longitude) <= 180) segments.push([a, b]);
    }
  }
  return segments;
}
