import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircleIcon, UsersIcon } from "lucide-react";
import * as React from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { useAppDispatch, useAppSelector } from "@/common/hooks";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { setSpatialwalkSettings } from "@/store/reducers/global";
import type { ISpatialwalkSettings } from "@/types";

export function SpatialwalkCfgSheet() {
  const dispatch = useAppDispatch();
  const spatialwalkSettings = useAppSelector(
    (state) => state.global.spatialwalkSettings
  );

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
          <SheetTitle>Spatialwalk Avatar</SheetTitle>
          <SheetDescription>
            `appId` and `avatarId` come from URL query params. Configure only
            environment here.
          </SheetDescription>
        </SheetHeader>

        <div className="my-4">
          <SpatialwalkCfgForm
            initialData={{
              spatialwalk_env: spatialwalkSettings.environment,
            }}
            onUpdate={async (data) => {
              const nextSettings: ISpatialwalkSettings = {
                enabled: true,
                avatarId: spatialwalkSettings.avatarId,
                appId: spatialwalkSettings.appId,
                environment: (data.spatialwalk_env as "cn" | "intl") || "intl",
                avatarDesktopLargeWindow: true,
              };
              dispatch(setSpatialwalkSettings(nextSettings));
              toast.success("Spatialwalk Settings", {
                description: "Settings updated successfully",
              });
            }}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}

const SpatialwalkCfgForm = ({
  initialData,
  onUpdate,
}: {
  initialData: Record<string, string | boolean | null | undefined>;
  onUpdate: (data: Record<string, string | boolean | null>) => void;
}) => {
  const formSchema = z.record(
    z.string(),
    z.union([z.string(), z.boolean(), z.null()])
  );
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: initialData,
  });

  const onSubmit = (data: z.infer<typeof formSchema>) => {
    onUpdate(data);
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField
          key={"spatialwalk_env"}
          control={form.control}
          name={"spatialwalk_env"}
          render={({ field }) => (
            <FormItem>
              <FormLabel>Environment</FormLabel>
              <FormControl>
                <Select
                  value={
                    field.value === null || field.value === undefined
                      ? "cn"
                      : field.value.toString()
                  }
                  onValueChange={field.onChange}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select environment" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cn">CN</SelectItem>
                    <SelectItem value="intl">Intl</SelectItem>
                  </SelectContent>
                </Select>
              </FormControl>
            </FormItem>
          )}
        />
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
