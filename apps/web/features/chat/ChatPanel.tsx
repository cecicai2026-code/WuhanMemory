"use client";

import { useMemo, useState } from "react";
import { CalendarDays, Send, Sparkles } from "lucide-react";
import type { ItineraryVersion } from "@wuhanmemory/shared";
import { createConversation, sendMessage } from "@/lib/api";

interface ChatPanelProps {
  itinerary: ItineraryVersion;
  onPlanningComplete: (versionId: string) => Promise<void>;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function ChatPanel({ itinerary, onPlanningComplete }: ChatPanelProps) {
  const [input, setInput] = useState("我想国庆去武汉玩 3 天，喜欢历史文化、美食和拍照，地铁优先。");
  const [isSending, setIsSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "已准备武汉 3 日 mock 行程，可继续调整节奏、交通和景点偏好。"
    }
  ]);

  const dateLabel = useMemo(
    () => `${itinerary.dateRange.start} - ${itinerary.dateRange.end}`,
    [itinerary.dateRange.end, itinerary.dateRange.start]
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = input.trim();
    if (!content || isSending) {
      return;
    }

    setIsSending(true);
    setMessages((current) => [...current, { role: "user", content }]);

    try {
      const conversation = await createConversation();
      const job = await sendMessage(conversation.conversationId, content);
      await onPlanningComplete(job.itineraryVersionId);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: "已用 mock LLM provider 生成结构化行程，并同步到地图和时间线。"
        }
      ]);
    } catch {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: "后端未启动，当前保持本地 mock 行程。"
        }
      ]);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="chat-panel">
      <div className="brand-row">
        <div>
          <p className="eyebrow">WuhanMemory</p>
          <h1>{itinerary.title}</h1>
        </div>
        <Sparkles aria-hidden="true" size={22} />
      </div>

      <div className="trip-meta">
        <span>
          <CalendarDays aria-hidden="true" size={16} />
          {dateLabel}
        </span>
        <span>{itinerary.travelerProfile.transportPreference}</span>
      </div>

      <div className="message-list" aria-live="polite">
        {messages.map((message, index) => (
          <p className={`message ${message.role}`} key={`${message.role}-${index}`}>
            {message.content}
          </p>
        ))}
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          rows={4}
          aria-label="旅行偏好"
        />
        <button type="submit" disabled={isSending} aria-label="发送规划请求">
          <Send aria-hidden="true" size={18} />
          <span>{isSending ? "规划中" : "发送"}</span>
        </button>
      </form>
    </div>
  );
}
