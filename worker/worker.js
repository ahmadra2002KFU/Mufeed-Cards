/**
 * Mufeed Cards intake worker.
 *
 * Receives the add-your-card form from cards.mufeedai.com and commits
 * people/<slug>/card.json (+ optional photo.jpg) to the Mufeed-Cards repo
 * through the GitHub Contents API. GitHub Actions then builds and deploys
 * the card automatically.
 *
 * Deploy: Cloudflare dashboard -> Workers -> create "mufeed-cards-intake",
 * paste this file, then add a secret named GITHUB_TOKEN (fine-grained PAT,
 * ONLY the Mufeed-Cards repo, ONLY "Contents: read & write").
 */

const REPO = "ahmadra2002KFU/Mufeed-Cards";
const ALLOWED_ORIGINS = [
  "https://cards.mufeedai.com",
  "http://localhost:5603",
];
const MAX_PHOTO_BYTES = 1_500_000; // ~1.5MB after client-side resize

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0],
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function json(status, body, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
  });
}

async function github(env, method, path, body) {
  return fetch(`https://api.github.com/repos/${REPO}/${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "mufeed-cards-intake",
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}

const REQUIRED = ["name_en", "full_name_en", "phone", "vcard"];

function validate(slug, card) {
  if (!/^[a-z0-9][a-z0-9-]{1,29}$/.test(slug || "")) return "invalid slug";
  if (!card || typeof card !== "object") return "missing card";
  for (const k of REQUIRED) if (!card[k]) return `missing field: ${k}`;
  if (!/^\+\d{8,15}$/.test(card.phone)) return "invalid phone";
  for (const k of ["email"]) {
    if (card[k] && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(card[k])) return "invalid email";
  }
  for (const k of ["website", "linkedin"]) {
    if (card[k] && !/^https:\/\//.test(card[k])) return `invalid ${k} (must be https)`;
  }
  for (const [k, v] of Object.entries(card)) {
    if (typeof v === "string" && v.length > 300) return `field too long: ${k}`;
  }
  return null;
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }
    if (request.method !== "POST") {
      return json(405, { error: "POST only" }, origin);
    }

    let payload;
    try {
      payload = await request.json();
    } catch {
      return json(400, { error: "invalid JSON" }, origin);
    }

    const { slug, card, photo_base64 } = payload;
    const err = validate(slug, card);
    if (err) return json(400, { error: err }, origin);
    if (photo_base64 && photo_base64.length * 0.75 > MAX_PHOTO_BYTES) {
      return json(400, { error: "photo too large" }, origin);
    }

    // refuse to overwrite an existing card — updates go through the admin
    const existing = await github(env, "GET", `contents/people/${slug}/card.json`);
    if (existing.status === 200) {
      return json(409, { error: "slug already taken" }, origin);
    }

    const cardText = JSON.stringify(card, null, 2) + "\n";
    const put = await github(env, "PUT", `contents/people/${slug}/card.json`, {
      message: `Add ${card.full_name_en} via cards.mufeedai.com`,
      content: btoa(unescape(encodeURIComponent(cardText))),
    });
    if (!put.ok) {
      return json(502, { error: `GitHub rejected the card (${put.status})` }, origin);
    }

    if (photo_base64) {
      const photo = await github(env, "PUT", `contents/people/${slug}/photo.jpg`, {
        message: `Add ${card.full_name_en}'s photo`,
        content: photo_base64,
      });
      if (!photo.ok) {
        return json(200, {
          ok: true,
          url: `https://cards.mufeedai.com/${slug}/`,
          warning: "card saved but the photo failed — send it to the admin",
        }, origin);
      }
    }

    return json(200, { ok: true, url: `https://cards.mufeedai.com/${slug}/` }, origin);
  },
};
