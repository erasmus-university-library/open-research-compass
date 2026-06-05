"use client";
import React from "react";
import dynamic from "next/dynamic";
import "@copilotkit/react-core/v2/styles.css";
import "./style.css";
import { CopilotChat } from "@copilotkit/react-core/v2";
import { CopilotKit, useCopilotChat } from "@copilotkit/react-core";
import { TextMessage, MessageRole } from "@copilotkit/runtime-client-gql";


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
      <div className="flex h-full w-full max-w-5xl flex-col p-4 gap-3">
        <GroupedSuggestions />
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
