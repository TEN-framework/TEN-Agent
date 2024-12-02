import * as React from "react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useAppDispatch, useAppSelector } from "@/common/hooks"
import {
  setSelectedGraphId,
} from "@/store/reducers/global"


export function RemoteGraphSelect() {
    const dispatch = useAppDispatch()
    const graphName = useAppSelector((state) => state.global.selectedGraphId)
    const graphs = useAppSelector((state) => state.global.graphList)
    const agentConnected = useAppSelector((state) => state.global.agentConnected)
  
    const onGraphNameChange = (val: string) => {
      dispatch(setSelectedGraphId(val))
    }
  
    const graphOptions = graphs.map((item) => ({
      label: item,
      value: item,
    }))
  
    return (
      <>
        <Select
          value={graphName}
          onValueChange={onGraphNameChange}
          disabled={agentConnected}
        >
          <SelectTrigger className="w-auto max-w-full">
            <SelectValue placeholder="Select Graph" />
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
    )
  }
  