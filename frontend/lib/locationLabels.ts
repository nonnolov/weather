import type {Location} from "./api";

type AreaKind = "subdistrict" | "district" | "province";

export function administrativeLabel(
  value: string | null | undefined,
  kind: AreaKind,
  language: "th" | "en",
  province?: string | null,
): string {
  const name = value?.trim();
  if (!name) return "";
  const bangkok = /กรุงเทพ|bangkok/i.test(province ?? "");
  if (kind === "province" && /กรุงเทพ|bangkok/i.test(name)) return name;
  const prefixes = {
    subdistrict: /^(?:ตำบล|แขวง|ต\.|Subdistrict\s+)/i,
    district: /^(?:อำเภอ|เขต|อ\.|District\s+)/i,
    province: /^(?:จังหวัด|จ\.|Province\s+)/i,
  };
  const bare = name.replace(prefixes[kind], "").trim();
  if (!bare) return name;
  if (language === "en") {
    const label = kind === "subdistrict" ? "Subdistrict" : kind === "district" ? "District" : "Province";
    return label + " " + bare;
  }
  const label = kind === "subdistrict" ? (bangkok ? "แขวง" : "ตำบล")
    : kind === "district" ? (bangkok ? "เขต" : "อำเภอ") : "จังหวัด";
  return label + bare;
}

export function locationLabels(location: Location, language: "th" | "en") {
  const subdistrict = administrativeLabel(location.subdistrict, "subdistrict", language, location.province);
  const district = administrativeLabel(location.district, "district", language, location.province);
  const province = administrativeLabel(location.province, "province", language, location.province);
  return {subdistrict, district, province, parts: [subdistrict || location.name, district, province].filter(Boolean)};
}
