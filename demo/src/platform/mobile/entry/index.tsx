import Chat from "../chat"
import Description from "../description"
import Rtc from "../rtc"
import Header from "../header"
import Menu, { IMenuData } from "../menu"
import styles from "./index.module.scss"
import FormModal from "@/components/settings"


const MenuData: IMenuData[] = [{
  name: "Agent",
  component: <Rtc></Rtc>,
}, {
  name: "Chat",
  component: <Chat></Chat>,
}]


const MobileEntry = () => {

  return <div className={styles.entry}>
    <Header></Header>
    <Description></Description>
    <div className={styles.content}>
      <Menu data={MenuData}></Menu>
    </div>
    <FormModal></FormModal>
  </div>
}


export default MobileEntry
