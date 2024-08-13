"use client"

import AgoraRTC from "agora-rtc-sdk-ng"
import { useState, useEffect } from "react"
import { Select } from "antd"
import { IMicrophoneAudioTrack } from "agora-rtc-sdk-ng"

import styles from "./index.module.scss"

interface MicSelectProps {
  audioTrack?: IMicrophoneAudioTrack
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

const MicSelect = (props: MicSelectProps) => {
  const { audioTrack } = props
  const [items, setItems] = useState<SelectItem[]>([DEFAULT_ITEM]);
  const [value, setValue] = useState("default");

  useEffect(() => {
    if (audioTrack) {
      const label = audioTrack?.getTrackLabel();
      setValue(label);
      AgoraRTC.getMicrophones().then(arr => {
        setItems(arr.map(item => ({
          label: item.label,
          value: item.label,
          deviceId: item.deviceId
        })));
      });
    }
  }, [audioTrack]);

  const onChange = async (value: string) => {
    const target = items.find(item => item.value === value);
    if (target) {
      setValue(target.value);
      if (audioTrack) {
        await audioTrack.setDevice(target.deviceId);
      }
    }
  }

  return <Select className={styles.select} value={value} options={items} onChange={onChange}></Select>
}

export default MicSelect 
