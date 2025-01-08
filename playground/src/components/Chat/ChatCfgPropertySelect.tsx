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
  useAppSelector,
} from "@/common"
import { cn } from "@/lib/utils"
import { SettingsIcon, LoaderCircleIcon, BoxesIcon, Trash2Icon } from "lucide-react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { toast } from "sonner"
import { useGraphs } from "@/common/hooks"
import { AddonDef, Graph } from "@/common/graph"

export function RemotePropertyCfgSheet() {
  const dispatch = useAppDispatch()
  const { selectedGraph, update: updateGraph } = useGraphs()
  const graphName = useAppSelector((state) => state.global.selectedGraphId)

  const [selectedExtension, setSelectedExtension] = React.useState<string>("")
  const selectedExtensionNode = selectedGraph?.nodes.find(n => n.name === selectedExtension)
  const addonModules = useAppSelector((state) => state.global.addonModules)
  const selectedAddonModule = addonModules.find(
    (module) => module.name === selectedExtensionNode?.addon,
  )
  const hasProperty = !!selectedAddonModule?.api?.property && Object.keys(selectedAddonModule?.api?.property).length > 0

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
          <SheetTitle>Properties Setting</SheetTitle>
          <SheetDescription>
            You can adjust extension properties for selected graph here, the values will be
            written into property.json file when you save.
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
              {selectedGraph ? (selectedGraph.nodes).map((node) => (
                <SelectItem key={node.name} value={node.name}>
                  {node.name}
                </SelectItem>
              )) : null}
            </SelectContent>
          </Select>
        </div>

        {hasProperty ? selectedExtensionNode?.["property"] && (
          <GraphCfgForm
            selectedAddonModule={selectedAddonModule}
            selectedExtension={selectedExtension}
            key={`${graphName}-${selectedExtension}`}
            initialData={
              selectedExtensionNode?.["property"] || {}
            }
            metadata={
              addonModules.find(
                (module) => module.name === selectedExtensionNode?.addon,
              )?.api?.property || {}
            }
            onUpdate={async (data) => {
              // clone the overridenProperties
              const selectedGraphCopy: Graph = JSON.parse(JSON.stringify(selectedGraph))
              const nodes = selectedGraphCopy?.nodes || []
              let needUpdate = false
              for (const node of nodes) {
                if (node.name === selectedExtension) {
                  node.property = data
                  needUpdate = true
                }
              }
              if (needUpdate) {
                await updateGraph(selectedGraphCopy.id, selectedGraphCopy)
                toast.success("Properties updated", {
                  description: `Graph: ${graphName}, Extension: ${selectedExtension}`,
                })
              }
            }}
          />
        ) : (
          <SheetDescription>
            No properties found for the selected extension.
          </SheetDescription>
        )}
      </SheetContent>
    </Sheet>
  )
}



