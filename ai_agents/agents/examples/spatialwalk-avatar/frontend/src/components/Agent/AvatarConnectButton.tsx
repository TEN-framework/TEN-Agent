"use client";

import { Loader2, Plug, PlugZap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAgentConnect } from "@/components/Layout/useAgentConnect";

export default function AvatarConnectButton(props: { className?: string }) {
  const { className } = props;
  const { loading, agentConnected, canConnect, onToggleConnect } =
    useAgentConnect();

  return (
    <Button
      onClick={onToggleConnect}
      variant={!agentConnected ? "default" : "destructive"}
      size="icon"
      disabled={!canConnect || loading}
      title={agentConnected ? "Disconnect" : "Connect"}
      className={cn(
        "h-10 w-10 rounded-full border border-white/20 bg-black/55 text-white hover:bg-black/70",
        className
      )}
    >
      {loading ? (
        <Loader2 className="h-5 w-5 animate-spin" />
      ) : agentConnected ? (
        <PlugZap className="h-5 w-5" />
      ) : (
        <Plug className="h-5 w-5" />
      )}
      <span className="sr-only">{agentConnected ? "Disconnect" : "Connect"}</span>
    </Button>
  );
}
