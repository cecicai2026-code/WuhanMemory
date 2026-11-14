/**
 * 基础组件。每个组件对应设计规范第 7 节里的一件"实物"。
 * 这些组件只管长相，不含任何业务数据。
 */
import Link from "next/link";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import s from "./ui.module.css";

function cx(...names: Array<string | false | null | undefined>) {
  return names.filter(Boolean).join(" ");
}

/** 标注字：四角的小字 */
export function Label({ className, ...rest }: ComponentPropsWithoutRef<"span">) {
  return <span className={cx(s.label, className)} {...rest} />;
}

/** 标题字。level 决定是 h1 还是 h2 */
export function Title({
  level = 1,
  className,
  ...rest
}: ComponentPropsWithoutRef<"h1"> & { level?: 1 | 2 }) {
  const Tag = level === 1 ? "h1" : "h2";
  return <Tag className={cx(s.title, className)} {...rest} />;
}

interface BrassProps {
  children: ReactNode;
  /** 给了 href 就是链接，否则是按钮 */
  href?: string;
  round?: boolean;
  disabled?: boolean;
  type?: "button" | "submit";
  onClick?: () => void;
  className?: string;
}

/** 主按钮：黄铜铭牌（round 时是黄铜圆按钮） */
export function BrassButton({ children, href, round, disabled, type = "button", onClick, className }: BrassProps) {
  const cls = cx(s.brass, round && s.round, className);
  if (href && !disabled) {
    return (
      <Link className={cls} href={href}>
        {children}
      </Link>
    );
  }
  return (
    <button className={cls} type={type} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

interface NoteProps {
  children: ReactNode;
  href?: string;
  /** 用作切换时：true 是选中，false 是没选中 */
  pressed?: boolean;
  onClick?: () => void;
  className?: string;
}

/** 次按钮：一张小纸签 */
export function NoteButton({ children, href, pressed, onClick, className }: NoteProps) {
  if (href) {
    return (
      <Link className={cx(s.note, className)} href={href}>
        {children}
      </Link>
    );
  }
  return (
    <button className={cx(s.note, className)} type="button" aria-pressed={pressed} onClick={onClick}>
      {children}
    </button>
  );
}

interface TextLinkProps {
  children: ReactNode;
  href: string;
  /** 当前所在的项：黄铜色并带下划线 */
  current?: boolean;
  onPaper?: boolean;
  className?: string;
}

/** 文字链接：标注字体的小字 */
export function TextLink({ children, href, current, onPaper, className }: TextLinkProps) {
  return (
    <Link className={cx(s.link, onPaper && s.onPaper, className)} href={href} aria-current={current ? "page" : undefined}>
      {children}
    </Link>
  );
}

interface PaperProps {
  children: ReactNode;
  /** letter 是信纸，card 是带横线格的索引卡 */
  kind?: "letter" | "card";
  /** 给了 href，整张纸就是一个链接，悬停时抬起 */
  href?: string;
  /** 随意摆放的角度，2 到 6 度以内（第 5 节） */
  tilt?: number;
  as?: "div" | "section" | "article" | "li";
  className?: string;
  "aria-label"?: string;
}

/** 信纸或索引卡。纸上的文字用墨色 */
export function Paper({ children, kind = "letter", href, tilt, as: Tag = "div", className, ...rest }: PaperProps) {
  const style = tilt ? { transform: `rotate(${tilt}deg)` } : undefined;
  const cls = cx(s.paper, kind === "card" && s.card, href && s.liftable, className);
  if (href) {
    return (
      <Link className={cls} style={style} href={href} {...rest}>
        {children}
      </Link>
    );
  }
  return (
    <Tag className={cls} style={style} {...rest}>
      {children}
    </Tag>
  );
}

/** 纸上的小标题 */
export function PaperTitle({ level = 2, className, ...rest }: ComponentPropsWithoutRef<"h2"> & { level?: 2 | 3 }) {
  const Tag = level === 2 ? "h2" : "h3";
  return <Tag className={cx(s.paperTitle, className)} {...rest} />;
}

/** 纸左上角的红褐色小字 */
export function PaperMark({ className, ...rest }: ComponentPropsWithoutRef<"p">) {
  return <p className={cx(s.paperMark, className)} {...rest} />;
}

/** 纸上的次要文字 */
export function Soft({ className, ...rest }: ComponentPropsWithoutRef<"span">) {
  return <span className={cx(s.paperSoft, className)} {...rest} />;
}

/** 纸上的横线。dashed 是条目之间的虚线 */
export function Rule({ dashed }: { dashed?: boolean }) {
  return <hr className={cx(s.rule, dashed && s.ruleDashed)} />;
}

export type Status = "verified" | "pending" | "expired";

const STATUS_TEXT: Record<Status, string> = {
  verified: "已核实",
  pending: "待确认",
  expired: "已过期"
};

interface StampProps {
  status: Status;
  /** 不给就用默认文字：已核实、待确认、已过期 */
  children?: ReactNode;
  /** 盖在深色底上时换一组更亮的颜色 */
  onDark?: boolean;
  className?: string;
}

/** 状态：绿色印章、蓝灰色铅笔批注、红色印章。一定带文字，不只靠颜色 */
export function Stamp({ status, children, onDark, className }: StampProps) {
  return <span className={cx(s.stamp, s[status], onDark && s.onDark, className)}>{children ?? STATUS_TEXT[status]}</span>;
}

/** 手写批注：只用在纸面上的短句，例如"待补充" */
export function PencilNote({ className, ...rest }: ComponentPropsWithoutRef<"span">) {
  return <span className={cx(s.pencil, className)} {...rest} />;
}

interface LineInputProps extends Omit<ComponentPropsWithoutRef<"input">, "className"> {
  label: string;
  /** 标签只给读屏软件，不显示 */
  hideLabel?: boolean;
}

/** 输入框：纸上的一条横线 */
export function LineInput({ label, hideLabel, id, ...rest }: LineInputProps) {
  return (
    <label className={s.field} htmlFor={id}>
      <span className={hideLabel ? "sr-only" : s.fieldLabel}>{label}</span>
      <input className={s.input} id={id} {...rest} />
    </label>
  );
}
