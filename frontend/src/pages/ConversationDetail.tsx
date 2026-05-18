import { type ReactNode, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { ArrowLeft, Clock, Loader2, MessagesSquare } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import type { ConversationDetail, MessageOut } from "@/types/api";

export function ConversationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const numericId = id ? parseInt(id, 10) : NaN;

  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isNaN(numericId)) {
      setError("Invalid conversation ID.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    api
      .getConversation(numericId)
      .then((data) => {
        setDetail(data);
      })
      .catch((exc) => {
        setError(exc instanceof Error ? exc.message : "Failed to load conversation.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [numericId]);

  return (
    <div className="space-y-8">
      {/* Back link */}
      <div>
        <Link
          to="/history"
          className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-hud-textDim transition-colors hover:text-hud-glow"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to history
        </Link>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center gap-2 font-mono text-[13px] text-hud-textFaint">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading conversation…
        </div>
      )}

      {/* Error state */}
      {error && (
        <Card className="border-hud-warn/40">
          <CardContent className="pt-5 text-sm text-hud-warn">{error}</CardContent>
        </Card>
      )}

      {detail && (
        <>
          {/* Page heading */}
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
              Conversation · ID #{detail.id} · {detail.source_name}
            </div>
            <h1 className="mt-2 font-display text-3xl uppercase tracking-[0.16em] text-hud-text">
              {detail.title ?? "(untitled)"}
            </h1>
          </div>

          {/* Metadata strip */}
          <div className="grid grid-cols-3 gap-4">
            <MetaStat
              label="Started"
              value={fmtDate(detail.started_at)}
              icon={<Clock className="h-3.5 w-3.5 text-hud-glow/70" />}
            />
            <MetaStat
              label="Ended"
              value={fmtDate(detail.ended_at)}
              icon={<Clock className="h-3.5 w-3.5 text-hud-glow/70" />}
            />
            <MetaStat
              label="Messages"
              value={detail.message_count.toLocaleString()}
              icon={<MessagesSquare className="h-3.5 w-3.5 text-hud-glow/70" />}
            />
          </div>

          {/* Summary */}
          {detail.summary && (
            <Card>
              <CardHeader>
                <CardTitle>Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="font-sans text-[14px] leading-relaxed text-hud-textDim">
                  {detail.summary}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Messages timeline */}
          <div className="space-y-4">
            <div className="font-display text-[10px] uppercase tracking-[0.4em] text-hud-textFaint">
              Timeline · {detail.messages.length} messages
            </div>
            {detail.messages.map((msg) => (
              <MessageCard key={msg.id} message={msg} />
            ))}
            {detail.messages.length === 0 && (
              <Card>
                <CardContent className="pt-5 text-center font-mono text-[13px] text-hud-textFaint">
                  No messages found for this conversation.
                </CardContent>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ── Metadata tile ──────────────────────────────────────────────────────────────

interface MetaStatProps {
  label: string;
  value: string;
  icon?: ReactNode;
}

function MetaStat({ label, value, icon }: MetaStatProps) {
  return (
    <div className="rounded-md border border-hud-line bg-hud-panel/40 px-4 py-3">
      <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.25em] text-hud-textFaint">
        {icon}
        {label}
      </div>
      <div className="mt-1.5 font-mono text-[12px] text-hud-text">{value}</div>
    </div>
  );
}

// ── Message card ───────────────────────────────────────────────────────────────

interface MessageCardProps {
  message: MessageOut;
}

function MessageCard({ message }: MessageCardProps) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";

  const borderClass = isUser
    ? "border-hud-glow/30"
    : isAssistant
      ? "border-hud-line"
      : "border-hud-textFaint/30";

  const bgClass = isUser
    ? "bg-hud-glow/5"
    : isAssistant
      ? "bg-hud-panel/40"
      : "";

  const opacityClass = !isUser && !isAssistant ? "opacity-80" : "";

  const roleLabel =
    message.role === "user"
      ? "User"
      : message.role === "assistant"
        ? "Assistant"
        : message.role;

  const roleColor = isUser
    ? "text-hud-glow"
    : isAssistant
      ? "text-hud-accent"
      : "text-hud-textFaint";

  return (
    <div
      className={`holo-panel rounded-lg ${borderClass} ${bgClass} ${opacityClass}`}
    >
      {/* Message header */}
      <div className="flex items-center justify-between border-b border-hud-line/40 px-5 py-2.5">
        <div className="flex items-center gap-3">
          <span
            className={`font-display text-[10px] uppercase tracking-[0.22em] ${roleColor}`}
          >
            {roleLabel}
          </span>
          <span className="font-mono text-[10px] text-hud-textFaint">
            #{message.sequence}
          </span>
        </div>
        <span className="font-mono text-[10px] text-hud-textFaint">
          {fmtDate(message.message_at)}
        </span>
      </div>

      {/* Message body */}
      <div className="px-5 py-4">
        {isAssistant ? (
          <div className="prose-hud">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        ) : (
          <div className="whitespace-pre-wrap font-sans text-[14px] leading-relaxed text-hud-text">
            {message.content}
          </div>
        )}
      </div>
    </div>
  );
}
