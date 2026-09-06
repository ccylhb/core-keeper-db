import type { APIRoute } from "astro";
import accessories_data from "../data/accessories.json";
import armor_data from "../data/armor.json";
import enemies_data from "../data/enemies.json";
import food_data from "../data/food.json";
import weapons_data from "../data/weapons.json";

const tools: Array<{ t: string; u: string; k: string; i?: string }> = [{"t": "Item Rankings", "u": "/rankings/", "k": "Tool"}, {"t": "Crafting Calculator", "u": "/calculator/", "k": "Tool"}];

const items: Array<{ t: string; u: string; k: string; i?: string }> = [
  ...accessories_data.map((x: any) => { const n = x.name || x.title; if (!n || !x.slug) return null; if (n.includes("/") || String(x.slug).includes("/")) return null; return { t: n, u: `/accessories/${x.slug}/`, k: "Accessories", i: x.icon || "" }; }).filter(Boolean) as Array<{t:string;u:string;k:string;i:string}>,
  ...armor_data.map((x: any) => { const n = x.name || x.title; if (!n || !x.slug) return null; if (n.includes("/") || String(x.slug).includes("/")) return null; return { t: n, u: `/armor/${x.slug}/`, k: "Armor", i: x.icon || "" }; }).filter(Boolean) as Array<{t:string;u:string;k:string;i:string}>,
  ...enemies_data.map((x: any) => { const n = x.name || x.title; if (!n || !x.slug) return null; if (n.includes("/") || String(x.slug).includes("/")) return null; return { t: n, u: `/enemies/${x.slug}/`, k: "Creatures", i: x.icon || "" }; }).filter(Boolean) as Array<{t:string;u:string;k:string;i:string}>,
  ...food_data.map((x: any) => { const n = x.name || x.title; if (!n || !x.slug) return null; if (n.includes("/") || String(x.slug).includes("/")) return null; return { t: n, u: `/food/${x.slug}/`, k: "Consumables", i: x.icon || "" }; }).filter(Boolean) as Array<{t:string;u:string;k:string;i:string}>,
  ...weapons_data.map((x: any) => { const n = x.name || x.title; if (!n || !x.slug) return null; if (n.includes("/") || String(x.slug).includes("/")) return null; return { t: n, u: `/weapons/${x.slug}/`, k: "Weapons", i: x.icon || "" }; }).filter(Boolean) as Array<{t:string;u:string;k:string;i:string}>,
];

export const GET: APIRoute = () =>
  new Response(JSON.stringify({ tools, items }), {
    headers: { "Content-Type": "application/json" },
  });
