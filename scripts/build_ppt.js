"use strict";

const fs = require("fs");
const path = require("path");
const PptxGenJS = require("pptxgenjs");
const { warnIfSlideHasOverlaps, warnIfSlideElementsOutOfBounds } = require("./helpers/layout");
let SHAPE_TYPES = null;

function shape(name) {
  return (SHAPE_TYPES && SHAPE_TYPES[name]) || name;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const item = argv[i];
    if (item.startsWith("--")) {
      args[item.slice(2)] = argv[i + 1];
      i += 1;
    }
  }
  return args;
}

function hex(value, fallback) {
  const cleaned = String(value || fallback || "7A0019").replace("#", "").trim();
  return cleaned.length === 6 ? cleaned : fallback;
}

function themeFonts(theme) {
  return {
    title: theme.fonts.title_zh || theme.fonts.body_zh || "Microsoft YaHei",
    body: theme.fonts.body_zh || theme.fonts.title_zh || "Microsoft YaHei",
    mono: theme.fonts.mono || "Courier New",
    latinTitle: theme.fonts.title_en || "Arial",
    latinBody: theme.fonts.body_en || "Arial",
  };
}

function addText(slide, text, opts = {}) {
  if (!text) return;
  slide.addText(text, {
    margin: 0,
    valign: "top",
    color: opts.color || "1B1E23",
    fontFace: opts.fontFace || "Microsoft YaHei",
    fontSize: opts.fontSize || 16,
    breakLine: false,
    ...opts,
  });
}

function bulletRuns(items) {
  return (items || []).filter(Boolean).map((item) => ({ text: item, options: { bullet: { indent: 16 } } }));
}

function addHeader(slide, spec, theme, assets) {
  const palette = theme.palette;
  const fonts = themeFonts(theme);
  slide.background = { color: hex(palette.surface, "F6F2ED") };
  slide.addShape(shape("rect"), {
    x: 0,
    y: 0,
    w: 13.333,
    h: 0.16,
    line: { color: hex(palette.primary, "7A0019"), transparency: 100 },
    fill: { color: hex(palette.primary, "7A0019"), transparency: 0 },
  });
  slide.addShape(shape("rect"), {
    x: 0,
    y: 0.16,
    w: 13.333,
    h: 0.28,
    line: { color: hex(palette.accent, "B58A2A"), transparency: 100 },
    fill: { color: hex(palette.accent, "B58A2A"), transparency: 0 },
  });
  if (assets.logo_path && fs.existsSync(assets.logo_path)) {
    slide.addImage({ path: assets.logo_path, x: 11.7, y: 0.42, w: 0.95, h: 0.7 });
  }
  addText(slide, spec.title, {
    x: 0.75,
    y: 0.62,
    w: 8.6,
    h: 0.5,
    fontFace: fonts.title,
    fontSize: spec.slide_type === "cover" ? 24 : 22,
    bold: true,
    color: hex(palette.primary, "7A0019"),
  });
  if (spec.slide_type !== "cover") {
    addText(slide, spec.key_message || "", {
      x: 0.78,
      y: 1.08,
      w: 8.2,
      h: 0.35,
      fontFace: fonts.body,
      fontSize: 11.5,
      color: hex(palette.muted, "66707A"),
    });
  }
}

function addFooter(slide, deckTitle, theme, index, total) {
  const fonts = themeFonts(theme);
  slide.addShape(shape("line"), {
    x: 0.72,
    y: 7.02,
    w: 11.9,
    h: 0,
    line: { color: hex(theme.palette.line, "D7C9B8"), width: 1 },
  });
  addText(slide, `${deckTitle}  ${index}/${total}`, {
    x: 0.78,
    y: 7.07,
    w: 4.6,
    h: 0.2,
    fontFace: fonts.body,
    fontSize: 8.5,
    color: hex(theme.palette.muted, "66707A"),
  });
}

function maybeAddSupportImage(slide, slideAsset, x, y, w, h) {
  if (slideAsset && slideAsset.illustration_path && fs.existsSync(slideAsset.illustration_path)) {
    slide.addImage({ path: slideAsset.illustration_path, x, y, w, h });
    return true;
  }
  return false;
}

