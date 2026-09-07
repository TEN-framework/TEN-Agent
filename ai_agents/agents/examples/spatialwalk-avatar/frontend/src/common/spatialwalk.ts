type SpatialwalkMissingField = "appId" | "avatarId";

export interface SpatialwalkUrlConfig {
  appId: string;
  avatarId: string;
}

export interface SpatialwalkValidationResult {
  isValid: boolean;
  missingFields: SpatialwalkMissingField[];
  message: string;
}

const isBlank = (value: string | null | undefined): boolean =>
  !value || value.trim().length === 0;

export const getSpatialwalkUrlConfig = (): SpatialwalkUrlConfig => {
  if (typeof window === "undefined") {
    return { appId: "", avatarId: "" };
  }
  const params = new URLSearchParams(window.location.search);
  return {
    appId: params.get("appId")?.trim() || "",
    avatarId: params.get("avatarId")?.trim() || "",
  };
};

export const validateSpatialwalkRequiredConfig = (
  config: SpatialwalkUrlConfig
): SpatialwalkValidationResult => {
  const missingFields: SpatialwalkMissingField[] = [];
  if (isBlank(config.appId)) {
    missingFields.push("appId");
  }
  if (isBlank(config.avatarId)) {
    missingFields.push("avatarId");
  }

  if (missingFields.length === 0) {
    return { isValid: true, missingFields, message: "" };
  }

  if (missingFields.length === 2) {
    return {
      isValid: false,
      missingFields,
      message: "Missing URL params: appId and avatarId.",
    };
  }

  return {
    isValid: false,
    missingFields,
    message:
      missingFields[0] === "appId"
        ? "Missing URL param: appId."
        : "Missing URL param: avatarId.",
  };
};