export function RemotePropertyAddCfgSheet({
  selectedExtension,
  extensionNodeData,
  onUpdate,
}: {
  selectedExtension: string,
  extensionNodeData: Record<string, string | number | boolean | null>,
  onUpdate: (data: string) => void
}) {
  const dispatch = useAppDispatch()
  const { selectedGraph } = useGraphs()

  const selectedExtensionNode = selectedGraph?.nodes.find(n => n.name === selectedExtension)
  const addonModules = useAppSelector((state) => state.global.addonModules)
  const selectedAddonModule = addonModules.find(
    (module) => module.name === selectedExtensionNode?.addon,
  )
  const allProperties = Object.keys(selectedAddonModule?.api?.property || {})
  const usedProperties = Object.keys(extensionNodeData)
  const remainingProperties = allProperties.filter(
    (prop) => !usedProperties.includes(prop),
  )
  const hasRemainingProperties = remainingProperties.length > 0

  const [selectedProperty, setSelectedProperty] = React.useState<string>("")
  const [isSheetOpen, setSheetOpen] = React.useState(false) // State to control the sheet

  return (
    <Sheet open={isSheetOpen} onOpenChange={setSheetOpen}>
      <SheetTrigger asChild
      >
        <div>
          <Button type="button" variant="secondary" onClick={() => { setSheetOpen(true) }}>Add</Button>
        </div>
      </SheetTrigger>
      <SheetContent className="w-[400px] overflow-y-auto sm:w-[540px]">
        <SheetHeader>
          <SheetTitle>Property Add</SheetTitle>
          <SheetDescription>
            You can add a property into a graph extension node and configure its value.
          </SheetDescription>
        </SheetHeader>
        {hasRemainingProperties ? (
          <>
            <Select
              onValueChange={(key) => {
                setSelectedProperty(key)
              }}
              value={selectedProperty}
            >
              <SelectTrigger className="w-full my-4">
                <SelectValue placeholder="Select a property" />
              </SelectTrigger>
              <SelectContent>
                {remainingProperties.map((item) => (
                  <SelectItem key={item} value={item}>
                    {item}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button type="submit" onClick={() => {
              setSheetOpen(false)
              if (selectedProperty !== "") {
                onUpdate(selectedProperty)
                setSelectedProperty("")
              }
            }}>Add</Button>
          </>
        ) : (
          <>
            <SheetDescription className="my-4">
              No remaining properties to add.
            </SheetDescription>
            <Button type="submit" onClick={() => {
              setSheetOpen(false)
            }}>OK</Button>
          </>
        )}

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
    case "float32":
      return parseFloat(value)
    case "bool":
      return value === true || value === "true"
    case "string":
      return String(value)
    default:
      return value
  }
}

const defaultTypeValue = (type: string) => {
  switch (type) {
    case "int64":
    case "int32":
      return 0
    case "float64":
      return 0.1
    case "bool":
      return false
    case "string":
    default:
      return ""
  }
}

import { useState } from "react"

const GraphCfgForm = ({
  selectedExtension,
  selectedAddonModule,
  initialData,
  metadata,
  onUpdate,
}: {
  selectedExtension: string,
  selectedAddonModule: AddonDef.Module | undefined,
  initialData: Record<string, string | number | boolean | null>
  metadata: Record<string, { type: string }>
  onUpdate: (data: Record<string, string | number | boolean | null>) => void
}) => {
  const formSchema = z.record(
    z.string(),
    z.union([z.string(), z.number(), z.boolean(), z.null()])
  )

  const [formData, setFormData] = useState(initialData)

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: formData,
  })

  const onSubmit = (data: z.infer<typeof formSchema>) => {
    const convertedData = Object.entries(data).reduce(
      (acc, [key, value]) => {
        const type = metadata[key]?.type || "string"
        acc[key] = value === "" ? defaultTypeValue(type) : convertToType(value, type)
        return acc
      },
      {} as Record<string, string | number | boolean | null>
    )
    onUpdate(convertedData)
  }

  const handleDelete = (key: string) => {
    const updatedData = { ...formData }
    delete updatedData[key] // Remove the specific key
    setFormData(updatedData) // Update state
    form.reset(updatedData) // Reset the form
  }

  const initialDataWithType = Object.entries(formData).reduce(
    (acc, [key, value]) => {
      acc[key] = { value, type: metadata[key]?.type || "string" }
      return acc
    },
    {} as Record<
      string,
      { value: string | number | boolean | null; type: string }
    >
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
                <div className="flex justify-between items-center">
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
                  <div
                    className={cn(
                      buttonVariants({ variant: "outline", size: "icon" }),
                      "bg-transparent",
                      "ml-2",
                      "cursor-pointer"
                    )}
                    onClick={() => handleDelete(key)} // Delete action
                  >
                    <Trash2Icon />
                  </div>
                </div>
              </FormItem>
            )}
          />
        ))}
        <div className="flex">
          <RemotePropertyAddCfgSheet
            selectedExtension={selectedExtension}
            extensionNodeData={formData}
            onUpdate={(key: string) => {
              let defaultProperty = selectedAddonModule?.defaultProperty || {}
              let defaultValue = defaultProperty[key]

              if (defaultValue === undefined) {
                let schema = selectedAddonModule?.api?.property || {}
                let schemaType = schema[key]?.type
                if (schemaType === "bool") {
                  defaultValue = false
                }
              }
              let updatedData = { ...formData }
              updatedData[key] = defaultValue
              setFormData(updatedData)
              form.reset(updatedData)
            }}
          />
          <Button
            className="mx-2"
            type="submit"
            disabled={form.formState.isSubmitting}
          >
            {form.formState.isSubmitting ? (
              <>
                <LoaderCircleIcon className="h-4 w-4 animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              "Save changes"
            )}
          </Button>
        </div>
      </form>
    </Form>
  )
}
