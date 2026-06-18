# Design

## Visual Direction

Weather Lab 采用浅色、低噪声的数据工作台风格。界面应接近 Arc 和 Notion 的简洁感：信息密度适中，边界清楚，视觉表达轻，但不空。

主视觉是合规中国轮廓图。地图保持单色和安静，站点点位承担天气状态、当前温度、选中反馈和动效。

禁用 emoji。天气状态使用 lucide 图标或自制 SVG 图标。

## Theme

默认使用浅色主题。

物理场景：课程答辩时，界面在笔记本或投影屏上展示，环境光较亮，观看者距离屏幕较远。浅色界面更利于读数、地图轮廓和图表线条识别。

背景与层级：

- 页面背景：轻微冷灰。
- 内容框：接近白色，但不使用纯白。
- 边界：低对比细线。
- 阴影：少量，用于浮层或可点击区域，不用于装饰。

## Color

颜色策略：Restrained。

主色使用低饱和青绿，只用于选中站点、主按钮、活动图线和焦点状态。页面不使用高饱和渐变，不使用科技大屏蓝。

建议 token：

```css
:root {
  --background: oklch(0.975 0.006 225);
  --foreground: oklch(0.23 0.012 230);

  --surface: oklch(0.992 0.004 225);
  --surface-muted: oklch(0.955 0.007 225);
  --border: oklch(0.88 0.01 225);

  --primary: oklch(0.58 0.12 190);
  --primary-foreground: oklch(0.98 0.006 190);
  --focus: oklch(0.62 0.12 190);

  --muted: oklch(0.64 0.015 225);
  --muted-foreground: oklch(0.45 0.014 225);

  --danger: oklch(0.58 0.16 30);
  --warning: oklch(0.72 0.13 75);
}
```

指标色：

```css
:root {
  --metric-temperature: oklch(0.63 0.14 45);
  --metric-humidity: oklch(0.60 0.12 245);
  --metric-pressure: oklch(0.57 0.08 300);
  --metric-wind-speed: oklch(0.58 0.11 150);
  --metric-wind-direction: oklch(0.56 0.10 270);
}
```

使用规则：

- 主色不超过界面的 10%。
- 指标色只用于图表线、图例、少量状态标记。
- 非选中站点使用中性灰，不使用弱彩色。
- 禁止大面积蓝色、紫色或青色渐变。

## Typography

主字体使用思源黑体。

```css
font-family:
  "Source Han Sans SC",
  "Noto Sans CJK SC",
  "Noto Sans SC",
  "Microsoft YaHei UI",
  "Microsoft YaHei",
  system-ui,
  sans-serif;
```

数字读数启用等宽数字：

```css
font-variant-numeric: tabular-nums;
```

字号建议：

```text
Page title: 20px / 600
Section title: 16px / 600
Body: 14px / 400
Label: 12px / 500
Large metric: 28-36px / 600
Table: 13px / 400
```

规则：

- 不使用 display font。
- 不使用流式字号。
- 数据读数优先清晰和对齐。
- 中文文案使用书面语，短句，避免口语化。

## Layout

总览页结构：

```text
Title
Map Card
Current Metrics Card
```

地图框：

- 占据总览页主要视觉区域。
- 桌面端高度建议 520-620px。
- 右上角放刷新按钮。
- 站点点位叠加在轮廓图上。

当前指标框：

- 放在地图下方。
- 一行展示五指标。
- 右下角放“查看详细数据”。
- 小屏下转为两列或单列。

详细数据页结构：

```text
Title + Back Action
Filter Bar
Trend Grid
Summary Strip
Records Table
```

桌面端趋势图使用两列；平板和手机端降为单列。

## Components

### Buttons

使用 shadcn/ui Button。

刷新按钮：

- `variant="ghost"` 或轻边框按钮。
- 放在地图框右上角。
- 使用 lucide `RefreshCw` 图标。
- 文案可为“刷新”，也可只保留图标和 tooltip。

主操作按钮：

- 用于“查看详细数据”“返回总览”。
- 不使用强烈填充色作为默认样式。
- 选中和 hover 使用低饱和青绿。

### Cards

只使用两类内容框：

