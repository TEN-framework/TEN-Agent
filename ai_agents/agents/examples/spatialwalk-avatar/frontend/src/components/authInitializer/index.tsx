"use client";

import { type ReactNode, useEffect, useRef } from "react";
import { toast } from "sonner";
import {
  getSpatialwalkUrlConfig,
  getOptionsFromLocal,
  getRandomChannel,
  getRandomUserId,
  getSpatialwalkSettingsFromLocal,
  useAppDispatch,
  useAppSelector,
  validateSpatialwalkRequiredConfig,
} from "@/common";
import { useGraphs } from "@/common/hooks";
import {
  fetchGraphDetails,
  reset,
  setOptions,
  setSelectedGraphId,
  setSpatialwalkSettings,
} from "@/store/reducers/global";

interface AuthInitializerProps {
  children: ReactNode;
}

const AuthInitializer = (props: AuthInitializerProps) => {
  const { children } = props;
  const dispatch = useAppDispatch();
  const { initialize } = useGraphs();
  const selectedGraphId = useAppSelector(
    (state) => state.global.selectedGraphId
  );
  const graphList = useAppSelector((state) => state.global.graphList);
  const spatialwalkWarningShown = useRef(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const options = getOptionsFromLocal();
      const spatialwalkSettings = getSpatialwalkSettingsFromLocal();
      const validation = validateSpatialwalkRequiredConfig(
        getSpatialwalkUrlConfig()
      );
      initialize();
      if (options && options.channel) {
        dispatch(reset());
        dispatch(setOptions(options));
        dispatch(setSpatialwalkSettings(spatialwalkSettings));
      } else {
        dispatch(reset());
        dispatch(
          setOptions({
            channel: getRandomChannel(),
            userId: getRandomUserId(),
          })
        );
        dispatch(setSpatialwalkSettings(spatialwalkSettings));
      }
      if (!spatialwalkWarningShown.current && !validation.isValid) {
        spatialwalkWarningShown.current = true;
        toast.error("Spatialwalk Settings", {
          description: validation.message,
        });
      }
    }
  }, [dispatch]);

  // Auto-select the only/default graph.
  useEffect(() => {
    if (graphList.length > 0) {
      const defaultGraph = graphList[0];
      const defaultGraphId = defaultGraph.graph_id || defaultGraph.name;
      if (selectedGraphId !== defaultGraphId) {
        dispatch(setSelectedGraphId(defaultGraphId));
      }
    }
  }, [graphList, selectedGraphId, dispatch]);

  useEffect(() => {
    if (selectedGraphId) {
      const graph = graphList.find((g) => g.graph_id === selectedGraphId);
      if (!graph) {
        return;
      }
      dispatch(fetchGraphDetails(graph));
    }
  }, [selectedGraphId, graphList, dispatch]); // Automatically fetch details when `selectedGraphId` changes

  return children;
};

export default AuthInitializer;
