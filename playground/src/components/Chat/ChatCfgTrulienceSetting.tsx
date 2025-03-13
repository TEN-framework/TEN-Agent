import * as React from "react"
import { buttonVariants } from "@/components/ui/button"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
    SheetTrigger,
} from "@/components/ui/sheet"
import {
    Form,
    FormControl,
    FormField,
    FormItem,
    FormLabel,
} from "@/components/ui/form"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { LoaderCircleIcon, UsersIcon } from "lucide-react"
import { set, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Switch } from "../ui/switch"
import { useAppDispatch, useAppSelector } from "@/common/hooks"
import { Input } from "../ui/input"
import { setTrulienceSettings } from "@/store/reducers/global"
import { toast } from "sonner"

export function TrulienceCfgSheet() {
    const dispatch = useAppDispatch()
    const trulienceSettings = useAppSelector((state) => state.global.trulienceSettings)
    return (
        <Sheet>
            <SheetTrigger
                className={cn(
                    buttonVariants({ variant: "outline", size: "icon" }),
                    "bg-transparent"
                )}
            >
                <UsersIcon />
            </SheetTrigger>
            <SheetContent className="w-[400px] overflow-y-auto sm:w-[540px]">
                <SheetHeader>
                    <SheetTitle>Trulience Avatar</SheetTitle>
                    <SheetDescription>
                        You can configure the Trulience Avatar settings here. This will give you a nice avatar for your chat.
                    </SheetDescription>
                </SheetHeader>

                <div className="my-4">
                    <TrulienceCfgForm
                        initialData={{
                            enable_trulience_avatar: trulienceSettings.enabled,
                            trulience_avatar_id: trulienceSettings.avatarId,
                            trulience_avatar_token: trulienceSettings.avatarToken,
                            trulience_large_window: trulienceSettings.avatarDesktopLargeWindow,
                            trulience_sdk_url: trulienceSettings.trulienceSDK,
                            trulience_animation_url: trulienceSettings.animationURL,
                        }}
                        onUpdate={async (data) => {
                            if (data.enable_trulience_avatar === true) {
                                if (!data.trulience_avatar_id || !data.trulience_avatar_token) {
                                    toast.error("Trulience Settings", {
                                        description: `Please provide Trulience Avatar ID and Token`,
                                    })
                                    return
                                }
                            }
                            dispatch(setTrulienceSettings({
                                enabled: data.enable_trulience_avatar as boolean,
                                avatarId: data.trulience_avatar_id as string,
                                avatarToken: data.trulience_avatar_token as string,
                                avatarDesktopLargeWindow: data.trulience_large_window as boolean,
                                trulienceSDK: data.trulience_sdk_url as string,
                                animationURL: data.trulience_animation_url as string,
                            }))
                            toast.success("Trulience Settings", {
                              description: `Settings updated successfully`,
                            })
                        }}
                    />
                </div>
            </SheetContent>
        </Sheet>
    );
}

const TrulienceCfgForm = ({
    initialData,
    onUpdate,
}: {
    initialData: Record<string, string | boolean | null | undefined>;
    onUpdate: (data: Record<string, string | boolean | null>) => void;
}) => {
    const formSchema = z.record(z.string(),
        z.union([z.string(), z.boolean(), z.null()]));
    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: initialData,
    });
    const { watch } = form;
    // Watch for changes in "enable_trulience_avatar" field
    const enableTrulienceAvatar = watch("enable_trulience_avatar");

    const onSubmit = (data: z.infer<typeof formSchema>) => {
        onUpdate(data);
    };
    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                <FormField
                    key={"enable_trulience_avatar"}
                    control={form.control}
                    name={"enable_trulience_avatar"}
                    render={({ field }) => (
                        <FormItem>
                            <FormLabel>Enable Trulience Avatar</FormLabel>
                            <div className="flex justify-between items-center">
                                <FormControl>
                                    <div className="flex items-center space-x-2">
                                        <Switch
                                            checked={field.value === true}
                                            onCheckedChange={field.onChange}
                                        />
                                    </div>
                                </FormControl>
                            </div>
                        </FormItem>
                    )}
                />
                {
                    enableTrulienceAvatar && (
                        <>
                            <FormField
                                key={"trulience_avatar_id"}
                                control={form.control}
                                name={"trulience_avatar_id"}
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Trulience Avatar ID</FormLabel>
                                        <div className="flex justify-between items-center">
                                            <FormControl>
                                                <Input
                                                    {...field}
                                                    value={
                                                        field.value === null || field.value === undefined
                                                            ? ""
                                                            : field.value.toString()
                                                    }
                                                    type={"text"}
                                                />
                                            </FormControl>
                                        </div>
                                    </FormItem>
                                )}
                            />
                            <FormField
                                key={"trulience_avatar_token"}
                                control={form.control}
                                name={"trulience_avatar_token"}
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Trulience Avatar Token</FormLabel>
                                        <div className="flex justify-between items-center">
                                            <FormControl>
                                                <Input
                                                    {...field}
                                                    value={
                                                        field.value === null || field.value === undefined
                                                            ? ""
                                                            : field.value.toString()
                                                    }
                                                    type={"text"}
                                                />
                                            </FormControl>
                                        </div>
                                    </FormItem>
                                )}
                            />
                            <FormField
                                key={"trulience_large_window"}
                                control={form.control}
                                name={"trulience_large_window"}
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Trulience Large Window</FormLabel>
                                        <div className="flex justify-between items-center">
                                            <FormControl>
                                                <div className="flex items-center space-x-2">
                                                    <Switch
                                                        checked={field.value === true}
                                                        onCheckedChange={field.onChange}
                                                    />
                                                </div>
                                            </FormControl>
                                        </div>
                                    </FormItem>
                                )}
                            />
                            <FormField
                                key={"trulience_sdk_url"}
                                control={form.control}
                                name={"trulience_sdk_url"}
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Trulience SDK URL</FormLabel>
                                        <div className="flex justify-between items-center">
                                            <FormControl>
                                                <Input
                                                    {...field}
                                                    value={
                                                        field.value === null || field.value === undefined
                                                            ? ""
                                                            : field.value.toString()
                                                    }
                                                    type={"text"}
                                                />
                                            </FormControl>
                                        </div>
                                    </FormItem>
                                )}
                            />
                            <FormField
                                key={"trulience_animation_url"}
                                control={form.control}
                                name={"trulience_animation_url"}
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Trulience Animation URL</FormLabel>
                                        <div className="flex justify-between items-center">
                                            <FormControl>
                                                <Input
                                                    {...field}
                                                    value={
                                                        field.value === null || field.value === undefined
                                                            ? ""
                                                            : field.value.toString()
                                                    }
                                                    type={"text"}
                                                />
                                            </FormControl>
                                        </div>
                                    </FormItem>
                                )}
                            />
                        </>
                    )
                }
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
