import { useMemo } from "react"
import { COLOR_LIST, useAppSelector, useAppDispatch } from "@/common"
import { setThemeColor } from "@/store/reducers/global"
import ColorPicker from "./colorPicker"
import { Popover } from 'antd';


import styles from "./index.module.scss"

interface StylePopoverProps {
  children?: React.ReactNode
}

const StylePopover = (props: StylePopoverProps) => {
  const { children } = props
  const dispatch = useAppDispatch()
  const themeColor = useAppSelector(state => state.global.themeColor)


  const onClickColor = (index: number) => {
    const target = COLOR_LIST[index]
    if (target.active !== themeColor) {
      dispatch(setThemeColor(target.active))
    }
  }

  const content = <section className={styles.info}>
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
    <ColorPicker></ColorPicker>
  </section>


  return <Popover content={content} arrow={false}>{children}</Popover>

}

export default StylePopover