function drawCover(slide, spec, theme, slideAsset) {
  const fonts = themeFonts(theme);
  addHeader(slide, spec, theme, slideAsset);
  slide.addShape(shape("roundRect"), {
    x: 0.8,
    y: 1.55,
    w: 7.3,
    h: 3.9,
    rectRadius: 0.08,
    line: { color: hex(theme.palette.line, "D7C9B8"), transparency: 100 },
    fill: { color: "FFFFFF", transparency: 8 },
  });
  addText(slide, spec.key_message, {
    x: 1.05,
    y: 2.0,
    w: 6.4,
    h: 1.0,
    fontFace: fonts.title,
    fontSize: 28,
    bold: true,
    color: hex(theme.palette.primary, "7A0019"),
  });
  slide.addText(bulletRuns(spec.body || []), {
    x: 1.05,
    y: 3.3,
    w: 5.9,
    h: 1.3,
    fontFace: fonts.body,
    fontSize: 14,
    color: hex(theme.palette.text, "1B1E23"),
    paraSpaceAfterPt: 10,
    margin: 0,
  });
  if (!maybeAddSupportImage(slide, slideAsset, 8.65, 1.55, 3.6, 4.35)) {
    slide.addShape(shape("hexagon"), {
      x: 9.15,
      y: 2.05,
      w: 2.6,
      h: 2.2,
      line: { color: hex(theme.palette.accent, "B58A2A"), width: 2 },
      fill: { color: hex(theme.palette.accent, "B58A2A"), transparency: 88 },
    });
    addText(slide, "THU\nTECH", {
      x: 9.6,
      y: 2.63,
      w: 1.7,
      h: 0.7,
      align: "center",
      fontFace: fonts.latinTitle,
      fontSize: 18,
      bold: true,
      color: hex(theme.palette.primary, "7A0019"),
    });
  }
}

function drawAgenda(slide, spec, theme, slideAsset) {
  addHeader(slide, spec, theme, slideAsset);
  spec.body.slice(0, 6).forEach((item, index) => {
    slide.addShape(shape("roundRect"), {
      x: 0.95,
      y: 1.7 + index * 0.8,
      w: 10.9,
      h: 0.58,
      rectRadius: 0.05,
      line: { color: hex(theme.palette.line, "D7C9B8"), transparency: 100 },
      fill: { color: index % 2 === 0 ? "FFFFFF" : hex(theme.palette.soft_fill, "F3EEE7"), transparency: 0 },
    });
    addText(slide, String(index + 1).padStart(2, "0"), {
      x: 1.18,
      y: 1.9 + index * 0.8,
      w: 0.5,
      h: 0.2,
      fontSize: 10.5,
      bold: true,
      color: hex(theme.palette.accent, "B58A2A"),
    });
    addText(slide, item, {
      x: 1.9,
      y: 1.84 + index * 0.8,
      w: 8.4,
      h: 0.24,
      fontSize: 15,
    });
  });
}

function drawBulletCards(slide, spec, theme, slideAsset) {
  addHeader(slide, spec, theme, slideAsset);
  const items = spec.body.slice(0, 4);
  items.forEach((item, index) => {
    const col = index % 2;
    const row = Math.floor(index / 2);
    const x = 0.95 + col * 5.6;
    const y = 1.8 + row * 2.0;
    slide.addShape(shape("roundRect"), {
      x,
      y,
      w: 4.95,
      h: 1.52,
      rectRadius: 0.05,
      line: { color: hex(theme.palette.line, "D7C9B8"), transparency: 100 },
      fill: { color: "FFFFFF", transparency: 0 },
    });
    slide.addShape(shape("rect"), {
      x: x + 0.22,
      y: y + 0.25,
      w: 0.1,
      h: 0.92,
      line: { color: hex(theme.palette.accent, "B58A2A"), transparency: 100 },
      fill: { color: hex(theme.palette.accent, "B58A2A"), transparency: 0 },
    });
    addText(slide, item, {
      x: x + 0.5,
      y: y + 0.26,
      w: 4.0,
      h: 0.9,
      fontSize: 15,
      bold: true,
    });
  });
}

function drawProcess(slide, spec, theme, slideAsset, visual) {
  addHeader(slide, spec, theme, slideAsset);
  const steps = (visual.steps || []).slice(0, 5);
  const labels = steps.length ? steps.map((item) => item.name || item.code || item) : spec.body.slice(0, 5);
  labels.forEach((item, index) => {
    const x = 0.95 + index * 2.38;
    slide.addShape(shape("roundRect"), {
      x,
      y: 2.45,
      w: 1.85,
      h: 0.92,
      rectRadius: 0.05,
      line: { color: hex(theme.palette.line, "D7C9B8"), transparency: 100 },
      fill: { color: index % 2 === 0 ? "FFFFFF" : hex(theme.palette.surface_alt, "EDE3D6"), transparency: 0 },
    });
    addText(slide, item, {
      x: x + 0.14,
      y: 2.76,
      w: 1.55,
      h: 0.24,
      align: "center",
      fontSize: 12.5,
      bold: true,
    });
    if (index < labels.length - 1) {
      slide.addShape(shape("chevron"), {
        x: x + 1.92,
        y: 2.77,
        w: 0.26,
        h: 0.2,
        line: { color: hex(theme.palette.accent, "B58A2A"), transparency: 100 },
        fill: { color: hex(theme.palette.accent, "B58A2A"), transparency: 0 },
      });
    }
  });
  slide.addText(bulletRuns(spec.body.slice(0, 4)), {
    x: 1.0,
    y: 4.35,
    w: 11.0,
    h: 1.55,
    fontFace: themeFonts(theme).body,
    fontSize: 13.5,
    color: hex(theme.palette.text, "1B1E23"),
    paraSpaceAfterPt: 10,
    margin: 0,
  });
}

