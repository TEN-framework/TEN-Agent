import { Select, Button, message, Upload, UploadProps } from "antd"
import { useState } from "react"
import { PlusOutlined, LoadingOutlined } from '@ant-design/icons';
import { REQUEST_URL, useAppSelector, genUUID } from "@/common"
import { IPdfData } from "@/types"

import styles from "./index.module.scss"

interface PdfSelectProps {
  onSuccess?: (data: IPdfData) => void
}

const PdfUpload = (props: PdfSelectProps) => {
  const { onSuccess } = props
  const agentConnected = useAppSelector(state => state.global.agentConnected)
  const options = useAppSelector(state => state.global.options)
  const { channel, userId } = options

  const [uploading, setUploading] = useState(false)

  const uploadProps: UploadProps = {
    accept: "application/pdf",
    maxCount: 1,
    showUploadList: false,
    action: `${REQUEST_URL}/vector/document/upload`,
    data: {
      channel_name: channel,
      uid: String(userId),
      request_id: genUUID()
    },
    onChange: (info) => {
      const { file } = info
      const { status, name } = file
      if (status == "uploading") {
        setUploading(true)
      } else if (status == 'done') {
        setUploading(false)
        const { response } = file
        if (response.code == "0") {
          message.success(`Upload ${name} success`)
          const { collection, file_name } = response.data
          onSuccess && onSuccess({
            fileName: file_name,
            collection
          })
        } else {
          message.error(response.msg)
        }
      } else if (status == 'error') {
        setUploading(false)
        message.error(`Upload ${name} failed`)
      }
    }
  }

  const onClickUploadPDF = (e: any) => {
    if (!agentConnected) {
      message.error("Please connect to agent first")
      e.stopPropagation()
    }
  }


  return <Upload {...uploadProps}>
    <Button className={styles.btn} type="text"
      icon={uploading ? <LoadingOutlined></LoadingOutlined> : <PlusOutlined />}
      onClick={onClickUploadPDF}>
      Upload PDF
    </Button>
  </Upload>
}


export default PdfUpload
