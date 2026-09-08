export function validRegion(value: unknown, bounds: number[] = [-180, -90, 180, 90]): value is number[] {
  return Array.isArray(value) && value.length === 4 && value.every(v => typeof v === 'number' && Number.isFinite(v)) &&
    value[0] >= bounds[0] && value[1] >= bounds[1] && value[2] <= bounds[2] && value[3] <= bounds[3] &&
    value[0] < value[2] && value[1] < value[3] && value[2] - value[0] <= 180;
}
