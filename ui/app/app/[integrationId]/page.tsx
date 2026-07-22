"use client";
import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import "@copilotkit/react-core/v2/styles.css";
import "./style.css";
import { CopilotChat } from "@copilotkit/react-core/v2";
import { CopilotKit, useCopilotChat, useCopilotChatInternal } from "@copilotkit/react-core";
import { TextMessage, MessageRole } from "@copilotkit/runtime-client-gql";

const TOOL_LABELS: Record<string, string> = {
  search_database:  "Searching",
  search_hybrid:    "Searching",
  search_authors:   "Searching authors",
  get_author_stats: "Analyzing authors",
  most_similar:     "Finding similar papers",
  get_faculties:    "Fetching faculties",
  get_schema:       "Reading schema",
  summarize_table:  "Summarizing",
  execute_query:    "Querying",
  expansion_agent:  "Expanding query",
};

const ActivityPill = () => {
  const { isLoading, messages = [] } = useCopilotChatInternal();
  const msgs = messages as any[];
  const [dots, setDots] = useState(1);

  useEffect(() => {
    if (!isLoading) return;
    const id = setInterval(() => setDots((d) => (d % 3) + 1), 500);
    return () => clearInterval(id);
  }, [isLoading]);

  if (!isLoading) return null;

  const completedIds = new Set(
    msgs.filter((m) => m.role === "tool").map((m) => m.toolCallId).filter(Boolean),
  );
  const lastAssistant = [...msgs].reverse().find((m) => m.role === "assistant");
  const activeCalls = (lastAssistant?.toolCalls ?? []).filter((tc: any) => !completedIds.has(tc.id));
  const toolName = activeCalls[activeCalls.length - 1]?.function?.name;
  const label = (toolName ? TOOL_LABELS[toolName] ?? toolName : null) ?? "Thinking";

  return (
    <div className="self-end flex items-center gap-1.5 rounded-full border border-[#e3dad8] bg-white px-4 py-1.5 text-[11px] text-[#002328] font-mono shadow-sm tracking-wide">
      <span className="h-1.5 w-1.5 rounded-full bg-[#002328] flex-shrink-0 activity-dot" />
      <span>{label}</span>
      <span className="inline-block w-[2ch] text-left">{".".repeat(dots)}</span>
    </div>
  );
};


interface AgenticChatProps {
  params: Promise<{ integrationId: string }>;
}

const groups = [
  {
    label: "Discover",
    suggestions: [
      { title: "Find experts", message: "Who are experts in the field of substance abuse and addiction?" },
      { title: "Author profile", message: "Create a short profile for Steven Verheyen based on recent publications." },
    ],
  },
  {
    label: "Explore",
    suggestions: [
      { title: "Explain a topic", message: "What is bossware?" },
      { title: "Similar papers", message: "What publication is most similar to: 'Mapping spatial organization of in vitro neuronal networks using high-content imaging'" },
    ],
  },
  {
    label: "Analyze",
    suggestions: [
      { title: "Publication stats", message: "What faculty has the largest share of publications in Dutch?" },
    ],
  },
];

const GroupedSuggestions = () => {
  const { appendMessage, visibleMessages = [] } = useCopilotChat();

  if (visibleMessages.length > 0) return null;

  const handleClick = (message: string) => {
    appendMessage(new TextMessage({ role: MessageRole.User, content: message }));
  };

  return (
    <div className="flex gap-6 px-4 pb-4">
      {groups.map((group) => (
        <div key={group.label} className="flex flex-col gap-1.5">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-zinc-400 px-1">
            {group.label}
          </span>
          <div className="flex flex-wrap gap-2">
            {group.suggestions.map((s) => (
              <button
                key={s.title}
                onClick={() => handleClick(s.message)}
                className="rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-sm text-zinc-700 transition-colors hover:border-zinc-400 hover:bg-zinc-50"
              >
                {s.title}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

const AgenticChat: React.FC<AgenticChatProps> = ({ params }) => {
  const unwrappedParams = React.use(params);
  const integrationId = unwrappedParams?.integrationId || "default";

  return (
    <CopilotKit
      runtimeUrl={`/api/copilotkit/${integrationId}`}
      agent="root_agent"
    >
      <Chat />
    </CopilotKit>
  );
};

const Chat = () => {
  return (
    <div className="flex justify-center items-center h-[90vh] w-full bg-white">
      <div className="flex h-full w-full max-w-5xl flex-col p-4 gap-2">
        <GroupedSuggestions />
        <div className="flex justify-end min-h-[2rem] items-center">
          <ActivityPill />
        </div>
        <div className="flex-1 min-h-0">
          <CopilotChat
            agentId="root_agent"
            className="h-full rounded-2xl border shadow-xl bg-white"
            labels={{
              welcomeMessageText: "Open Research Compass",
            }}
          />
        </div>
      </div>
    </div>
  );
};

const AgenticChatContainer = dynamic(() => Promise.resolve(AgenticChat), {
  ssr: false,
});

export default AgenticChatContainer;
