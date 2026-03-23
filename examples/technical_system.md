# 智能体技能升级架构汇报

汇报人：研发平台组
日期：2026-03-18

## 现状问题

- 旧版生成器把输入按段落切成很多页，导致信息密度低但节奏拖沓。
- 对代码、模块、接口和执行链路理解不足，技术材料经常被原样贴到幻灯片上。
- 资产选择偏随机，图像与页面主旨关联弱。

## 新架构

```python
def run_pipeline(input_text):
    parsed = parse_input(input_text)
    analysis = analyze_document(parsed)
    plan = plan_slides(analysis)
    assets = select_assets(plan)
    improved = lint_and_improve(plan, assets)
    return build_ppt(improved, assets)
```

- 输入先进入 `parse_input`，提取章节、代码块、时间线、指标和叙事线索。
- `analyze_document` 识别 audience、purpose、core message、technical density 和 visual intent。
- `plan_slides` 决定哪些内容应成为架构图、流程图、卡片页或指标页。
- `lint_and_improve` 检查过多幻灯片、弱视觉支持和重复布局，并自动重构。

## 数据流

- User Request -> Parse Layer -> Narrative Engine -> Slide Blueprint -> Asset Matcher -> Quality Loop -> PptxGenJS Renderer
- Parse Layer 读取 markdown、plain text、outline 与 code block。
- Narrative Engine 压缩冗余信息，并把系统说明转成可讲述的结构。
- Quality Loop 在最终渲染前执行 slide merge、layout swap、diagram upgrade。

## 结果

- 幻灯片数量减少 30%
- 技术材料默认转成流程或架构表达
- 输出同时保留 `final_deck.pptx` 与 `deck_source.js`
