import {
  CopilotRuntime,
  ExperimentalEmptyAdapter, // Use this for AG-UI agents
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";

export const POST = async (req: NextRequest) => {
  const agentUrl = process.env.AGENT_URL ?? "http://127.0.0.1:8000/";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mkAgent = (url: string) => new HttpAgent({ url }) as any;
  const runtime = new CopilotRuntime({
    agents: {
      "root_agent": mkAgent(agentUrl),
    },
  });

  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    // We use ExperimentalEmptyAdapter because the Python agent 
    // already has its own model (Gemini) and adapter.
    serviceAdapter: new ExperimentalEmptyAdapter(),
    endpoint: req.nextUrl.pathname,
  });

  return handleRequest(req);
};