import * as React from "react";
import { useIsCompactLayout } from "@/common";
import { useAppDispatch, useAppSelector } from "@/common/hooks";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { setSelectedGraphId } from "@/store/reducers/global";

export function RemoteGraphSelect() {
  const dispatch = useAppDispatch();
  const graphName = useAppSelector((state) => state.global.selectedGraphId);
  const graphs = useAppSelector((state) => state.global.graphList);
  const agentConnected = useAppSelector((state) => state.global.agentConnected);

  const onGraphNameChange = (val: string) => {
    dispatch(setSelectedGraphId(val));
  };

  const graphOptions = graphs.map((item) => ({
    label: item.name,
    value: item.graph_id,
  }));

  // Get the selected graph's label for display
  const selectedGraph = graphs.find((g) => g.graph_id === graphName);
  const displayLabel = selectedGraph?.name || "Select Graph";

  // Truncate label for display when closed (max 20 chars on mobile, 25 on desktop)
  const truncatedLabel = displayLabel.length > 20
    ? displayLabel.substring(0, 17) + "..."
    : displayLabel;

  return (
    <>
      <Select
        value={graphName}
        onValueChange={onGraphNameChange}
        disabled={agentConnected}
      >
        <SelectTrigger
          className={cn(
            "w-auto max-w-[180px] md:max-w-[220px]"
          )}
        >
          <SelectValue placeholder={"Select Graph"}>
            <span className="truncate">{truncatedLabel}</span>
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {graphOptions.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </>
  );
}
