"use client";

import * as React from "react";
import { toast } from "sonner";
import {
  apiPing,
  apiStartService,
  apiStopService,
  getSpatialwalkUrlConfig,
  useAppDispatch,
  useAppSelector,
  validateSpatialwalkRequiredConfig,
} from "@/common";
import { setAgentConnected } from "@/store/reducers/global";

let intervalId: NodeJS.Timeout | null = null;

const startPing = (channel: string) => {
  if (intervalId) {
    clearInterval(intervalId);
  }
  intervalId = setInterval(() => {
    apiPing(channel);
  }, 3000);
};

const stopPing = () => {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
  }
};

export const useAgentConnect = () => {
  const dispatch = useAppDispatch();
  const agentConnected = useAppSelector((state) => state.global.agentConnected);
  const channel = useAppSelector((state) => state.global.options.channel);
  const userId = useAppSelector((state) => state.global.options.userId);
  const language = useAppSelector((state) => state.global.language);
  const voiceType = useAppSelector((state) => state.global.voiceType);
  const graphList = useAppSelector((state) => state.global.graphList);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (!channel) {
      return;
    }
    const checkAgentConnected = async () => {
      try {
        const res: any = await apiPing(channel);
        if (res?.code == 0) {
          dispatch(setAgentConnected(true));
          startPing(channel);
        } else {
          dispatch(setAgentConnected(false));
          stopPing();
        }
      } catch {
        dispatch(setAgentConnected(false));
        stopPing();
      }
    };
    checkAgentConnected();
  }, [channel, dispatch]);

  const onToggleConnect = async () => {
    if (loading || !channel) {
      return;
    }
    setLoading(true);

    try {
      if (agentConnected) {
        await apiStopService(channel);
        dispatch(setAgentConnected(false));
        toast.success("Agent disconnected");
        stopPing();
        return;
      }

      const graph = graphList[0];
      if (!graph) {
        toast.error("No graph available");
        return;
      }

      const spatialwalkUrlConfig = getSpatialwalkUrlConfig();
      const validation = validateSpatialwalkRequiredConfig(spatialwalkUrlConfig);
      if (!validation.isValid) {
        toast.error("Spatialwalk Settings", {
          description: validation.message,
        });
        return;
      }

      const res = await apiStartService({
        channel,
        userId,
        graphName: graph.name,
        language,
        voiceType,
        properties: {
          avatar: {
            spatialreal_avatar_id: spatialwalkUrlConfig.avatarId,
          },
        },
      });
      const { code, msg } = res || {};
      if (code != 0) {
        if (code == "10001") {
          toast.error(
            "The number of users experiencing the program simultaneously has exceeded the limit. Please try again later."
          );
        } else {
          toast.error(`code:${code},msg:${msg}`);
        }
        return;
      }

      dispatch(setAgentConnected(true));
      toast.success("Agent connected");
      startPing(channel);
    } finally {
      setLoading(false);
    }
  };

  return {
    loading,
    agentConnected,
    canConnect: Boolean(channel) && (graphList.length > 0 || agentConnected),
    connectLabel: loading
      ? "Connecting"
      : !agentConnected
        ? "Connect"
        : "Disconnect",
    onToggleConnect,
  };
};
