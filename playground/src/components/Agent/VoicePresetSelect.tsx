"use client"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useAppSelector, useAppDispatch, VOICE_OPTIONS } from "@/common"
import { setVoiceType } from "@/store/reducers/global"
import type { VoiceType } from "@/types"
import { VoiceIcon } from "@/components/Icon"

export default function AgentVoicePresetSelect() {
  const dispatch = useAppDispatch()
  const options = useAppSelector((state) => state.global.options)
  const voiceType = useAppSelector((state) => state.global.voiceType)

  const onVoiceChange = (value: string) => {
    dispatch(setVoiceType(value as VoiceType))
  }

  return (
    <Select value={voiceType} onValueChange={onVoiceChange}>
      <SelectTrigger className="w-[180px]">
        <div className="inline-flex items-center gap-2">
          <SelectValue placeholder="Voice" />
        </div>
      </SelectTrigger>
      <SelectContent>
        {VOICE_OPTIONS.map((option) => (
          <SelectItem
            key={option.value}
            value={option.value}
            className="flex items-center gap-2"
          >
            <span className="flex items-center gap-2">
              <VoiceIcon className="h-4 w-4" />
              {option.label}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
