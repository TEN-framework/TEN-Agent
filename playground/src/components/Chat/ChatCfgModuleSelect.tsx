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
import { useAppSelector, useGraphs } from "@/common/hooks"
import { AddonDef, Graph, Destination, GraphEditor, ProtocolLabel as GraphConnProtocol } from "@/common/graph"
import { toast } from "sonner"
import { BoxesIcon, ChevronRightIcon, LoaderCircleIcon, SettingsIcon, Trash2Icon, WrenchIcon } from "lucide-react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger, DropdownMenuTrigger } from "../ui/dropdown"
import { isLLM } from "@/common"

export function RemoteModuleCfgSheet() {
    const addonModules = useAppSelector((state) => state.global.addonModules);
    const { getGraphNodeAddonByName, selectedGraph, update: updateGraph } = useGraphs();

    const moduleMapping: Record<string, string[]> = {
        stt: [],
        llm: ["openai_chatgpt_python"],
        v2v: [],
        tts: [],
    };

    // Define the exclusion map for modules
    const exclusionMapping: Record<string, string[]> = {
        stt: [],
        llm: ["qwen_llm_python"],
        v2v: ["minimax_v2v_python"],
        tts: [],
    };

    const modules = React.useMemo(() => {
        const result: Record<string, string[]> = {};

        addonModules.forEach((module) => {
            const matchingNode = selectedGraph?.nodes.find((node) =>
                ["stt", "tts", "llm", "v2v"].some((type) =>
                    node.name === type &&
                    (module.name.includes(type) ||
                        (type === "stt" && module.name.includes("asr")) ||
                        (moduleMapping[type]?.includes(module.name)))
                )
            );

            if (
                matchingNode &&
                !exclusionMapping[matchingNode.name]?.includes(module.name)
            ) {
                if (!result[matchingNode.name]) {
                    result[matchingNode.name] = [];
                }
                result[matchingNode.name].push(module.name);
            }
        });

        return result;
    }, [addonModules, selectedGraph]);

    const { toolModules } = useGraphs();

    const metadata = React.useMemo(() => {
        const dynamicMetadata: Record<string, { type: string; options: string[] }> = {};

        Object.keys(modules).forEach((key) => {
            dynamicMetadata[key] = { type: "string", options: modules[key] };
        });

        return dynamicMetadata;
    }, [modules]);

    const initialData = React.useMemo(() => {
        const dynamicInitialData: Record<string, string | null | undefined> = {};

        Object.keys(modules).forEach((key) => {
            dynamicInitialData[key] = getGraphNodeAddonByName(key)?.addon;
        });

        return dynamicInitialData;
    }, [modules, getGraphNodeAddonByName]);

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

                            // Retrieve the agora_rtc node
                            const agoraRtcNode = GraphEditor.findNode(selectedGraphCopy, "agora_rtc");
                            if (!agoraRtcNode) {
                                toast.error("agora_rtc node not found in the graph");
                                return;
                            }

                            // Identify removed tools and process them
                            const currentToolsInGraph = nodes
                                .filter((node) => toolModules.map((module) => module.name).includes(node.addon))
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


                            // Update graph nodes with selected modules
                            Object.entries(data).forEach(([key, value]) => {
                                const node = nodes.find((n) => n.name === key);
                                if (node && value && node.addon !== value) {
                                    node.addon = value;
                                    node.property = addonModules.find((module) => module.name === value)?.defaultProperty;
                                    needUpdate = true;
                                }
                            });

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
    metadata: Record<string, { type: string; options: string[] }>;
    onUpdate: (data: Record<string, string | null>, tools: string[]) => void;
}) => {
    const formSchema = z.record(z.string(), z.string().nullable());
    const { selectedGraph, toolModules } = useGraphs();

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: initialData,
    });

    const onSubmit = (data: z.infer<typeof formSchema>) => {
        onUpdate(data, selectedTools);
    };


    // Custom labels for specific keys
    const fieldLabels: Record<string, string> = {
        stt: "STT (Speech to Text)",
        llm: "LLM (Large Language Model)",
        tts: "TTS (Text to Speech)",
        v2v: "LLM v2v (V2V Large Language Model)",
    };


    // Initialize selectedTools by extracting tool addons used in graph nodes
    const initialSelectedTools = React.useMemo(() => {
        const toolNames = toolModules.map((module) => module.name);
        return selectedGraph?.nodes
            .filter((node) => toolNames.includes(node.addon))
            .map((node) => node.addon) || [];
    }, [toolModules, selectedGraph]);

    const [selectedTools, setSelectedTools] = React.useState<string[]>(initialSelectedTools);

    // Desired field order
    const fieldOrder = ["stt", "llm", "v2v", "tts"];
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
                                                <div className="flex justify-between items-center justify-center ">
                                                    <div className="py-3">{fieldLabels[key]}</div>
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
                                                                            {toolModules.map((module) => (
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
                                                                            ))}
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
                                                            <SelectItem key={option} value={option}>
                                                                {option}
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
