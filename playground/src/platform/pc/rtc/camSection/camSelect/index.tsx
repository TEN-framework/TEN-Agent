"use client"

import AgoraRTC, { ICameraVideoTrack } from "agora-rtc-sdk-ng"
import { useState, useEffect } from "react"
import { Select } from "antd"

import styles from "./index.module.scss"

interface CamSelectProps {
  videoTrack?: ICameraVideoTrack
}

interface SelectItem {
  label: string
  value: string
  deviceId: string
}

const DEFAULT_ITEM: SelectItem = {
  label: "Default",
  value: "default",
  deviceId: ""
}

const CamSelect = (props: CamSelectProps) => {
  const { videoTrack } = props
  const [items, setItems] = useState<SelectItem[]>([DEFAULT_ITEM]);
  const [value, setValue] = useState("default");

  useEffect(() => {
    if (videoTrack) {
      const label = videoTrack?.getTrackLabel();
      setValue(label);
      AgoraRTC.getCameras().then(arr => {
        setItems(arr.map(item => ({
          label: item.label,
          value: item.label,
          deviceId: item.deviceId
        })));
      });
    }
  }, [videoTrack]);

  const onChange = async (value: string) => {
    const target = items.find(item => item.value === value);
    if (target) {
      setValue(target.value);
      if (videoTrack) {
        await videoTrack.setDevice(target.deviceId);
      }
    }
  }

  return <Select className={styles.select} value={value} options={items} onChange={onChange}></Select>
}

export default CamSelect 
