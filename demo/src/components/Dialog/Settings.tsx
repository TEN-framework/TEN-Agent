"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { SettingsIcon, RotateCcwIcon } from "lucide-react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { toast } from "sonner"
import { useAppDispatch, useAppSelector } from "@/common"
import {
  setAgentSettings,
  setCozeSettings,
  resetCozeSettings,
} from "@/store/reducers/global"

const TABS_OPTIONS = [
  {
    label: "Agent",
    value: "agent",
  },
  {
    label: "Coze",
    value: "coze",
  },
]

export const useSettingsTabs = () => {
  const [tabs, setTabs] = React.useState(TABS_OPTIONS)

  const graphName = useAppSelector((state) => state.global.graphName)

  const enableCozeSettingsMemo = React.useMemo(() => {
    return isCozeGraph(graphName)
  }, [graphName])

  React.useEffect(() => {
    if (enableCozeSettingsMemo) {
      setTabs((prev) =>
        prev.find((tab) => tab.value === "coze")
          ? prev
          : [...prev, { label: "Coze", value: "coze" }],
      )
    } else {
      setTabs((prev) => prev.filter((tab) => tab.value !== "coze"))
    }
  }, [enableCozeSettingsMemo])

  return tabs
}

export default function SettingsDialog() {
  const [open, setOpen] = React.useState(false)

  const tabs = useSettingsTabs()

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="w-9">
          <SettingsIcon />
        </Button>
      </DialogTrigger>
      <DialogContent className="w-fit">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
        </DialogHeader>
        <Tabs
          defaultValue={TABS_OPTIONS[0].value}
          className="w-full min-w-96 max-w-screen-sm"
        >
          {tabs.length > 1 && (
            <TabsList className="w-full">
              {tabs.map((tab) => (
                <TabsTrigger
                  key={tab.value}
                  className="w-full"
                  value={tab.value}
                >
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          )}
          <TabsContent value="agent">
            <CommonAgentSettingsTab
              handleClose={() => setOpen(false)}
              handleSubmit={() => setOpen(false)}
            />
          </TabsContent>
          <TabsContent value="coze">
            <CozeSettingsTab
              handleClose={() => setOpen(false)}
              handleSubmit={() => setOpen(false)}
            />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}

const formSchema = z.object({
  greeting: z.string().optional(),
  prompt: z.string().optional(),
})

export function CommonAgentSettingsTab(props: {
  handleClose?: () => void
  handleSubmit?: (values: z.infer<typeof formSchema>) => void
}) {
  const { handleSubmit } = props

  const dispatch = useAppDispatch()
  const agentSettings = useAppSelector((state) => state.global.agentSettings)

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      greeting: agentSettings.greeting,
      prompt: agentSettings.prompt,
    },
  })

  function onSubmit(values: z.infer<typeof formSchema>) {
    console.log("Form Values:", values)
    dispatch(setAgentSettings(values))
    handleSubmit?.(values)
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
        <FormField
          control={form.control}
          name="greeting"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Greeting</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Enter the greeting, leave it blank if you want to use default one."
                  className="resize-none"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="prompt"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Prompt</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Enter the prompt, leave it blank if you want to use default one."
                  className="resize-none"
                  rows={4}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <DialogFooter>
          <Button type="submit" disabled={!form.formState.isValid}>
            Save Agent Settings
          </Button>
        </DialogFooter>
      </form>
    </Form>
  )
}

export const cozeSettingsFormSchema = z.object({
  token: z
    .string({
      message: "Token is required",
    })
    .min(1),
  bot_id: z
    .string({
      message: "Bot ID is required",
    })
    .min(1),
  base_url: z.enum(["api.coze.cn", "api.coze.com"]).default("api.coze.cn"),
})

export const isCozeGraph = (graphName: string) => {
  return graphName.toLowerCase().includes("coze")
}

export function CozeSettingsTab(props: {
  handleClose?: () => void
  handleSubmit?: (values: z.infer<typeof cozeSettingsFormSchema>) => void
}) {
  const { handleSubmit } = props

  const dispatch = useAppDispatch()
  const cozeSettings = useAppSelector((state) => state.global.cozeSettings)

  const form = useForm<z.infer<typeof cozeSettingsFormSchema>>({
    resolver: zodResolver(cozeSettingsFormSchema),
    defaultValues: {
      token: cozeSettings.token,
      bot_id: cozeSettings.bot_id,
      base_url: cozeSettings.base_url as z.infer<
        typeof cozeSettingsFormSchema
      >["base_url"],
    },
  })

  function onSubmit(values: z.infer<typeof cozeSettingsFormSchema>) {
    console.log("Coze Form Values:", values)
    dispatch(setCozeSettings(values))
    handleSubmit?.(values)
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
        <FormField
          control={form.control}
          name="bot_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Bot ID*</FormLabel>
              <FormControl>
                <Input placeholder="Enter your Coze bot ID" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="token"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Token*</FormLabel>
              <FormControl>
                <Input placeholder="Enter your Coze API token" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="base_url"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Base URL*</FormLabel>
              <FormControl>
                <Select {...field} onValueChange={field.onChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select base URL" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="api.coze.com">
                      https://api.coze.com
                    </SelectItem>
                    <SelectItem value="api.coze.cn">
                      https://api.coze.cn
                    </SelectItem>
                  </SelectContent>
                </Select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <DialogFooter>
          <Button
            variant="destructive"
            size="icon"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              form.reset({
                token: "",
                bot_id: "",
                base_url: "api.coze.cn",
              })
              dispatch(resetCozeSettings())
              toast.success("Coze settings reset")
            }}
          >
            <RotateCcwIcon />
          </Button>
          <Button type="submit" disabled={!form.formState.isValid}>
            Save Coze Settings
          </Button>
        </DialogFooter>
      </form>
    </Form>
  )
}
