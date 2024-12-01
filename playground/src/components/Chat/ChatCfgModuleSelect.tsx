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
import { useAppDispatch, useAppSelector } from "@/common/hooks"
import { AddonDef, Graph, useGraphManager, Destination } from "@/common/graph"
import { toast } from "sonner"
import { BoxesIcon, ChevronRightIcon, LoaderCircleIcon, SettingsIcon, Trash2Icon } from "lucide-react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuSub, DropdownMenuSubContent, DropdownMenuSubTrigger, DropdownMenuTrigger } from "../ui/dropdown"

export function RemoteModuleCfgSheet() {
    const addonModules = useAppSelector((state) => state.global.addonModules);
    const { getGraphNodeAddonByName, selectedGraph, update: updateGraph } = useGraphManager();

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
                            const nodes = selectedGraphCopy?.nodes || [];
                            const connections = selectedGraphCopy?.connections || [];
                            let needUpdate = false;

                            // Retrieve current tools in the graph
                            const toolModules = addonModules.filter((module) => module.name.includes("tool"));
                            const currentToolsInGraph = nodes
                                .filter((node) => toolModules.map((module) => module.name).includes(node.addon))
                                .map((node) => node.addon);

                            // Retrieve the app value from the agora_rtc node
                            const agoraRtcNode = nodes.find((node) => node.name === "agora_rtc");

                            if (!agoraRtcNode) {
                                toast.error("agora_rtc node not found in the graph");
                                return;
                            }

                            const agoraApp = agoraRtcNode?.app || "localhost";

                            // Identify removed tools
                            const removedTools = currentToolsInGraph.filter((tool) => !tools.includes(tool));

                            removedTools.forEach((tool) => {
                                // Remove the tool node
                                const toolNodeIndex = nodes.findIndex((node) => node.addon === tool);
                                if (toolNodeIndex !== -1) {
                                    nodes.splice(toolNodeIndex, 1);
                                    needUpdate = true;
                                }
                            
                                // Remove connections involving the tool
                                connections.forEach((connection, connIndex) => {
                                    // If the connection extension matches the tool, remove the entire connection
                                    if (connection.extension === tool) {
                                        connections.splice(connIndex, 1);
                                        needUpdate = true;
                                        return; // Skip further processing for this connection
                                    }
                            
                                    // Remove tool from cmd, data, audioFrame, and videoFrame destinations
                                    const removeEmptyDestObjects = (array: Array<{ name: string; dest: Array<Destination> }> | undefined) => {
                                        if (!array) return;
                            
                                        array.forEach((object, objIndex) => {
                                            object.dest = object.dest.filter((dest) => dest.extension !== tool);
                            
                                            // If `dest` is empty, remove the object
                                            if (object.dest.length === 0) {
                                                array.splice(objIndex, 1);
                                                needUpdate = true;
                                            }
                                        });
                                    };
                            
                                    // Clean up cmd, data, audioFrame, and videoFrame
                                    removeEmptyDestObjects(connection.cmd);
                                    removeEmptyDestObjects(connection.data);
                                    removeEmptyDestObjects(connection.audioFrame);
                                    removeEmptyDestObjects(connection.videoFrame);
                            
                                    // Remove the entire connection if it has no `cmd`, `data`, `audioFrame`, or `videoFrame`
                                    if (
                                        (!connection.cmd || connection.cmd.length === 0) &&
                                        (!connection.data || connection.data.length === 0) &&
                                        (!connection.audioFrame || connection.audioFrame.length === 0) &&
                                        (!connection.videoFrame || connection.videoFrame.length === 0)
                                    ) {
                                        connections.splice(connIndex, 1);
                                        needUpdate = true;
                                    }
                                });
                            });
                            
                            // Process tool modules
                            if (tools.length > 0) {
                                if (tools.some((tool) => tool.includes("vision"))) {
                                    agoraRtcNode.property = {
                                        ...agoraRtcNode.property,
                                        subscribe_video_pix_fmt: 4,
                                        subscribe_video: true,
                                    }
                                    needUpdate = true;
                                } else {
                                    delete agoraRtcNode.property?.subscribe_video_pix_fmt;
                                    delete agoraRtcNode.property?.subscribe_video;
                                }

                                tools.forEach((tool) => {
                                    if (!currentToolsInGraph.includes(tool)) {
                                        // 1. Remove existing node for the tool if it exists
                                        const existingNodeIndex = nodes.findIndex((node) => node.name === tool);
                                        if (existingNodeIndex >= 0) {
                                            nodes.splice(existingNodeIndex, 1);
                                        }

                                        // Add new node for the tool
                                        const toolModule = addonModules.find((module) => module.name === tool);
                                        if (toolModule) {
                                            nodes.push({
                                                app: agoraApp,
                                                name: tool,
                                                addon: tool,
                                                extensionGroup: "default",
                                                property: toolModule.defaultProperty,
                                            });
                                            needUpdate = true;
                                        }

                                        // 2. Find or create a connection for node name "llm" with cmd dest "tool_call"
                                        let llmConnection = connections.find(
                                            (connection) => connection.extension === "llm"
                                        );

                                        // Retrieve the extensionGroup dynamically from the graph
                                        const llmNode = nodes.find((node) => node.name === "llm");
                                        const llmExtensionGroup = llmNode?.extensionGroup || "default";

                                        if (llmConnection) {
                                            // If the connection exists, ensure it has a cmd array
                                            if (!llmConnection.cmd) {
                                                llmConnection.cmd = [];
                                            }

                                            // Find the tool_call command
                                            let toolCallCommand = llmConnection.cmd.find((cmd) => cmd.name === "tool_call");

                                            if (!toolCallCommand) {
                                                // If tool_call command doesn't exist, create it
                                                toolCallCommand = {
                                                    name: "tool_call",
                                                    dest: [],
                                                };
                                                llmConnection.cmd.push(toolCallCommand);
                                                needUpdate = true;
                                            }

                                            // Add the tool to the dest array if not already present
                                            if (!toolCallCommand.dest.some((dest) => dest.extension === tool)) {
                                                toolCallCommand.dest.push({
                                                    app: agoraApp,
                                                    extensionGroup: "default",
                                                    extension: tool,
                                                });
                                                needUpdate = true;
                                            }
                                        } else {
                                            // If llmConnection doesn't exist, create it with the tool_call command
                                            connections.push({
                                                app: agoraApp,
                                                extensionGroup: llmExtensionGroup,
                                                extension: "llm",
                                                cmd: [
                                                    {
                                                        name: "tool_call",
                                                        dest: [
                                                            {
                                                                app: agoraApp,
                                                                extensionGroup: "default",
                                                                extension: tool,
                                                            },
                                                        ],
                                                    },
                                                ],
                                            });
                                            needUpdate = true;
                                        }


                                        // 3. Create a connection for the tool node with cmd dest "tool_register"
                                        connections.push({
                                            app: agoraApp,
                                            extensionGroup: "default",
                                            extension: tool,
                                            cmd: [
                                                {
                                                    name: "tool_register",
                                                    dest: [
                                                        {
                                                            app: agoraApp,
                                                            extensionGroup: llmExtensionGroup,
                                                            extension: "llm",
                                                        },
                                                    ],
                                                },
                                            ],
                                        });
                                        needUpdate = true;

                                        // Create videoFrame connection for tools with "visual" in the name
                                        if (tool.includes("vision")) {
                                            const rtcConnection = connections.find(
                                                (connection) =>
                                                    connection.extension === "agora_rtc"
                                            );

                                            if (rtcConnection) {
                                                if (!rtcConnection?.videoFrame) {
                                                    rtcConnection.videoFrame = []
                                                }

                                                if (!rtcConnection.videoFrame.some((frame) => frame.name === "video_frame")) {
                                                    rtcConnection.videoFrame.push({
                                                        name: "video_frame",
                                                        dest: [
                                                            {
                                                                app: agoraApp,
                                                                extensionGroup: "default",
                                                                extension: tool,
                                                            },
                                                        ],
                                                    });
                                                    needUpdate = true;
                                                } else if (!rtcConnection.videoFrame.some((frame) => frame.dest.some((dest) => dest.extension === tool))) {
                                                    rtcConnection.videoFrame.find((frame) => frame.name === "video_frame")?.dest.push({
                                                        app: agoraApp,
                                                        extensionGroup: "default",
                                                        extension: tool,
                                                    });
                                                    needUpdate = true;
                                                }
                                            }
                                        }
                                    }
                                });
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
    const addonModules = useAppSelector((state) => state.global.addonModules);
    const { selectedGraph } = useGraphManager();

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
        v2v: "LLM v2v (Voice to Voice Large Language Model)",
    };

    // Extract tool modules from addonModules
    const toolModules = React.useMemo(
        () => addonModules.filter((module) => module.name.includes("tool")),
        [addonModules]
    );

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
                                                    {(key === "llm" || key === "v2v") && (
                                                        <DropdownMenu>
                                                            <DropdownMenuTrigger className={cn(
                                                                buttonVariants({ variant: "outline", size: "icon" }),
                                                                "bg-transparent",
                                                            )}><SettingsIcon />
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
                                {key === "llm" && selectedTools.length > 0 && (
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
