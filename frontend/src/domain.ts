/** Money stays in integer paise. Previews are estimates; saved server shares are authoritative. */
export function parseMoney(value: string, allowZero = false): number | null {
  const v = value.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(v)) return null;
  const [whole, fraction = ""] = v.split(".");
  const minor = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(minor) &&
    minor <= 1_000_000_000 &&
    (allowZero ? minor >= 0 : minor > 0)
    ? minor
    : null;
}
export function splitPreview(value: string, members: { id: number }[]) {
  const minor = parseMoney(value);
  if (minor === null || !members.length) return [];
  const sorted = [...members].sort((a, b) => a.id - b.id);
  return sorted.map((p, i) => ({
    id: p.id,
    minor:
      Math.floor(minor / sorted.length) + (i < minor % sorted.length ? 1 : 0),
  }));
}
export function customPreview(
  value: string,
  members: { id: number }[],
  shares: Record<number, string>,
) {
  const minor = parseMoney(value);
  const amounts = members.map((p) => parseMoney(shares[p.id] ?? "", true));
  const total = amounts.reduce<number>((s, n) => s + (n ?? 0), 0);
  return {
    total,
    remaining: (minor ?? 0) - total,
    valid:
      minor !== null &&
      members.length > 0 &&
      amounts.every((n) => n !== null) &&
      total === minor,
  };
}
export function formatMoney(minor: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  }).format(minor / 100);
}
export function personLabel(person: { id: number; name: string }) {
  return `${person.name} · #${person.id}`;
}
export function validPhoto(file: File) {
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type))
    return "Choose a JPEG, PNG or WebP photo.";
  if (file.size > 5 * 1024 * 1024) return "Photo must be 5 MB or smaller.";
  return null;
}
export function dateLabel(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}
