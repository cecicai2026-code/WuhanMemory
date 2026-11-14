import type { Metadata } from "next";
import { Scene } from "@/components/shell/Scene";
import {
  BrassButton,
  Label,
  LineInput,
  NoteButton,
  Paper,
  PaperMark,
  PaperTitle,
  PencilNote,
  Rule,
  Soft,
  Stamp,
  TextLink,
  Title
} from "@/components/ui";
import s from "./styleguide.module.css";

export const metadata: Metadata = { title: "样式参考" };

/**
 * 样式参考页：把设计规范里的颜色、字体和基础组件各摆一份，方便对照检查。
 * 不放进菜单，直接打开 /styleguide。
 */
const COLORS: Array<[name: string, variable: string, use: string]> = [
  ["暗角黑", "--black", "页面最外圈、暗角"],
  ["木头暗部", "--wood-dark", "桌面的暗处"],
  ["木头", "--wood", "桌面"],
  ["木头亮部", "--wood-lit", "灯光照到的桌面"],
  ["墨绿", "--green", "器物"],
  ["黄铜", "--brass", "边框、铭牌、按钮"],
  ["黄铜高光", "--brass-bright", "悬停、高光"],
  ["黄铜暗部", "--brass-deep", "金属暗面、细线"],
  ["纸", "--paper", "信纸；深色底上的主文字"],
  ["纸的暗部", "--paper-shade", "纸的阴影面"],
  ["墨", "--ink", "纸上的正文"],
  ["淡墨", "--ink-soft", "纸上的次要文字"],
  ["胶片橙", "--film", "胶片底片"],
  ["樱桃红", "--cherry", "每一幕最多一个的亮点"],
  ["铅笔蓝灰", "--pencil", "纸上的手写批注"],
  ["红褐", "--oxblood", "页码小字、已过期章"],
  ["次要文字", "--text-secondary", "深色底上的说明"],
  ["标注字", "--text-muted", "四角的标注"]
];

export default function StyleguidePage() {
  return (
    <Scene
      scene={{ no: "00", name: "样式参考" }}
      count={`${COLORS.length} 种颜色`}
      title="样式参考"
      kicker="Design System v3"
      intro="颜色、字体和基础组件各摆一份，对照 docs/design/design-system.md 检查。"
    >
      <div className={s.page}>
        <section aria-labelledby="sg-colors">
          <Title level={2} id="sg-colors" className={s.h2}>
            颜色
          </Title>
          <ul className={s.swatches}>
            {COLORS.map(([name, variable, use]) => (
              <li key={variable}>
                <span className={s.chip} style={{ background: `var(${variable})` }} />
                <span className={s.swatchName}>{name}</span>
                <Label>{variable}</Label>
                <span className={s.swatchUse}>{use}</span>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="sg-type">
          <Title level={2} id="sg-type" className={s.h2}>
            四种字
          </Title>
          <div className={s.voices}>
            <div>
              <Label>标注 · IBM Plex Mono + 思源黑体</Label>
              <p>
                <Label className={s.bright}>第 02 幕 — 胶卷 · Scene 02 · 01 / 10</Label>
              </p>
            </div>
            <div>
              <Label>标题 · Cormorant Garamond 斜体 + 思源宋体</Label>
              <Title level={2}>黄鹤楼 Yellow Crane Tower</Title>
            </div>
            <Paper>
              <PaperMark>纸上正文 · Courier Prime + 霞鹜文楷</PaperMark>
              <PaperTitle>纸上的小标题 Paper title</PaperTitle>
              <p>
                纸上的正文用打字机字体，行高 1.8。The quick brown fox, 0123456789. <Soft>次要的文字用淡墨色。</Soft>
              </p>
              <Rule dashed />
              <p>
                <strong>条目名称</strong>　<PencilNote>待补充</PencilNote>
              </p>
              <PaperMark className={s.gap}>批注 · Caveat + 楷体，只出现在纸面上</PaperMark>
              <p>
                <PencilNote>handwritten note 手写的批注</PencilNote>
              </p>
            </Paper>
          </div>
        </section>

        <section aria-labelledby="sg-buttons">
          <Title level={2} id="sg-buttons" className={s.h2}>
            按钮和链接
          </Title>
          <div className={s.row}>
            <BrassButton round>开始规划</BrassButton>
            <BrassButton>把这里加入行程</BrassButton>
            <BrassButton disabled>不可点</BrassButton>
            <NoteButton href="/styleguide">小纸签</NoteButton>
            <TextLink href="/styleguide">← 文字链接</TextLink>
            <TextLink href="/styleguide" current>
              当前项
            </TextLink>
          </div>
        </section>

        <section aria-labelledby="sg-paper">
          <Title level={2} id="sg-paper" className={s.h2}>
            纸、印章和输入框
          </Title>
          <div className={s.papers}>
            <Paper tilt={-1.5}>
              <PaperMark>信纸</PaperMark>
              <PaperTitle>三种状态</PaperTitle>
              <Rule />
              <p className={s.row}>
                <Stamp status="verified" />
                <Stamp status="pending" />
                <Stamp status="expired" />
              </p>
              <Rule dashed />
              <LineInput id="sg-input" label="输入框是纸上的一条横线" placeholder="在这里打字试试…" />
              <div className={s.gap}>
                <LineInput id="sg-input-off" label="还没接通的输入框" placeholder="暂时不能输入" disabled />
              </div>
            </Paper>
            <Paper kind="card" tilt={1.5}>
              <PaperMark>索引卡</PaperMark>
              <PaperTitle level={3}>带横线格的卡片</PaperTitle>
              <p>用来放一条一条的内容。</p>
              <p>
                <Soft>横线和文字的行对齐。</Soft>
              </p>
            </Paper>
            <Paper kind="card" href="/styleguide" tilt={-1}>
              <PaperMark>可以点的卡</PaperMark>
              <PaperTitle level={3}>鼠标移上来</PaperTitle>
              <p>整张卡抬起、转正。</p>
            </Paper>
          </div>
          <p className={s.row}>
            <Label>深色底上的状态：</Label>
            <Stamp status="verified" onDark />
            <Stamp status="pending" onDark />
            <Stamp status="expired" onDark />
          </p>
        </section>
      </div>
    </Scene>
  );
}
