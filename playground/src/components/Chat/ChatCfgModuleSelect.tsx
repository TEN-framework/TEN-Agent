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
import { AddonDef, Graph, useGraphManager } from "@/common/graph"
import { toast } from "sonner"
import { BoxesIcon, LoaderCircleIcon } from "lucide-react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"

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
                        onUpdate={async (data) => {
                            // clone the overriddenAddons
                            const selectedGraphCopy: Graph = JSON.parse(JSON.stringify(selectedGraph));
                            const nodes = selectedGraphCopy?.nodes || [];
                            let needUpdate = false;

                            Object.entries(data).forEach(([key, value]) => {
                                const node = nodes.find((n) => n.name === key);
                                if (node && value && node.addon !== value) {
                                    node.addon = value;
                                    node.property = addonModules.find((module) => module.name === value)?.defaultProperty;
                                    needUpdate = true;
                                }
                            });

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
    onUpdate: (data: Record<string, string | null>) => void;
}) => {
    const formSchema = z.record(z.string(), z.string().nullable());

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: initialData,
    });

    const onSubmit = (data: z.infer<typeof formSchema>) => {
        onUpdate(data);
    };

    // Custom labels for specific keys
    const fieldLabels: Record<string, string> = {
        stt: "STT (Speech to Text)",
        llm: "LLM (Large Language Model)",
        tts: "TTS (Text to Speech)",
        v2v: "LLM v2v (Voice to Voice Large Language Model)",
    };


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
                                            <FormLabel>{fieldLabels[key]}</FormLabel>
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