- 地图框。
- 指标、图表或表格框。

规则：

- 圆角不超过 8px。
- 边界优先于阴影。
- 不嵌套卡片。
- 不使用玻璃拟态。

### Station Marker

站点点位由三部分组成：

```text
WeatherIcon
StationName
Temperature
```

状态：

- 默认：中性灰点位，标签低对比。
- hover：标签提升，点位轻微放大。
- selected：青绿外圈，标签加重。
- loading：保留点位，温度位置显示 skeleton。
- unavailable：灰色点位，标签显示“暂无”。

禁用 emoji。天气图标使用 lucide 图标或自制 SVG。

### Metric Readout

五指标读数固定顺序：

```text
温度
湿度
气压
风速
风向
```

每个读数组成：

```text
value + unit
label
```

规则：

- value 使用 tabular numbers。
- unit 不抢数值层级。
- 风向可以显示角度和方位短标签，例如 `200 deg SSW`。
- 指标不只靠颜色区分。

## Map

地图使用合规来源处理出的单色中国轮廓。

要求：

- 使用官方标准地图或审查通过的地图文件。
- 保留官方边界。
- 不使用来源不明的 GeoJSON。
- 不自行绘制或修改国界线。
- 报告中注明来源、版本和审图号。

视觉：

```css
--map-fill: oklch(0.94 0.01 215);
--map-stroke: oklch(0.68 0.025 215);
--map-stroke-muted: oklch(0.80 0.012 215);
```

地图本身保持安静：

- 单色浅填充。
- 细线边界。
- 无彩色行政区。
- 无地图纹理。
- 无发光边缘。

站点点位可以明显动效，但动效集中在点位、标签和天气状态，不作用于国界轮廓。

## Motion

动画允许较多，但必须服务于状态变化。

允许：

- 地图点位 pulse。
- 当前站点切换时点位外圈扩散。
- 天气图标短暂 morph 或 fade。
- 数值切换 fade/slide。
- 图表线条进入时 line draw。
- 页面进入时轻微 reveal。

禁止：

- 拖沓转场。
- 大幅弹跳。
- 装饰性循环动画。
- 背景漂浮物。
- 因动画导致读数延迟出现。

时长：

```text
Micro interaction: 120-180ms
Panel reveal: 180-240ms
Map marker transition: 200-320ms
Chart draw: 300-500ms
```

缓动：

```css
cubic-bezier(0.16, 1, 0.3, 1)
```

`prefers-reduced-motion: reduce` 时：

- 禁用 pulse。
- 禁用 line draw。
- 状态即时切换。
- 保留颜色、边界、文本变化。

Remotion 可以用于生成高质量 SVG 或动画资产，但不作为运行时依赖的默认选项。运行时动效优先用 CSS、SVG 和 Framer Motion 实现。

## Charts

图表使用 Recharts，并套 shadcn/ui chart 风格。

规则：

- 细线图。
- 少网格线。
- 坐标轴弱化。
- tooltip 清楚。
- 图例可读。
- 不使用面积渐变。
- 不使用厚重阴影。
- 不使用 3D 图。

趋势图分组：

- 温湿度趋势：温度与湿度。
- 气压趋势：气压。
- 风况：风速与风向。
- 多站对比：同一指标的三站点对比。

图表空态：

- 显示简短说明。
- 不使用插画。
- 不使用“暂无数据哦”等口语化文案。

## Copy

文案使用中文书面语。句子短，直接描述功能和状态。

推荐：

- `总览`
- `详细数据`
- `查看详细数据`
- `返回总览`
- `温湿度趋势`
- `气压趋势`
- `风况`
- `多站对比`
- `统计摘要`
- `数据记录`

避免：

- 口语化表达。
- AI 模板文案。
- 解释系统实现的页面文案。
- 使用感叹号。
- 使用 emoji。

## Accessibility

要求：

- 浅色优先。
- 文本和关键图形保持足够对比度。
- 指标不能只靠颜色区分。
- 站点点位可键盘聚焦。
- 刷新、查看详细数据、返回总览可键盘操作。
- 支持 reduced motion。

ARIA 不列为课程强制范围，但应使用语义化元素和 shadcn/ui 的基础可访问能力。
