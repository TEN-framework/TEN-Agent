"use client"

import { HexColorPicker } from "react-colorful";
import { useAppSelector, useAppDispatch } from "@/common"
import { setThemeColor } from "@/store/reducers/global"
import styles from "./index.module.scss";

const ColorPicker = () => {
  const dispatch = useAppDispatch()
  const themeColor = useAppSelector(state => state.global.themeColor)

  const onColorChange = (color: string) => {
    console.log(color);
    dispatch(setThemeColor(color))
  };

  return <div className={styles.colorPicker}>
    <HexColorPicker color={themeColor} onChange={onColorChange} />
  </div>
};

export default ColorPicker;
