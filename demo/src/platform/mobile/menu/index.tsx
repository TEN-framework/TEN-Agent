"use client"

import { ReactElement, useEffect, useState, useRef, useMemo, useCallback } from "react"
import { useAutoScroll } from "@/common"
import { MenuContext } from "./context"
import styles from "./index.module.scss"

export interface IMenuData {
  name: string,
  component: ReactElement
}

export interface IMenuContentComponentPros {
  scrollToBottom: () => void
}

interface MenuProps {
  data: IMenuData[]
}


const Menu = (props: MenuProps) => {
  const { data } = props
  const [activeIndex, setActiveIndex] = useState(0)
  const contentRefList = useRef<(HTMLDivElement | null)[]>([])

  const onClickItem = (index: number) => {
    setActiveIndex(index)
  }

  useEffect(() => {
    scrollToTop()
  }, [activeIndex])

  const scrollToBottom = useCallback(() => {
    const current = contentRefList.current?.[activeIndex]
    if (current) {
      current.scrollTop = current.scrollHeight
    }
  }, [contentRefList, activeIndex])

  const scrollToTop = useCallback(() => {
    const current = contentRefList.current?.[activeIndex]
    if (current) {
      current.scrollTop = 0
    }
  }, [contentRefList, activeIndex])


  return <div className={styles.menu}>
    <section className={styles.header}>
      {data.map((item, index) => {
        return <span
          key={index}
          className={`${styles.menuItem} ${index == activeIndex ? styles.active : ''}`}
          onClick={() => onClickItem(index)}>{item.name}</span>
      })}
    </section>
    <section className={styles.content} >
      <MenuContext.Provider value={{ scrollToBottom }}>
        {data.map((item, index) => {
          return <div
            key={index}
            ref={el => {
              contentRefList.current[index] = el;
            }}
            className={`${styles.item} ${index == activeIndex ? styles.active : ''}`}>
            {item.component}
          </div>
        })}
      </MenuContext.Provider>
    </section>
  </div >
}

export default Menu
