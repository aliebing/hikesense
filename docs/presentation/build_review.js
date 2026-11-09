// HikeSense review deck (9 slides, English): why, what it offers, technical 1/2 (whole flow) and 2/2 (LangGraph),
// guard, grounding, evaluation, what could be better. Same outline as CineSense's deck
// (CineSenseAi/docs/presentation/build_review.js); the technical slides compare the two apps.
// Run: NODE_PATH=<dir with pptxgenjs, react, react-dom, react-icons, sharp> SKILL_DIR=<pptx skill> node build_review.js [out.pptx]
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require(process.env.SKILL_DIR + "/scripts/apply_theme.js");

const OUT = process.argv[2] || path.join(__dirname, "hikesense-en.pptx");
const SHOTS = path.join(__dirname, "..", "showcase");
const ASSETS = path.join(__dirname, "assets");

// the app's own look: forest green, amber for the model, a light paper ground
const THEME = {
  name: "HikeSense",
  headFontFace: "Georgia",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1C2A20", lt1: "F4F1EA", dk2: "5A6B5E", lt2: "FFFFFF",
    accent1: "2F5D3A", accent2: "D9A23A", accent3: "8DAA5B", accent4: "B4532A",
    accent5: "66786B", accent6: "E4DED0", hlink: "2F5D3A", folHlink: "66786B",
  },
};
const HEX = THEME.colors;