function drawArchitecture(slide, spec, theme, slideAsset, visual) {
  addHeader(slide, spec, theme, slideAsset);
  const nodes = (visual.nodes || []).slice(0, 6);
  nodes.forEach((item, index) => {
    const row = index < 3 ? 0 : 1;
    const col = index % 3;
    const x = 1.05 + col * 3.65;
    const y = 1.95 + row * 1.65;
    slide.addShape(shape("roundRect"), {
      x,
      y,
      w: 2.55,
      h: 0.85,
      rectRadius: 0.05,
      line: { color: hex(theme.palette.line, "D7C9B8"), transparency: 100 },
      fill: { color: row === 0 ? "FFFFFF" : hex(theme.palette.surface_alt, "EDE3D6"), transparency: 0 },
    });
    addText(slide, item, {
      x: x + 0.16,
      y: y + 0.28,
      w: 2.2,
      h: 0.24,
      align: "center",
      fontSize: 12.5,
      bold: true,
    });
  });
  if (nodes.length >= 4) {
    [0, 1, 2].forEach((col) => {
      slide.addShape(shape("line"), {
        x: 2.3 + col * 3.65,
        y: 2.8,
        w: 0,
        h: 0.78,
        line: { color: hex(theme.palette.accent, "B58A2A"), width: 1.5 },
      });
    });
  }
  slide.addText(bulletRuns(spec.body.slice(0, 4)), {
    x: 0.98,
    y: 5.1,
    w: 11.1,
    h: 1.15,
    fontFace: themeFonts(theme).body,
    fontSize: 13.2,
    paraSpaceAfterPt: 10,
    color: hex(theme.palette.text, "1B1E23"),
    margin: 0,
  });
}

function drawMetrics(slide, spec, theme, slideAsset, visual) {
  addHeader(slide, spec, theme, slideAsset);
  const cards = (visual.cards || []).slice(0, 4);
  cards.forEach((card, index) => {
    const x = 0.95 + index * 3.0;
    slide.addShape(shape("roundRect"), {
      x,
      y: 1.95,
      w: 2.45,
      h: 1.65,
      rectRadius: 0.05,
      line: { color: hex(theme.palette.line, "D7C9B8"), transparency: 100 },
      fill: { color: "FFFFFF", transparency: 0 },
    });
    addText(slide, card.value, {
      x: x + 0.16,
      y: 2.25,
      w: 2.1,
      h: 0.42,
      align: "center",
      fontSize: 21,
      bold: true,
      color: hex(theme.palette.primary, "7A0019"),
    });
    addText(slide, card.label, {
      x: x + 0.16,
      y: 2.85,
      w: 2.1,
      h: 0.26,
      align: "center",
      fontSize: 11.5,
      color: hex(theme.palette.muted, "66707A"),
    });
  });
  slide.addText(bulletRuns(spec.body.slice(0, 4)), {
    x: 0.98,
    y: 4.35,
    w: 11.1,
    h: 1.35,
    fontFace: themeFonts(theme).body,
    fontSize: 13.2,
    paraSpaceAfterPt: 10,
    color: hex(theme.palette.text, "1B1E23"),
    margin: 0,
  });
}

function drawComparison(slide, spec, theme, slideAsset, visual) {
  addHeader(slide, spec, theme, slideAsset);
  const columns = visual.columns || [];
  columns.slice(0, 2).forEach((column, index) => {
    const x = index === 0 ? 0.95 : 6.8;
    slide.addShape(shape("roundRect"), {
      x,
      y: 1.8,
      w: 5.4,
      h: 4.45,
      rectRadius: 0.05,
      line: { color: hex(theme.palette.line, "D7C9B8"), transparency: 100 },
      fill: { color: "FFFFFF", transparency: 0 },
    });
    addText(slide, column.label, {
      x: x + 0.28,
      y: 2.04,
      w: 2.1,
      h: 0.25,
      fontSize: 13,
      bold: true,
      color: hex(theme.palette.accent, "B58A2A"),
    });
    slide.addText(bulletRuns(column.items || []), {
      x: x + 0.3,
      y: 2.45,
      w: 4.65,
      h: 3.2,
      fontSize: 13.5,
      color: hex(theme.palette.text, "1B1E23"),
      paraSpaceAfterPt: 10,
      margin: 0,
    });
  });
}

