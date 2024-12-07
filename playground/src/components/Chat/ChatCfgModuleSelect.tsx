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
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useAppSelector, useGraphs, } from "@/common/hooks"
import { AddonDef, Graph, Destination, GraphEditor, ProtocolLabel as GraphConnProtocol } from "@/common/graph"
import { toast } from "sonner"
import { BoxesIcon, ChevronRightIcon, LoaderCircleIcon, SettingsIcon, Trash2Icon, WrenchIcon } from "lucide-react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger, DropdownMenuTrigger } from "../ui/dropdown"
import { isLLM } from "@/common"
import { compatibleTools, ModuleRegistry, ModuleTypeLabels } from "@/common/moduleConfig"

export function RemoteModuleCfgSheet() {
    const addonModules = useAppSelector((state) => state.global.addonModules);
    const { getGraphNodeAddonByName, selectedGraph, update: updateGraph, installedAndRegisteredModulesMap, installedAndRegisteredToolModules } = useGraphs();

    const metadata = React.useMemo(() => {
        const dynamicMetadata: Record<string, { type: string; options: { value: string; label: string }[] }> = {};

        if (selectedGraph) {
            Object.keys(installedAndRegisteredModulesMap).forEach((key) => {
                const moduleTypeKey = key as ModuleRegistry.ModuleType;

                // Check if the current graph has a node whose name contains the ModuleType
                const hasMatchingNode = selectedGraph.nodes.some((node) =>
                    node.name.includes(moduleTypeKey)
                );

                if (hasMatchingNode) {
                    dynamicMetadata[moduleTypeKey] = {
                        type: "string",
                        options: installedAndRegisteredModulesMap[moduleTypeKey].map((module) => ({
                            value: module.name,
                            label: module.label,
                        })),
                    };
                }
            });
        }

        return dynamicMetadata;
    }, [installedAndRegisteredModulesMap, selectedGraph]);

    const initialData = React.useMemo(() => {
        const dynamicInitialData: Record<string, string | null | undefined> = {};

        if (selectedGraph) {
            Object.keys(installedAndRegisteredModulesMap).forEach((key) => {
                const moduleTypeKey = key as ModuleRegistry.ModuleType;

                // Check if the current graph has a node whose name contains the ModuleType
                const hasMatchingNode = selectedGraph.nodes.some((node) =>
                    node.name.includes(moduleTypeKey)
                );

                if (hasMatchingNode) {
                    dynamicInitialData[moduleTypeKey] = getGraphNodeAddonByName(moduleTypeKey)?.addon;
                }
            });
        }

        return dynamicInitialData;
    }, [installedAndRegisteredModulesMap, selectedGraph, getGraphNodeAddonByName]);


    return (
        <Sheet>
            <SheetTrigger
                className={cn(
                    buttonVariants({ variant: "outline", size: "icon" }),
                    "bg-transparent"
                )}
            >
                <BoxesIcon />
            </SheetTrigger>
            <SheetContent className="w-[400px] overflow-y-auto sm:w-[540px]">
                <SheetHeader>
                    <SheetTitle>Module Picker</SheetTitle>
                    <SheetDescription>
                        You can adjust STT/TTS/LLM/LLMv2v extension modules here, the values will be
                        written into property.json file when you save.
                    </SheetDescription>
                </SheetHeader>

                <div className="my-4">
                    <GraphModuleCfgForm
                        initialData={initialData}
                        metadata={metadata}
                        onUpdate={async (data, tools) => {
                            // Clone the selectedGraph to avoid mutating the original graph
                            const selectedGraphCopy: Graph = JSON.parse(JSON.stringify(selectedGraph));
                            const nodes = selectedGraphCopy.nodes;
                            let needUpdate = false;


                            // Update graph nodes with selected modules
                            Object.entries(data).forEach(([key, value]) => {
                                const node = nodes.find((n) => n.name === key);
                                if (node && value && node.addon !== value) {
                                    node.addon = value;
                                    node.property = addonModules.find((module) => module.name === value)?.defaultProperty;
                                    needUpdate = true;
                                }
                            });

                            // Retrieve the agora_rtc node
                            const agoraRtcNode = GraphEditor.findNode(selectedGraphCopy, "agora_rtc");
                            if (!agoraRtcNode) {
                                toast.error("agora_rtc node not found in the graph");
                                return;
                            }

                            // Identify removed tools and process them
                            const currentToolsInGraph = nodes
                                .filter((node) => installedAndRegisteredToolModules.map((module) => module.name).includes(node.addon))
                                .map((node) => node.addon);

                            const removedTools = currentToolsInGraph.filter((tool) => !tools.includes(tool));
                            removedTools.forEach((tool) => {
                                GraphEditor.removeNodeAndConnections(selectedGraphCopy, tool);
                                needUpdate = true;
                            });

                            // Process tool modules
                            if (tools.length > 0) {
                                GraphEditor.enableRTCVideoSubscribe(selectedGraphCopy, tools.some((tool) => tool.includes("vision")));

                                tools.forEach((tool) => {
                                    if (!currentToolsInGraph.includes(tool)) {
                                        const toolModule = addonModules.find((module) => module.name === tool);

                                        if (!toolModule) {
                                            toast.error(`Module ${tool} not found`);
                                            return;
                                        }

                                        const toolNode = GraphEditor.addNode(selectedGraphCopy, tool, tool, "default", toolModule.defaultProperty)

                                        // Create or update connections
                                        const llmNode = GraphEditor.findNodeByPredicate(selectedGraphCopy, (node) => isLLM(node.name));
                                        if (llmNode) {
                                            GraphEditor.linkTool(selectedGraphCopy, llmNode, toolNode);
                                        }
                                    }
                                });
                                needUpdate = true;
                            }

                            // Perform the update if changes are detected
                            if (needUpdate) {
                                try {
                                    await updateGraph(selectedGraphCopy.id, selectedGraphCopy);
                                    toast.success("Modules updated", {
                                        description: `Graph: ${selectedGraphCopy.id}`,
                                    });
                                } catch (e) {
                                    toast.error("Failed to update modules");
                                }
                            }
                        }}

                    />
                </div>
            </SheetContent>
        </Sheet>
    );
}

