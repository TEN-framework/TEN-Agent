"use client";

import {
  EMobileActiveTab,
  MOBILE_ACTIVE_TAB_MAP,
  useAppDispatch,
  useAppSelector,
} from "@/common";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { setMobileActiveTab } from "@/store/reducers/global";
import { SpatialwalkCfgSheet } from "../Chat/ChatCfgSpatialwalkSetting";

export default function Action(props: { className?: string }) {
  const { className } = props;
  const dispatch = useAppDispatch();
  const mobileActiveTab = useAppSelector(
    (state) => state.global.mobileActiveTab
  );

  const onChangeMobileActiveTab = (tab: string) => {
    dispatch(setMobileActiveTab(tab as EMobileActiveTab));
  };

  return (
    <>
      {/* Action Bar */}
      <div
        className={cn(
          "mx-2 mt-2 flex items-center justify-between rounded-t-lg bg-[#181a1d] p-2 md:m-2 md:rounded-lg",
          className
        )}
      >
        {/* -- Description Part */}
        <div className="hidden md:block">
          <span className="font-bold text-sm">Description</span>
          <span className="ml-2 whitespace-nowrap text-muted-foreground text-xs">
            A Realtime Conversational AI Agent powered by TEN
          </span>
        </div>

        <div className="flex w-full flex-col justify-between md:flex-row md:items-center md:justify-end">
          {/* -- Tabs Section */}
          <Tabs
            defaultValue={mobileActiveTab}
            className="w-full md:hidden md:flex-row"
            onValueChange={onChangeMobileActiveTab}
          >
            <TabsList className="flex justify-center md:justify-start">
              {Object.values(EMobileActiveTab).map((tab) => (
                <TabsTrigger key={tab} value={tab} className="w-24 text-sm">
                  {MOBILE_ACTIVE_TAB_MAP[tab]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          {/* -- Settings */}
          <div className="mt-2 flex w-full items-center justify-between gap-2 md:mt-0 md:w-auto md:flex-wrap">
            <SpatialwalkCfgSheet />
          </div>
        </div>
      </div>
    </>
  );
}