function drawClosing(slide, spec, theme, slideAsset) {
  addHeader(slide, spec, theme, slideAsset);
  spec.body.slice(0, 4).forEach((item, index) => {
    slide.addShape(shape("roundRect"), {
      x: 1.0,
      y: 1.9 + index * 0.95,
      w: 10.9,
      h: 0.62,
      rectRadius: 0.05,
      line: { color: hex(theme.palette.line, "D7C9B8"), transparency: 100 },
      fill: { color: index === 0 ? hex(theme.palette.surface_alt, "EDE3D6") : "FFFFFF", transparency: 0 },
    });
    addText(slide, item, {
      x: 1.26,
      y: 2.12 + index * 0.95,
      w: 10.1,
      h: 0.22,
      fontSize: 14,
      bold: index === 0,
    });
  });
}

function drawThankYou(slide, spec, theme, slideAsset) {
  const fonts = themeFonts(theme);
  addHeader(slide, spec, theme, slideAsset);
  addText(slide, "欢迎交流", {
    x: 4.4,
    y: 2.45,
    w: 4.2,
    h: 0.6,
    align: "center",
    fontFace: fonts.title,
    fontSize: 24,
    bold: true,
    color: hex(theme.palette.primary, "7A0019"),
  });
  addText(slide, (spec.body || []).filter(Boolean).join("  "), {
    x: 3.3,
    y: 3.3,
    w: 6.5,
    h: 0.3,
    align: "center",
    fontSize: 12.5,
    color: hex(theme.palette.muted, "66707A"),
  });
}

function drawSlide(slide, spec, theme, slideAsset, visual) {
  const slideType = spec.slide_type;
  if (slideType === "cover") return drawCover(slide, spec, theme, slideAsset);
  if (slideType === "agenda") return drawAgenda(slide, spec, theme, slideAsset);
  if (slideType === "codebase_file_role" || slideType === "limitations_risks") return drawComparison(slide, spec, theme, slideAsset, visual.visual_kind === "comparison_cards" ? visual : { columns: [{ label: "关键信息", items: spec.body.slice(0, 3) }, { label: "讲解重点", items: spec.body.slice(1, 4) }] });
  if (["data_representation", "architecture_diagram", "algorithm_mechanism"].includes(slideType)) return drawArchitecture(slide, spec, theme, slideAsset, visual);
  if (["training_pipeline", "execution_loop"].includes(slideType)) return drawProcess(slide, spec, theme, slideAsset, visual);
  if (slideType === "evaluation_results") return drawMetrics(slide, spec, theme, slideAsset, visual);
  if (slideType === "conclusion_next_steps") return drawClosing(slide, spec, theme, slideAsset);
  if (slideType === "thank_you") return drawThankYou(slide, spec, theme, slideAsset);
  return drawBulletCards(slide, spec, theme, slideAsset);
}

function main() {
  const args = parseArgs(process.argv);
  const payload = readJson(args["payload-json"]);
  const pptx = new PptxGenJS();
  SHAPE_TYPES = pptx.ShapeType || {};
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "Codex thu-ppt-generator";
  pptx.company = "Tsinghua-style technical deck generator";
  pptx.subject = payload.plan.title;
  pptx.title = payload.plan.title;
  const fonts = themeFonts(payload.theme);
  pptx.theme = {
    headFontFace: fonts.title,
    bodyFontFace: fonts.body,
    lang: "zh-CN",
  };

  const slideAssets = payload.assets.slide_assets || [];
  const visualIndex = {};
  for (const item of payload.visual_plan.slides || []) visualIndex[item.slide_index] = item;

  payload.plan.slides.forEach((spec, idx) => {
    const slide = pptx.addSlide();
    const slideAsset = slideAssets[idx] || payload.assets.global_assets || {};
    drawSlide(slide, spec, payload.theme, slideAsset, (visualIndex[idx + 1] || {}).visual || {});
    if (spec.slide_type !== "cover") addFooter(slide, payload.plan.title, payload.theme, idx + 1, payload.plan.slides.length);
    warnIfSlideHasOverlaps(slide, pptx, { muteContainment: true });
    warnIfSlideElementsOutOfBounds(slide, pptx);
  });

  pptx.writeFile({ fileName: args["output-pptx"] || payload.output_pptx });
}

main();