const GraphModuleCfgForm = ({
    initialData,
    metadata,
    onUpdate,
}: {
    initialData: Record<string, string | null | undefined>;
    metadata: Record<string, { type: string; options: { value: string, label: string }[] }>;
    onUpdate: (data: Record<string, string | null>, tools: string[]) => void;
}) => {
    const formSchema = z.record(z.string(), z.string().nullable());
    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: initialData,
    });
    const { selectedGraph, installedAndRegisteredToolModules } = useGraphs();
    const { watch } = form;

    // Watch for changes in "llm" and "v2v" fields
    const llmValue = watch("llm");
    const v2vValue = watch("v2v");
    const toolModules = React.useMemo(() => {
        // Step 1: Get installed and registered tool modules
        const allToolModules = installedAndRegisteredToolModules || [];

        // Step 2: Determine the active module based on form values
        const activeModule = llmValue || v2vValue;

        // Step 3: Get compatible tools for the active module
        if (activeModule) {
            const compatibleToolNames = compatibleTools[activeModule] || [];
            return allToolModules.filter((module) => compatibleToolNames.includes(module.name));
        }

        // If no LLM or V2V module is selected, return all tool modules
        return [];
    }, [installedAndRegisteredToolModules, selectedGraph, llmValue, v2vValue]);


    const onSubmit = (data: z.infer<typeof formSchema>) => {
        onUpdate(data, selectedTools);
    };

    const [selectedTools, setSelectedTools] = React.useState<string[]>([]);

    // Synchronize selectedTools with selectedGraph and toolModules
    React.useEffect(() => {
        const toolNames = toolModules.map((module) => module.name);
        const graphToolAddons =
            selectedGraph?.nodes
                .filter((node) => toolNames.includes(node.addon))
                .map((node) => node.addon) || [];
        setSelectedTools(graphToolAddons);
    }, [toolModules, selectedGraph]);

    // Desired field order
    const fieldOrder: ModuleRegistry.ModuleType[] = ["stt", "llm", "v2v", "tts"];
    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                {fieldOrder.map(
                    (key) =>
                        metadata[key] && ( // Check if the field exists in metadata
                            <div key={key} className="space-y-2">
                                <FormField
                                    control={form.control}
                                    name={key}
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>
                                                <div className="flex items-center justify-center ">
                                                    <div className="py-3">{ModuleTypeLabels[key]}</div>
                                                    {isLLM(key) && (
                                                        <DropdownMenu>
                                                            <DropdownMenuTrigger className={cn(
                                                                buttonVariants({ variant: "outline", size: "icon" }),
                                                                "bg-transparent",
                                                            )}><WrenchIcon />
                                                            </DropdownMenuTrigger>
                                                            <DropdownMenuContent>
                                                                <DropdownMenuSub>
                                                                    <DropdownMenuSubTrigger icon={<ChevronRightIcon size={15} />} className="flex justify-between">
                                                                        Add Tools
                                                                    </DropdownMenuSubTrigger>
                                                                    <DropdownMenuPortal>
                                                                        <DropdownMenuSubContent
                                                                            className="DropdownMenuSubContent"
                                                                            sideOffset={2}
                                                                            alignOffset={-5}
                                                                        >
                                                                            {toolModules.length > 0 ? toolModules.map((module) => (
                                                                                <DropdownMenuItem
                                                                                    key={module.name}
                                                                                    disabled={selectedTools.includes(module.name)} // Disable if the tool is already selected
                                                                                    onClick={() => {
                                                                                        if (!selectedTools.includes(module.name)) {
                                                                                            setSelectedTools((prev) => [
                                                                                                ...prev,
                                                                                                module.name,
                                                                                            ]);
                                                                                        }
                                                                                    }}>
                                                                                    {module.name}
                                                                                </DropdownMenuItem>
                                                                            )) : (
                                                                                <DropdownMenuItem disabled>No compatible tools</DropdownMenuItem>
                                                                            )}
                                                                        </DropdownMenuSubContent>
                                                                    </DropdownMenuPortal>
                                                                </DropdownMenuSub>
                                                            </DropdownMenuContent>
                                                        </DropdownMenu>
                                                    )}
                                                </div>
                                            </FormLabel>
                                            <FormControl>
                                                <Select
                                                    value={field.value ?? ""}
                                                    onValueChange={field.onChange}
                                                >
                                                    <SelectTrigger>
                                                        <SelectValue placeholder={`Select a ${key.toUpperCase()} option`} />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {metadata[key].options.map((option) => (
                                                            <SelectItem key={option.value} value={option.value}>
                                                                {option.label}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </FormControl>
                                        </FormItem>
                                    )}
                                />
                                {isLLM(key) && selectedTools.length > 0 && (
                                    <div className="mt-2">
                                        {selectedTools.map((tool) => (
                                            <div
                                                key={tool}
                                                className="flex items-center justify-between py-2 px-3 rounded-md"
                                            >
                                                <span className="text-sm">{tool}</span>
                                                <div
                                                    className={cn(
                                                        buttonVariants({ variant: "outline", size: "icon" }),
                                                        "bg-transparent",
                                                        "ml-2",
                                                        "cursor-pointer"
                                                    )}
                                                    onClick={() => {
                                                        setSelectedTools((prev) => prev.filter((t) => t !== tool))
                                                    }} // Delete action
                                                >
                                                    <Trash2Icon />
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )
                )}

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
    );
};
