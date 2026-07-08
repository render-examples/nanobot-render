import { createContext, useContext, type ReactNode } from "react";

import type { NanobotClient } from "@/lib/nanobot-client";

interface ClientContextValue {
  client: NanobotClient;
  token: string;
  modelName: string | null;
  /** Hosted, unauthenticated, locked-down demo mode. */
  demo: boolean;
}

const ClientContext = createContext<ClientContextValue | null>(null);

export function ClientProvider({
  client,
  token,
  modelName = null,
  demo = false,
  children,
}: {
  client: NanobotClient;
  token: string;
  modelName?: string | null;
  demo?: boolean;
  children: ReactNode;
}) {
  return (
    <ClientContext.Provider value={{ client, token, modelName, demo }}>
      {children}
    </ClientContext.Provider>
  );
}

export function useClient(): ClientContextValue {
  const ctx = useContext(ClientContext);
  if (!ctx) {
    throw new Error("useClient must be used within a ClientProvider");
  }
  return ctx;
}