async function icon(name, color) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(fa[name], { color: "#" + color, size: 256 }));
  const png = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  pres.title = "HikeSense – an honest hiking planner";
  pres.author = "Alexander Liebing";
  const C = pres.SchemeColor;
  const W = 13.333;

  // text1 = dark green text, background1 = paper, background2 = white card
  pres.defineSlideMaster({
    title: "Title",
    background: { color: C.text1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 3.15, w: 8.2, h: 1.5,
        fontSize: 40, bold: true, color: C.background2, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "Content",
    background: { color: C.background1 },
    objects: [
      { placeholder: { options: { name: "kicker", type: "body", x: 0.6, y: 0.3, w: 8.0, h: 0.3,
        fontSize: 12, bold: true, color: C.accent1, charSpacing: 3, margin: 0 }, text: "" } },
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.6, w: 12.1, h: 0.75,
        fontSize: 32, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
      { text: { text: "HikeSense · Capstone review", options: { x: 0.6, y: 7.0, w: 4, h: 0.3, fontSize: 10, color: C.text2, margin: 0 } } },
    ],
    slideNumber: { x: 12.3, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.text2, align: "right" },
  });

  const card = (slide, x, y, w, h, name, o = {}) =>
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.1, fill: { color: o.fill || C.background2 },
      line: { color: C.accent6, width: 1 }, objectName: name });
  const iconDot = async (slide, x, y, name, d = 0.6) => {
    slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "Icon circle " + name });
    slide.addImage({ data: await icon(name, "FFFFFF"), x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52, altText: name });
  };
  const text = (slide, t, o) => slide.addText(t, { isTextBox: true, margin: 0, color: C.text1, fontSize: 15, valign: "top", ...o });
  const head = (slide, kicker, title, section) => {
    slide.addText(kicker, { placeholder: "kicker" });
    slide.addText(title, { placeholder: "title" });
  };

  // diagram nodes. kind: "code" (green, deterministic), "llm" (amber, a language model decides),
  // "ext" (outside service, dashed), "stop" (blocked / replaced, rust frame), "ok" (passes, moss frame)
  const STYLE = {
    code: { fill: C.accent1, line: { color: C.accent1, width: 1 }, head: C.background2, sub: C.accent6 },
    llm: { fill: C.accent2, line: { color: C.accent2, width: 1 }, head: C.text1, sub: C.text1 },
    ext: { fill: C.background2, line: { color: C.accent5, width: 1.25, dashType: "dash" }, head: C.text1, sub: C.text2 },
    stop: { fill: C.background2, line: { color: C.accent4, width: 2 }, head: C.accent4, sub: C.text2 },
    ok: { fill: C.background2, line: { color: C.accent3, width: 2 }, head: C.accent1, sub: C.text2 },
  };
  const node = (slide, x, y, w, h, headText, sub, kind = "code", o = {}) => {
    const st = STYLE[kind];
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: st.fill }, line: { ...st.line }, objectName: "Node " + headText });
    const runs = [{ text: headText, options: { bold: true, fontSize: o.headSize || 15, color: st.head, breakLine: !!sub && !o.inline } }];
    if (sub) runs.push({ text: (o.inline ? "  " : "") + sub, options: { fontSize: o.subSize || 12, color: st.sub } });
    const pad = o.pad ?? 0.12;
    text(slide, runs, { x: x + pad, y: y + 0.04, w: w - 2 * pad, h: h - 0.08, valign: o.valign || "middle",
      align: o.align || "left", paraSpaceAfter: 2, objectName: "Node text " + headText });
  };
  let arrowN = 0;
  const arrow = (slide, x1, y1, x2, y2, o = {}) => {
    arrowN += 1;
    slide.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
      flipH: x2 < x1, flipV: y2 < y1, objectName: "Arrow " + arrowN,
      line: { color: o.color || C.accent5, width: o.width || 1.5, dashType: o.dash || "solid",
        ...(o.noHead ? {} : { endArrowType: "triangle" }), ...(o.both ? { beginArrowType: "triangle" } : {}) } });
  };
  const polyline = (slide, pts, o = {}) => pts.slice(1).forEach((p, i) =>
    arrow(slide, pts[i][0], pts[i][1], p[0], p[1], { ...o, noHead: o.noHead || i < pts.length - 2 }));
  const label = (slide, t, x, y, w, h, o = {}) =>
    text(slide, t, { x, y, w, h, fontSize: 12, color: C.text2, italic: true, valign: "middle", objectName: "Label " + t, ...o });
  // a two-column comparison card: what HikeSense does on the left, what CineSense does on the right
  const compare = (slide, x, y, w, h, left, right) => {
    card(slide, x, y, w, h, "Comparison card", { fill: C.accent6 });
    const cw = (w - 0.75) / 2;
    [[left, x + 0.25, C.accent1], [right, x + 0.5 + cw, C.accent4]].forEach(([[h1, body], cx, color]) =>
      text(slide, [{ text: h1, options: { bold: true, color, fontSize: 14, breakLine: true } }, { text: body, options: { fontSize: 12.5 } }],
        { x: cx, y: y + 0.12, w: cw, h: h - 0.24, paraSpaceAfter: 4, objectName: "Compare " + h1 }));
    slide.addShape(pres.shapes.LINE, { x: x + 0.375 + cw, y: y + 0.2, w: 0, h: h - 0.4, line: { color: C.accent5, width: 1 }, objectName: "Compare divider" });
  };
  const legend = (slide, x, y, short = false) => {
    [["llm", short ? "calls the model" : "calls the model (OpenRouter)"], ["code", short ? "code only" : "code only: SQL, rules, calculations"]].forEach(([kind, t], i) => {
      const lx = x + i * (short ? 2.4 : 3.2);
      slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: lx, y: y + 0.06, w: 0.3, h: 0.2, rectRadius: 0.04, fill: { color: STYLE[kind].fill }, line: { type: "none" }, objectName: "Legend swatch " + kind });
      text(slide, t, { x: lx + 0.4, y, w: 2.7, h: 0.32, fontSize: 12, color: C.text2, valign: "middle", objectName: "Legend " + kind });
    });
  };

  // ---------- 1. Title ----------
  pres.addSection({ title: "Opening" });
  let s = pres.addSlide({ masterName: "Title", sectionTitle: "Opening" });
  s.addImage({ path: path.join(ASSETS, "title-photo.jpg"), x: 0, y: 0, w: W, h: 7.5, altText: "Misty Black Forest hills at sunrise" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: W, h: 7.5, fill: { color: C.text1, transparency: 45 }, line: { type: "none" }, objectName: "Photo shade" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.8, y: 0.7, w: 3.3, h: 1.95, rectRadius: 0.1, fill: { color: C.background2 }, line: { type: "none" }, objectName: "Logo card" });
  s.addImage({ path: path.join(ASSETS, "logo.png"), x: 0.95, y: 0.82, w: 3.0, h: 1.66, altText: "HikeSense logo: mountain with a sun arc, Plan. Hike. Stay. Explore." });
  s.addText("An honest hiking planner, operated through an AI chat", { placeholder: "title" });
  text(s, "Black Forest · Lake Constance · Palatinate Forest", { x: 0.8, y: 4.85, w: 8, h: 0.4, fontSize: 18, bold: true, color: C.accent3, objectName: "Regions" });
  text(s, "Every route from the database · every number checked by code", { x: 0.8, y: 5.3, w: 8, h: 0.4, fontSize: 16, italic: true, color: C.background2, objectName: "Promise" });
  text(s, "Capstone review · Alexander Liebing · November 2026", { x: 0.8, y: 6.5, w: 8, h: 0.35, fontSize: 13, color: C.accent6, objectName: "Byline" });
  s.addNotes("My capstone project is HikeSense, a hiking planner for the Black Forest, Lake Constance and the Palatinate Forest that you operate through an AI chat. First why it is needed and what it offers. Then the technical side on two slides: the whole flow, and the LangGraph flow of one message, each compared with CineSense. Then the guard, the grounding check and the evaluation, briefly, and at the end what could be better and where it could go.");

  // ---------- 2. Why ----------
  pres.addSection({ title: "Problem" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Problem" });
  head(s, "01 · WHY", "Three days in the Black Forest, days of preparation");
  text(s, [{ text: "A real trip: ", options: { bold: true } },
    { text: "three rooms in a row, about 15 km a day, a plan B for rain. The hard part was not finding a trail, it was making route, lodging and weather fit together." }],
  { x: 0.6, y: 1.5, w: 12.1, h: 0.65, fontSize: 16, color: C.text2, objectName: "Story" });
  const problems = [
    ["FaBed", "Route, lodging, weather must fit", "multi-day plans with lodging ≤ 1 km from the trail, DIN 33466 times and the forecast"],
    ["FaEyeSlash", "HikeAI dropped wishes silently", "names a wish that cannot be met, with the reason; fallbacks miss exactly one condition"],
    ["FaListUl", "HikeAI gave a list, not a plan", "day stages, arrival times, a rain variant; change it in the chat"],
    ["FaQuestionCircle", "HikeAI's data had no provenance", "every row points to a source and its licence; every import decision has a reason"],
  ];
  for (const [i, [ic, h1, answer]] of problems.entries()) {
    const x = 0.6 + (i % 2) * 6.15, y = 2.4 + Math.floor(i / 2) * 2.2;
    card(s, x, y, 5.95, 1.95, "Problem card " + (i + 1));
    await iconDot(s, x + 0.3, y + 0.32, ic);
    text(s, h1, { x: x + 1.15, y: y + 0.35, w: 4.6, h: 0.5, fontSize: 19, bold: true, objectName: "Problem " + (i + 1) });
    text(s, [{ text: "HikeSense: ", options: { bold: true, color: C.accent1 } }, { text: answer }],
      { x: x + 1.15, y: y + 0.95, w: 4.6, h: 0.85, fontSize: 15, objectName: "Answer " + (i + 1) });
  }
  s.addNotes("The project started with a real trip: three days in the Black Forest, three rooms in a row, about 15 kilometres a day, a plan B for rain. It worked, but it cost several days of research, because route, lodging and weather had to fit together. My Sprint 2 project HikeAI did not solve that, and the review criticised three things: it dropped wishes silently, it only gave a list, and the provenance of the data was not traceable. Each card shows how HikeSense answers that.");

  // ---------- 3. What HikeSense offers ----------
  pres.addSection({ title: "Solution" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Solution" });
  head(s, "02 · WHAT IT OFFERS", "What HikeSense offers");
  s.addImage({ path: path.join(SHOTS, "04-unerfuellbar-ausweichtouren.jpg"), x: 0.6, y: 1.55, w: 4.6, h: 2.59,
    altText: "Unsatisfiable wish: no tour meets all wishes, two fallback tours with a tick or cross per condition" });
  s.addImage({ path: path.join(SHOTS, "05-mehrtagesplan.jpg"), x: 0.6, y: 4.3, w: 4.6, h: 2.59,
    altText: "Three-day plan on the Westweg from Hausach: day stages with kilometres and lodging" });
  {
    const offers = [
      ["FaRoute", "Day hikes that fit", "577 checked tours in 3 regions; every condition ✓ / ✗ on the card"],
      ["FaBalanceScale", "Honest when nothing fits", "the reason in words; fallbacks miss exactly one condition"],
      ["FaBed", "Multi-day plans", "8 long-distance trails: stages, lodging ≤ 1 km, DIN 33466 times, weather, rain variant"],
      ["FaCommentDots", "Change it in the chat", "\"Day 3 shorter\": the other days stay as they were"],
      ["FaBookOpen", "Knowledge with sources", "answers from Wikipedia, Wikivoyage and own texts, with the links"],
      ["FaMobileAlt", "On the way", "remaining km and arrival on the phone; the position never leaves the browser"],
    ];
    for (const [i, [ic, h1, body]] of offers.entries()) {
      const y = 1.55 + i * 0.9;
      await iconDot(s, 5.85, y + 0.1, ic, 0.55);
      text(s, [{ text: h1, options: { bold: true, fontSize: 16, breakLine: true } }, { text: body, options: { fontSize: 13, color: C.text2 } }],
        { x: 6.6, y, w: 6.1, h: 0.8, valign: "middle", paraSpaceAfter: 2, objectName: "Offer " + h1 });
    }
  }
  s.addNotes("This is what the app offers. Day hikes in three regions, 577 tours that passed strict rules, and every card shows a tick or a cross for each condition. When nothing fits, as in the upper screenshot, the code says so with the reason and shows tours that miss exactly one condition. Multi-day plans on eight long-distance trails split the trail into days with lodging at most one kilometre from the trail, walking times after DIN 33466, the weather and a rain variant. You change the plan in the chat, for example 'day 3 shorter'. Knowledge questions are answered from sources with links, and the 'On the way' page shows the remaining kilometres on the phone without sending the position anywhere.");

  const PALETTE = { fill: "#FFFFFF", stroke: "#9AA89D", modelFill: "#FBEFD2", model: "#C68A1C", fg: "#1C2A20", muted: "#5A6B5E", edge: "#7D8B80" };
  const HEAD_COLOR = C.accent1;
  // ---------- technical slides: diagrams in the style of the comparison video (docs/video/compare_slides.html) ----------
  // A spec is drawn as SVG and rasterised with sharp: nodes ("model" = a language model, marked ✦; "ext" = a service or store,
  // dashed), edges as SVG paths ("back" = dashed, "both" = arrow at both ends, "plain" = no arrow), edge labels and end points.
  const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const diagramPng = async (spec) => {
    const P = PALETTE;
    const out = [`<svg xmlns="http://www.w3.org/2000/svg" width="${spec.w}" height="${spec.h}" viewBox="0 0 ${spec.w} ${spec.h}">`,
      `<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${P.edge}"/></marker></defs>`];
    for (const e of spec.edges) {
      const [d, kind = ""] = e;
      const dash = kind.includes("back") || kind.includes("link") ? ' stroke-dasharray="8 7"' : "";
      const head = kind.includes("plain") || kind.includes("link") ? "" : ' marker-end="url(#a)"';
      const tail = kind.includes("both") ? ' marker-start="url(#a)"' : "";
      out.push(`<path d="${d}" fill="none" stroke="${P.edge}" stroke-width="3"${dash}${head}${tail}/>`);
    }
    for (const [x, y, w, h, name, sub, kind = ""] of spec.nodes) {
      const model = kind === "model", ext = kind === "ext";
      out.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="14" fill="${model ? P.modelFill : P.fill}" stroke="${model ? P.model : P.stroke}" stroke-width="${model ? 2.5 : 2}"${ext ? ' stroke-dasharray="7 6"' : ""}/>`);
      const cx = x + w / 2, cy = y + h / 2;
      const label = model ? `${esc(name)} <tspan fill="${P.model}">✦</tspan>` : esc(name);
      out.push(`<text x="${cx}" y="${sub ? cy - 4 : cy + 9}" fill="${P.fg}" font-family="Ubuntu Sans Mono, DejaVu Sans Mono, monospace" font-weight="600" font-size="26" text-anchor="middle">${label}</text>`);
      if (sub) out.push(`<text x="${cx}" y="${cy + 26}" fill="${P.muted}" font-family="Ubuntu Sans, DejaVu Sans, sans-serif" font-size="19" text-anchor="middle">${esc(sub)}</text>`);
    }
    for (const [x, y, t, anchor = "middle"] of spec.labels || [])
      out.push(`<text x="${x}" y="${y}" fill="${P.muted}" font-family="Ubuntu Sans Mono, DejaVu Sans Mono, monospace" font-size="21" text-anchor="${anchor}">${esc(t)}</text>`);
    for (const [x, y] of spec.terms || []) out.push(`<circle cx="${x}" cy="${y}" r="12" fill="${P.edge}"/>`);
    out.push("</svg>");
    const png = await sharp(Buffer.from(out.join("")), { density: 160 }).png().toBuffer();
    return "image/png;base64," + png.toString("base64");
  };
  // three short columns of technical description under a diagram
  const describe = (slide, y, cols) => {
    const cw = (12.1 - 2 * 0.3) / 3;
    cols.forEach(([head, body], i) => {
      const x = 0.6 + i * (cw + 0.3);
      card(slide, x, y, cw, 6.88 - y, "Description " + head);
      text(slide, [{ text: head, options: { bold: true, color: HEAD_COLOR, fontSize: 14, breakLine: true } }, { text: body, options: { fontSize: 12 } }],
        { x: x + 0.2, y: y + 0.1, w: cw - 0.4, h: 6.88 - y - 0.24, paraSpaceAfter: 4, objectName: "Description text " + head });
    });
  };

  // the system flow: the main row, the model above, stores and services below, the stream back to the client
  const SYS = { w: 1800, h: 560, y: 150, hh: 90 };
  const sysFlow = (main, top, bottom, terms, back) => {
    const cy = SYS.y + SYS.hh / 2, nodes = [], edges = [["M36," + cy + " H58"]];
    main.forEach(([x, w, name, sub, kind], i) => {
      nodes.push([x, SYS.y, w, SYS.hh, name, sub, kind]);
      if (i < main.length - 1) edges.push([`M${x + w},${cy} H${main[i + 1][0] - 2}`]);
    });
    top.forEach(([x, w, name, links]) => {
      nodes.push([x, 20, w, 64, name, "", "ext"]);
      links.forEach((lx) => edges.push([`M${lx},${SYS.y} V86`, "link"]));
    });
    bottom.forEach((n) => nodes.push([n[0], 380, n[1], 80, n[2], n[3], "ext"]));
    const labels = [];
    terms.forEach(([x, t, anchor]) => { edges.push([`M${x},${SYS.y + SYS.hh} V298`]); labels.push([x + (anchor === "end" ? 15 : anchor === "start" ? -15 : 0), 352, t, anchor]); });
    const last = main[main.length - 1], first = main[0];
    edges.push([`M${last[0] + last[1] / 2},${SYS.y + SYS.hh} V490 Q${last[0] + last[1] / 2},505 ${last[0] + last[1] / 2 - 15},505 H${first[0] + first[1] / 2 + 15} Q${first[0] + first[1] / 2},505 ${first[0] + first[1] / 2},490 V${SYS.y + SYS.hh + 4}`, "back"]);
    labels.push([900, 545, back]);
    return { w: SYS.w, h: SYS.h, nodes, edges, labels, terms: [[24, cy], ...terms.map(([x]) => [x, 312])] };
  };

  // ---------- 4. Technical 1: system flow ----------
  pres.addSection({ title: "Technical" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Technical" });
  head(s, "03 · TECHNICAL 1/2", "System flow: from a wish to the answer");
  {
    const spec = sysFlow(
      [[60, 190, "client", "Next.js PWA"], [300, 190, "api", "FastAPI · JWT · SSE"], [540, 170, "guard", "9 patterns"],
        [760, 200, "understand", "structured output", "model"], [1010, 210, "search · plan", "PostGIS · ✓ / ✗"],
        [1270, 190, "answer", "words the reply", "model"], [1510, 220, "ground", "numbers checked"]],
      [[60, 430, "Supabase Auth · JWT", [155, 395]], [760, 700, "OpenRouter · gpt-4o-mini", [860, 1365]]],
      [[760, 200, "import", "offline: OSM, DEM"], [1010, 210, "Postgres", "PostGIS · 577 tours"], [1270, 190, "Open-Meteo", "forecast, live"]],
      [[625, "injection → fixed reply", "end"], [860, "unclear → asks back", "start"]],
      "reply, tour cards and plans stream back (SSE)");
    spec.edges.push(["M960,420 H1008"], ["M1115,244 V376", "both"], ["M1200,240 C1200,320 1365,300 1365,376"]);
    s.addImage({ data: await diagramPng(spec), x: 0.6, y: 1.45, w: 12.1, h: 12.1 * spec.h / spec.w, altText: "System flow of HikeSense: client, API, guard, understand (LLM), search and plan, answer (LLM), ground; Supabase Auth and OpenRouter above, import, Postgres with PostGIS and Open-Meteo below; the reply streams back to the client" });
    describe(s, 5.28, [
      ["Request", "The Next.js PWA posts the message with a Supabase JWT; FastAPI checks token and quota and streams JSON events (SSE). 9 injection patterns run before any model call."],
      ["Model ✦", "gpt-4o-mini via OpenRouter, twice: understand fills a Pydantic schema (code keeps only what was written), answer words the reply."],
      ["Code", "PostGIS search with ✓ / ✗ per condition, the day planner and the Open-Meteo forecast. Grounding checks every number and tour name against the tool results."],
    ]);
  }
  s.addNotes("The whole system on one diagram; the sparkle marks where a language model works. The Next.js PWA, signed in with Supabase, posts the message to FastAPI, which checks the token and the quota and streams JSON events back. The guard checks nine injection patterns before any model call. Understand makes one structured-output call through OpenRouter; if the place is unclear, the app asks back. Then plain code searches PostGIS and checks every condition, or plans the days with the forecast from Open-Meteo. The data in Postgres was imported offline from OpenStreetMap and other open sources. Answer words the reply, and ground checks every number and tour name. Reply, cards and plans stream back to the client.");

  // ---------- 5. Technical 2: the LangGraph graph ----------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Technical" });
  head(s, "04 · TECHNICAL 2/2 · LANGGRAPH", "Workflow-first: the code drives");
  {
    const br = ["clarify", "reply", "search", "multiday", "react", "groups", "events"];
    const by = (i) => 40 + i * 82, bc = (i) => by(i) + 31;
    const nodes = [[70, 285, 170, 70, "guard"], [320, 285, 240, 70, "understand", "", "model"],
      ...br.map((n, i) => [700, by(i), 210, 62, n, "", n === "react" ? "model" : ""]),
      [1010, 285, 200, 70, "answer", "", "model"], [1270, 285, 170, 70, "ground"], [1480, 285, 130, 70, "log"]];
    const edges = [["M28,320 H68"], ["M240,320 H318"],
      ...br.map((_, i) => [bc(i) === 317 ? "M560,320 H698" : `M560,320 C630,320 630,${bc(i)} 698,${bc(i)}`]),
      ["M155,285 C155,150 600,153 698,153", "back"],
      ...[2, 3, 4, 5, 6].map((i) => [bc(i) === 317 ? "M910,317 H1008" : `M910,${bc(i)} C960,${bc(i)} 960,320 1008,320`]),
      ["M1210,320 H1268"], ["M1440,320 H1478"], ["M1610,320 H1630"],
      ["M910,71 C1545,71 1545,71 1545,283", "back"], ["M910,153 C1500,153 1530,160 1540,283", "back"]];
    const spec = { w: 1660, h: 640, nodes, edges, labels: [[650, 22, "state[\"route\"]"], [430, 250, "injection"]], terms: [[14, 320], [1648, 320]] };
    s.addImage({ data: await diagramPng(spec), x: 1.45, y: 1.4, w: 10.4, h: 10.4 * spec.h / spec.w, altText: "HikeSense LangGraph graph: guard, understand (LLM), then exactly one of clarify, reply, search, multiday, react (LLM), groups, events; then answer (LLM), ground, log; clarify and reply go straight to log" });
    describe(s, 5.55, [
      ["✦ One model call", "understand fills a Pydantic schema; resolve() in code keeps only what was written and sets state[\"route\"]."],
      ["Code routes", "A conditional edge runs exactly one of 7 branches, with no loop back. Only react ✦ calls tools (4 tools, at most 8 calls)."],
      ["Checked output", "answer ✦ words the reply from the data, ground checks numbers and tour names, log writes one JSON line. State: a MemorySaver per user and thread."],
    ]);
  }
  s.addNotes("This is build_graph in graph.py. HikeSense is workflow-first: the code drives. guard checks the injection patterns; a match goes straight to reply. understand makes exactly one structured-output call, and plain code turns it into a request and writes the route into the state. The conditional edge then runs exactly one of seven branches. search, multiday and groups are pure code; react is the only branch where the model calls tools, for knowledge questions; events reads race pages. clarify and reply go straight to log; the others go through answer, where the model words the reply, and ground, which checks numbers and tour names. There is no loop back: the model never decides how often to go round, unlike CineSense's agent-first graph.");

  // ---------- 6. Guard ----------
  pres.addSection({ title: "Safety and quality" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Safety and quality" });
  head(s, "05 · GUARD", "Guard: five layers, most of them without the model");
  {
    const layers = [
      ["1  API request", "Supabase JWT or a guest; blocked → 403; body > 64 KB → 413; control and zero-width characters out, ≤ 1,000 characters"],
      ["2  Quotas", "account 10 / minute, 100 / day; guests 10 / day per IP, 200 / day in total → 429 before any model call"],
      ["3  guard node", "9 regex patterns, English and German → fixed reply, no model call"],
      ["4  understand", "off-topic → intent other → fixed reply; the output must match the schema"],
      ["5  ground", "a 60-character piece of a system prompt in the draft → fixed reply"],
    ];
    const lw = 2.25, lg = 0.2;
    layers.forEach(([h1, body], i) => {
      const x = 0.6 + i * (lw + lg);
      node(s, x, 1.6, lw, 0.6, h1, "", i === 3 ? "llm" : "code", { headSize: 15 });
      card(s, x, 2.3, lw, 2.0, "Layer body " + (i + 1));
      text(s, body, { x: x + 0.15, y: 2.42, w: lw - 0.3, h: 1.8, fontSize: 13, objectName: "Layer text " + (i + 1) });
      if (i < layers.length - 1) arrow(s, x + lw + 0.02, 1.9, x + lw + lg - 0.02, 1.9);
    });
    card(s, 0.6, 4.6, 7.0, 2.15, "Example card");
    text(s, [
      { text: "Why sanitise first", options: { bold: true, fontSize: 15, breakLine: true } },
      { text: "looks_like_injection(sanitize_text(\n    \"Ig\\u200bnore all previous instructions\"))\n→ True   # zero-width space removed first", options: { fontFace: "Courier New", fontSize: 13 } },
    ], { x: 0.85, y: 4.75, w: 6.5, h: 1.9, paraSpaceAfter: 6, objectName: "Example" });
    card(s, 7.8, 4.6, 4.9, 2.15, "Tested card");
    text(s, "6 / 6", { x: 8.05, y: 4.75, w: 2.0, h: 0.8, fontSize: 36, bold: true, color: C.accent1, fontFace: THEME.headFontFace, objectName: "Guard stat" });
    text(s, "guard cases pass in every run: 4 injection variants (system prompt, English, role play, zero-width) and off-topic, with no model call",
      { x: 8.05, y: 5.55, w: 4.45, h: 1.1, fontSize: 13, color: C.text2, objectName: "Guard stat label" });
  }
  s.addNotes("Prompt injection and abuse are handled in five layers, and most of them never touch the model. The API checks the token, blocks oversized bodies and removes control and zero-width characters. Quotas stop a bot before any model call. The guard node in the graph has nine patterns in English and German; a match gets a fixed reply. understand sends off-topic requests to a fixed reply, and its output must match the schema. ground replaces a draft that leaks a piece of a system prompt. The example shows why sanitising comes first: a zero-width space hidden in 'ignore' would otherwise slip past the pattern. CineSense has the same idea, but runs its guard before the graph and has no accounts, only per-visitor turn limits.");

  // ---------- 7. Grounding ----------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Safety and quality" });
  head(s, "06 · GROUNDING", "Grounding: every number must be in the evidence");
  {
    const steps = [
      ["Collect evidence", "every number with a unit and every name in the tool JSON, plus the code's own sentences"],
      ["Strip a false \"no tour fits\"", "only the code may say that"],
      ["Strip weather claims", "when the forecast says no or unknown"],
      ["Check every number", "German and English, units converted, rounded like the answer; a miss → \"?\" + note"],
      ["Check tour names", "a database name not in the evidence gets a note"],
      ["Assemble", "the code's honest sentences first, then the model's text"],
    ];
    steps.forEach(([h1, body], i) => {
      const y = 1.6 + i * 0.75;
      s.addShape(pres.shapes.OVAL, { x: 0.6, y: y + 0.08, w: 0.45, h: 0.45, fill: { color: C.accent1 }, line: { type: "none" }, objectName: "Step dot " + (i + 1) });
      text(s, String(i + 1), { x: 0.6, y: y + 0.08, w: 0.45, h: 0.45, fontSize: 15, bold: true, color: C.background2, align: "center", valign: "middle", objectName: "Step number " + (i + 1) });
      text(s, [{ text: h1, options: { bold: true, fontSize: 15, breakLine: true } }, { text: body, options: { fontSize: 12.5, color: C.text2 } }],
        { x: 1.25, y, w: 5.3, h: 0.7, valign: "middle", paraSpaceAfter: 1, objectName: "Step " + (i + 1) });
    });
    card(s, 6.85, 1.6, 5.85, 3.5, "Example card");
    text(s, [
      { text: "Real output of grounding_check (made-up draft)", options: { bold: true, fontSize: 14, breakLine: true } },
      { text: "evidence: 12,4 km · 540 Hm · Säbelthomaweg", options: { fontSize: 12.5, color: C.text2, breakLine: true } },
      { text: "draft", options: { bold: true, fontSize: 13, color: C.accent1, breakLine: true } },
      { text: "The Säbelthomaweg is 12.4 km long, so roughly 12 km, with 540 m of ascent. The café is 2 km from the start. The Jägersteig is shorter.", options: { fontSize: 13, breakLine: true } },
      { text: "after ground", options: { bold: true, fontSize: 13, color: C.accent1, breakLine: true } },
      { text: "… with 540 m of ascent. The café is ? km from the start. The Jägersteig is shorter.", options: { fontSize: 13, breakLine: true } },
      { text: "✓ 12.4 km · ✓ 12 km (rounded) · ✓ 540 m = 540 Hm · ✗ 2 km → ? · ✗ Jägersteig → note", options: { fontSize: 12.5, color: C.accent4 } },
    ], { x: 7.1, y: 1.75, w: 5.35, h: 3.25, paraSpaceAfter: 6, objectName: "Grounding example" });
    text(s, [{ text: "0 unsupported numbers ", options: { bold: true, color: C.accent1 } },
      { text: "of 670 / 661 / 690 in three eval runs. Limit: numbers, tour names and the \"no tour fits\" sentence are checked, not every statement." }],
    { x: 6.85, y: 5.35, w: 5.85, h: 0.8, fontSize: 14, objectName: "Grounding result" });
  }
  s.addNotes("Grounding is plain code in agent/grounding.py. While the branch runs, every number with a unit and every name in the tool results is collected as evidence, with the sentences the code writes itself. Only the code may say that no tour fits, and weather claims go when the forecast does not back them. The core: every number in the draft is found with regular expressions for German and English, converted, and compared at the answer's precision; a miss becomes a question mark plus a note. Tour names not in the evidence get a note. Then the code's honest sentences go first. On the right a real output of the function. In three runs, not one number was unsupported. CineSense checks film titles instead and replaces the whole reply with a template, because there the risk is an invented film, not an invented distance.");

  // ---------- 8. Evaluation ----------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Safety and quality" });
  head(s, "07 · EVALUATION", "Evaluation: 64 cases, checked by code, three runs");
  const evals = [
    ["64 / 64", "cases passed in each of 3 runs"],
    ["0 of 110", "invented tours (ids not in the database)"],
    ["0 of ~670", "unsupported numbers per run"],
    ["$0.033", "for a full run of 64 cases"],
  ];
  for (const [i, [big, small]] of evals.entries()) {
    const x = 0.6 + (i % 2) * 3.2, y = 1.6 + Math.floor(i / 2) * 2.0;
    card(s, x, y, 3.0, 1.8, "Eval stat " + (i + 1));
    text(s, big, { x: x + 0.25, y: y + 0.2, w: 2.6, h: 0.75, fontSize: 32, bold: true, color: C.accent1, fontFace: THEME.headFontFace, objectName: "Eval number " + (i + 1) });
    text(s, small, { x: x + 0.25, y: y + 1.0, w: 2.6, h: 0.7, fontSize: 14, color: C.text2, objectName: "Eval label " + (i + 1) });
  }
  text(s, [{ text: "How: ", options: { bold: true, color: C.accent1 } },
    { text: "make eval runs the real graph, model, database and index; the weather is frozen and \"today\" fixed. Code checks every answer, no LLM judge. 10 / 10 unsatisfiable wishes named, Recall@5 = 1.00." }],
  { x: 0.6, y: 5.65, w: 6.2, h: 1.2, fontSize: 13, objectName: "Eval method" });
  s.addChart(pres.charts.BAR, [{ name: "Cases", labels: ["satisfiable", "multi-day", "unsatisfiable", "knowledge", "input guard", "plan change", "groups + races"],
    values: [18, 12, 10, 10, 6, 5, 3] }], {
    x: 7.2, y: 1.5, w: 5.5, h: 4.2, barDir: "bar", catAxisOrientation: "maxMin",
    showTitle: true, title: "Test set: 64 cases by group", titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
    chartColors: [HEX.accent1], showValue: true, dataLabelPosition: "outEnd", dataLabelColor: HEX.dk1,
    dataLabelFontSize: 13, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0",
    catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt",
    valAxisHidden: true, valAxisMinVal: 0, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: false, barGapWidthPct: 50,
  });
  text(s, "gpt-4o-mini, 2026-11-03. gpt-4.1-mini costs twice as much and passed 60–61: the quality comes from the code checks, not the model.",
    { x: 7.2, y: 5.85, w: 5.5, h: 0.75, fontSize: 13, color: C.text2, objectName: "Chart caption" });
  s.addNotes("The evaluation runs 64 chat requests against the real agent: the same graph, the real model, database and knowledge index. The weather is frozen and 'today' is fixed, so runs repeat. The answers are checked by code, not by hand and not by a second model. With gpt-4o-mini all 64 cases passed in each of three runs: no invented tour, no unsupported number, all ten unsatisfiable wishes named, the expected source in the top five for every knowledge question, at about three cents per run. A stronger model, gpt-4.1-mini, was not better: it costs twice as much and passed 60 or 61. CineSense differs here too: it adds an LLM judge and two baselines, because ranking films by mood has no single right answer.");

  // ---------- 9. Improve and go further ----------
  pres.addSection({ title: "Outlook" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Outlook" });
  head(s, "08 · OUTLOOK", "What could be better, and where it could go");
  const better = [
    { text: "Room availability is unknown: the app links the lodging, it does not book", options: { bullet: true, breakLine: true } },
    { text: "OSM can be outdated or incomplete; well-mapped areas are favoured", options: { bullet: true, breakLine: true } },
    { text: "Grounding checks numbers and tour names, not every statement", options: { bullet: true, breakLine: true } },
    { text: "The test set is small and self-written: 3 runs, no confidence interval", options: { bullet: true, breakLine: true } },
    { text: "\"near Überlingen\" is read as a place name; the code asks back", options: { bullet: true } },
  ];
  const next = [
    { text: "More regions: a Region entry, a Geofabrik extract and a review", options: { bullet: true, breakLine: true } },
    { text: "Check statements, not only numbers, against the evidence", options: { bullet: true, breakLine: true } },
    { text: "Lodging availability through a booking partner's API", options: { bullet: true, breakLine: true } },
    { text: "A larger test set from anonymised real chats, with repeated runs", options: { bullet: true, breakLine: true } },
    { text: "A persistent checkpointer, so a chat survives a restart", options: { bullet: true } },
  ];
  card(s, 0.6, 1.6, 5.95, 4.6, "Better card");
  card(s, 6.75, 1.6, 5.95, 4.6, "Next card");
  await iconDot(s, 0.9, 1.85, "FaWrench");
  await iconDot(s, 7.05, 1.85, "FaRoute");
  text(s, "Could be better", { x: 1.7, y: 1.92, w: 4.5, h: 0.45, fontSize: 20, bold: true, objectName: "Better head" });
  text(s, "Next steps", { x: 7.85, y: 1.92, w: 4.5, h: 0.45, fontSize: 20, bold: true, objectName: "Next head" });
  text(s, better, { x: 0.9, y: 2.7, w: 5.4, h: 3.35, fontSize: 15, paraSpaceAfter: 8, objectName: "Better" });
  text(s, next, { x: 7.05, y: 2.7, w: 5.4, h: 3.35, fontSize: 15, paraSpaceAfter: 8, objectName: "Next steps" });
  text(s, [{ text: "Try it: ", options: { color: C.text2 } }, { text: "\"3 days Westweg from Hausach, ~15 km per day\" → \"Day 3 shorter\"", options: { bold: true, color: C.accent1 } },
    { text: "   ·   Thank you!", options: { color: C.text2 } }],
  { x: 0.6, y: 6.35, w: 12.1, h: 0.45, fontSize: 17, objectName: "Try it" });
  s.addNotes("What could be better: the app does not know whether a room is free; it links the lodging but does not book. OpenStreetMap can be outdated, and well-mapped areas are favoured. The grounding check covers numbers, tour names and the 'no tour fits' sentence, not every statement. The test set is small and self-written. And one known slip: 'near Überlingen' is read as a place name, so the code asks back instead of guessing. Where it could go: more regions, which is a configuration plus an import and a review; checking whole statements against the evidence; lodging availability through a booking partner; a larger test set from anonymised real chats; and a persistent checkpointer. Thank you; questions are welcome.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
