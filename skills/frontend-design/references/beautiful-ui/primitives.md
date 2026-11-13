# Beautiful UI 关键组件实现模式与代码范式

---

## 一、 人机协同审批卡片 (`ApprovalCard`)

用于大模型向用户发起决策询问（单选自动推进、多选显式提交、支持自定义手填、支持跳过）：

```tsx
"use client";

import React, { useState } from "react";

interface Question {
  q: string;
  type: "radio" | "check";
  options: string[];
}

export function ApprovalCard({
  questions,
  onFinish,
}: {
  questions: Question[];
  onFinish: (results: { answers: Record<number, number[]>; custom: Record<number, string> }) => void;
}) {
  const [qi, setQi] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number[]>>({});
  const [custom, setCustom] = useState<Record<number, string>>({});

  const question = questions[qi];
  const selected = answers[qi] ?? [];
  const hasAnswer = selected.length > 0 || Boolean(custom[qi]?.trim());
  const isLast = qi === questions.length - 1;

  const handleSelect = (idx: number) => {
    setAnswers((prev) => {
      const curr = prev[qi] ?? [];
      const next =
        question.type === "radio"
          ? [idx]
          : curr.includes(idx)
          ? curr.filter((i) => i !== idx)
          : [...curr, idx];
      return { ...prev, [qi]: next };
    });

    if (question.type === "radio") {
      setCustom((prev) => ({ ...prev, [qi]: "" }));
      // 单选延迟 400ms 自动翻页
      setTimeout(() => {
        if (!isLast) setQi((i) => i + 1);
        else onFinish({ answers, custom });
      }, 400);
    }
  };

  return (
    <div className="relative overflow-hidden rounded-2xl border border-line bg-surface p-5 shadow-lg">
      <div className="text-[14px] font-semibold text-ink">{question.q}</div>

      {/* 选项菜单 */}
      <div className="mt-3.5 flex flex-col gap-1.5">
        {question.options.map((opt, idx) => {
          const active = selected.includes(idx);
          return (
            <button
              key={idx}
              type="button"
              onClick={() => handleSelect(idx)}
              className={`flex items-center gap-2.5 rounded-xl px-3 py-2 text-left text-[13px] transition-colors duration-150 ${
                active ? "bg-accent/10 text-accent font-medium" : "text-ink-2 hover:bg-hover"
              }`}
            >
              <span className={`flex size-4 items-center justify-center rounded-full border transition-colors ${
                active ? "border-accent bg-accent text-white" : "border-line-strong"
              }`}>
                {active && <span className="size-1.5 rounded-full bg-white" />}
              </span>
              <span>{opt}</span>
            </button>
          );
        })}

        {/* 自定义输入框 */}
        <input
          type="text"
          placeholder="补充或手写其它要求…"
          value={custom[qi] ?? ""}
          onChange={(e) => setCustom({ ...custom, [qi]: e.target.value })}
          className="mt-1 rounded-xl border border-line bg-transparent px-3 py-2 text-[13px] text-ink outline-none placeholder:text-ink-3 focus:border-accent"
        />
      </div>

      {/* 底部导航栏与状态 */}
      <div className="mt-5 flex items-center justify-between border-t border-dashed border-line pt-3">
        <span className="font-mono text-[12px] text-ink-3">
          {qi + 1} / {questions.length}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => (!isLast ? setQi((i) => i + 1) : onFinish({ answers, custom }))}
            className="rounded-full px-3 py-1 text-[12px] text-ink-3 hover:text-ink"
          >
            跳过
          </button>
          <button
            type="button"
            disabled={!hasAnswer}
            onClick={() => (!isLast ? setQi((i) => i + 1) : onFinish({ answers, custom }))}
            className="rounded-full bg-accent px-4 py-1.5 text-[12.5px] font-medium text-white shadow-sm transition-all duration-150 hover:bg-accent/90 disabled:opacity-40"
          >
            {isLast ? "完成并继续" : "下一项"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## 二、 可折叠思考轨迹 (`ThinkingState`)

支持大模型输出中的“思考中”微光动画、展开后的步骤列表与耗时显现：

```tsx
"use client";

import React, { useState } from "react";
import { ChevronRight, Sparkles, Check } from "lucide-react";

export function ThinkingState({
  isThinking,
  steps,
  durationSec,
}: {
  isThinking: boolean;
  steps: { text: string; done: boolean; detail?: string }[];
  durationSec?: number;
}) {
  const [expanded, setExpanded] = useState(isThinking);

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-fit items-center gap-2 rounded-lg px-2 py-1 text-[13px] font-medium text-ink-2 hover:bg-hover"
      >
        <Sparkles className="size-3.5 text-accent animate-pulse" />
        {isThinking ? (
          <span className="bg-gradient-to-r from-ink-3 via-ink to-ink-3 bg-[length:200%_100%] bg-clip-text text-transparent animate-shimmer">
            深度思考中…
          </span>
        ) : (
          <span className="text-ink-3">已深度思考 ({durationSec ?? 3} 秒)</span>
        )}
        <ChevronRight
          className={`size-3.5 text-ink-3 transition-transform duration-200 ${
            expanded ? "rotate-90" : ""
          }`}
        />
      </button>

      {/* 平滑折叠容器 */}
      <div
        className={`grid transition-[grid-template-rows,opacity] duration-300 ${
          expanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0 pointer-events-none"
        }`}
      >
        <div className="overflow-hidden">
          <div className="relative ml-2.5 border-l border-line pl-3.5 py-1.5 flex flex-col gap-2">
            {steps.map((st, i) => (
              <div key={i} className="flex items-center gap-2 text-[12.5px]">
                {st.done ? (
                  <Check className="size-3 text-emerald-500 shrink-0" />
                ) : (
                  <div className="size-1.5 rounded-full bg-accent shrink-0 animate-ping" />
                )}
                <span className={st.done ? "text-ink-3" : "text-ink font-medium"}>
                  {st.text}
                </span>
                {st.detail && (
                  <span className="font-mono text-[11px] text-ink-3">({st.detail})</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
```

---

## 三、 流式问答与数据源引用堆叠 (`StreamingTextWithSources`)

在模型输出的段落中，行内优雅嵌入多来源网站 Favicon 堆叠徽章，点击展开事实依据列表：

- **堆叠 Favicon**：使用 `-space-x-1` 与 `shadow-[0_0_0_1.5px_var(--canvas)]` 做出高精致度的切片重叠效果。
- **引用列表**：展开包含清晰的站名、域名小字与点击跳转外部链接。
- **操作条**：在文字流式结束后平滑淡入（`opacity: 0 -> 1`），包含 Copy、Regenerate、Like、Dislike。
