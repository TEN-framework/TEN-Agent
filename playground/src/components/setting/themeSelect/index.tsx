import { useState } from "react"
import { COLOR_LIST, useAppSelector,useAppDispatch } from "@/common"
import styles from "./index.module.scss"
import { setThemeColor } from "@/store/reducers/global"

const ThemeSelect = () => {
  const dispatch = useAppDispatch()
  const themeColor = useAppSelector((state) => state.global.themeColor)

  const onClickColor = (index: number) => {
    const target = COLOR_LIST[index]
    if (target.active !== themeColor) {
      dispatch(setThemeColor(target.active))
    }
  }

  return <section className={styles.style}>
    <div className={styles.title}>STYLE</div>
    <div className={styles.color}>
      {
        COLOR_LIST.map((item, index) => {
          return <span
            style={{
              borderColor: item.active == themeColor ? item.active : "transparent",
            }}
            onClick={() => onClickColor(index)}
            className={styles.item}
            key={index}>
            <span className={styles.inner} style={{
              backgroundColor: item.active == themeColor ? item.active : item.default,
            }}></span>
          </span>
        })
      }
    </div>
  </section>
}


export default ThemeSelect
