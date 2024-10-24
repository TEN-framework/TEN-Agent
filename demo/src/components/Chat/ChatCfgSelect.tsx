"use client"

import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  useAppDispatch,
  LANGUAGE_OPTIONS,
  useAppSelector,
  GRAPH_OPTIONS,
} from "@/common"
import type { Language } from "@/types"
import { setGraphName, setLanguage } from "@/store/reducers/global"

export function GraphSelect() {
  const dispatch = useAppDispatch()
  const graphName = useAppSelector((state) => state.global.graphName)
  const onGraphNameChange = (val: string) => {
    dispatch(setGraphName(val))
  }

  return (
    <>
      <Select value={graphName} onValueChange={onGraphNameChange}>
        <SelectTrigger className="w-fit">
          <SelectValue placeholder="Graph" />
        </SelectTrigger>
        <SelectContent>
          {GRAPH_OPTIONS.map((item) => {
            return (
              <SelectItem value={item.value} key={item.value}>
                {item.label}
              </SelectItem>
            )
          })}
        </SelectContent>
      </Select>
    </>
  )
}

export function LanguageSelect() {
  const dispatch = useAppDispatch()
  const language = useAppSelector((state) => state.global.language)

  const onLanguageChange = (val: Language) => {
    dispatch(setLanguage(val))
  }

  return (
    <>
      <Select value={language} onValueChange={onLanguageChange}>
        <SelectTrigger className="w-32">
          <SelectValue placeholder="Language" />
        </SelectTrigger>
        <SelectContent>
          {LANGUAGE_OPTIONS.map((item) => {
            return (
              <SelectItem value={item.value} key={item.value}>
                {item.label}
              </SelectItem>
            )
          })}
        </SelectContent>
      </Select>
    </>
  )
}
