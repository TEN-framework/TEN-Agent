"use client"

import * as React from "react"
import { buttonVariants } from "@/components/ui/button"
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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  SheetFooter,
  SheetClose,
} from "@/components/ui/sheet"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  useAppDispatch,
  LANGUAGE_OPTIONS,
  useAppSelector,
  GRAPH_OPTIONS,
  useGraphExtensions,
} from "@/common"
import type { Language } from "@/types"
import {
  setGraphName,
  setLanguage,
  setOverridenPropertiesByGraph,
} from "@/store/reducers/global"
import { cn } from "@/lib/utils"
import { SettingsIcon, LoaderCircleIcon } from "lucide-react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { toast } from "sonner"

export function RemoteGraphSelect() {
  const dispatch = useAppDispatch()
  const graphName = useAppSelector((state) => state.global.graphName)
  const graphs = useAppSelector((state) => state.global.graphs)
  const agentConnected = useAppSelector((state) => state.global.agentConnected)

  const onGraphNameChange = (val: string) => {
    dispatch(setGraphName(val))
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

export function RemoteGraphCfgSheet() {
  const dispatch = useAppDispatch()
  const graphExtensions = useGraphExtensions()
  const graphName = useAppSelector((state) => state.global.graphName)
  const extensionMetadata = useAppSelector(
    (state) => state.global.extensionMetadata,
  )
  const overridenProperties = useAppSelector(
    (state) => state.global.overridenProperties,
  )

  const [selectedExtension, setSelectedExtension] = React.useState<string>("")

  return (
    <Sheet>
      <SheetTrigger
        className={cn(
          buttonVariants({ variant: "outline", size: "icon" }),
          "bg-transparent",
        )}
      >
        <SettingsIcon />
      </SheetTrigger>
      <SheetContent className="w-[400px] overflow-y-auto sm:w-[540px]">
        <SheetHeader>
          <SheetTitle>Properties Override</SheetTitle>
          <SheetDescription>
            You can adjust extension properties here, the values will be
            overridden when the agent starts using "Connect." Note that this
            won't modify the property.json file.
          </SheetDescription>
        </SheetHeader>

        <div className="my-4">
          <Label>Extension</Label>
          <Select
            onValueChange={setSelectedExtension}
            value={selectedExtension}
          >
            <SelectTrigger className="mt-2 w-full">
              <SelectValue placeholder="Select extension" />
            </SelectTrigger>
            <SelectContent>
              {Object.keys(graphExtensions).map((key) => (
                <SelectItem key={key} value={key}>
                  {key}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {graphExtensions?.[selectedExtension]?.["property"] && (
          <GraphCfgForm
            key={`${graphName}-${selectedExtension}`}
            initialData={
              graphExtensions?.[selectedExtension]?.["property"] || {}
            }
            metadata={
              extensionMetadata?.[
                graphExtensions?.[selectedExtension]?.["addon"]
              ]?.api?.property || {}
            }
            onUpdate={(data) => {
              // clone the overridenProperties
              let nodesMap = JSON.parse(
                JSON.stringify(overridenProperties[selectedExtension] || {}),
              )
              // Update initial data with any existing overridden values
              if (overridenProperties[selectedExtension]) {
                Object.assign(nodesMap, overridenProperties[selectedExtension])
              }
              nodesMap[selectedExtension] = data
              toast.success("Properties updated", {
                description: `Graph: ${graphName}, Extension: ${selectedExtension}`,
              })
              dispatch(
                setOverridenPropertiesByGraph({
                  graphName,
                  nodesMap,
                }),
              )
            }}
          />
        )}

        {/* <SheetFooter>
          <SheetClose asChild>
            <Button type="submit">Save changes</Button>
          </SheetClose>
        </SheetFooter> */}
      </SheetContent>
    </Sheet>
  )
}

// Helper to convert values based on type
const convertToType = (value: any, type: string) => {
  switch (type) {
    case "int64":
    case "int32":
      return parseInt(value, 10)
    case "float64":
      return parseFloat(value)
    case "bool":
      return value === true || value === "true"
    case "string":
      return String(value)
    default:
      return value
  }
}

const GraphCfgForm = ({
  initialData,
  metadata,
  onUpdate,
}: {
  initialData: Record<string, string | number | boolean | null>
  metadata: Record<string, { type: string }>
  onUpdate: (data: Record<string, string | number | boolean | null>) => void
}) => {
  const formSchema = z.record(
    z.string(),
    z.union([z.string(), z.number(), z.boolean(), z.null()]),
  )

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: initialData,
  })

  const onSubmit = (data: z.infer<typeof formSchema>) => {
    const convertedData = Object.entries(data).reduce(
      (acc, [key, value]) => {
        const type = metadata[key]?.type || "string"
        acc[key] = value === "" ? null : convertToType(value, type)
        return acc
      },
      {} as Record<string, string | number | boolean | null>,
    )
    onUpdate(convertedData)
  }

  const initialDataWithType = Object.entries(initialData).reduce(
    (acc, [key, value]) => {
      acc[key] = { value, type: metadata[key]?.type || "string" }
      return acc
    },
    {} as Record<
      string,
      { value: string | number | boolean | null; type: string }
    >,
  )

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {Object.entries(initialDataWithType).map(([key, { value, type }]) => (
          <FormField
            key={key}
            control={form.control}
            name={key}
            render={({ field }) => (
              <FormItem>
                <FormLabel>{key}</FormLabel>
                <FormControl>
                  {type === "bool" ? (
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={field.value === true}
                        onCheckedChange={field.onChange}
                      />
                    </div>
                  ) : (
                    <Input
                      {...field}
                      value={
                        field.value === null || field.value === undefined
                          ? ""
                          : field.value.toString()
                      }
                      type={type === "string" ? "text" : "number"}
                    />
                  )}
                </FormControl>
              </FormItem>
            )}
          />
        ))}
        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? (
            <>
              <LoaderCircleIcon className="h-4 w-4 animate-spin" />
              <span>Saving...</span>
            </>
          ) : (
            "Save changes"
          )}
        </Button>
      </form>
    </Form>
  )
}
