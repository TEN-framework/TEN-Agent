import { ReactElement, useState } from "react"
import { PdfIcon } from "@/components/icons"
import CustomSelect from "@/components/customSelect"
import { Divider, message } from 'antd';
import { useEffect } from 'react';
import { apiGetDocumentList, apiUpdateDocument, useAppSelector } from "@/common"
import PdfUpload from "./upload"
import { OptionType, IPdfData } from "@/types"

import styles from "./index.module.scss"

const PdfSelect = () => {
  const options = useAppSelector(state => state.global.options)
  const { channel } = options
  const [pdfOptions, setPdfOptions] = useState<OptionType[]>([])
  const [selectedPdf, setSelectedPdf] = useState<string>('')
  const agentConnected = useAppSelector(state => state.global.agentConnected)


  useEffect(() => {
    if(agentConnected) {
      getPDFOptions()
    } else {
      setPdfOptions([{
        value: '',
        label: 'Please select a PDF file'
      }])
    }
  }, [agentConnected])


  const getPDFOptions = async () => {
    const res = await apiGetDocumentList()
    setPdfOptions([{
      value: '',
      label: 'Please select a PDF file'
    }].concat(res.data.map((item: any) => {
      return {
        value: item.collection,
        label: item.file_name
      }
    })))
    setSelectedPdf('')
  }

  const onUploadSuccess = (data: IPdfData) => {
    setPdfOptions([...pdfOptions, {
      value: data.collection,
      label: data.fileName
    }])
    setSelectedPdf(data.collection)
  }

  const pdfDropdownRender = (menu: ReactElement) => {
    return <>
      {menu}
      <Divider style={{ margin: '8px 0', background: "#272A2F" }} />
      <div className={styles.dropdownRender} >
        <PdfUpload onSuccess={onUploadSuccess}></PdfUpload>
      </div >
    </>
  }


  const onSelectPdf = async (val: string) => {
    const item = pdfOptions.find(item => item.value === val)
    if (!item) {
      return message.error("Please select a PDF file")
    }
    setSelectedPdf(val)
    await apiUpdateDocument({
      collection: val,
      fileName: item.label,
      channel
    })
  }


  return <CustomSelect
    prefixIcon={<PdfIcon></PdfIcon>}
    onChange={onSelectPdf}
    value={selectedPdf}
    options={pdfOptions}
    dropdownRender={pdfDropdownRender}
    className={styles.pdfSelect} placeholder="Select a PDF file"></CustomSelect>
}

export default PdfSelect
